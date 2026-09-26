import json
import os
from dataclasses import dataclass

import cv2
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input

from app import db, utcnow
from app.models.hasil_labeling import HasilLabeling
from app.models.hasil_labeling_item import HasilLabelingItem
from app.models.label_kerusakan import LabelKerusakan
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.tingkat_kerusakan import TingkatKerusakan


@dataclass(frozen=True)
class LabelingDefaults:
    image_size: tuple = (224, 224)
    canny_low: int = 50
    canny_high: int = 150
    pca_components: int = 50
    n_clusters: int = 4
    random_state: int = 42
    n_init: int = 10


DEFAULTS = LabelingDefaults()
_MODEL = None


def _embedding_model():
    global _MODEL
    if _MODEL is None:
        _MODEL = MobileNetV2(
            input_shape=(*DEFAULTS.image_size, 3),
            include_top=False,
            pooling='avg',
            weights='imagenet',
        )
    return _MODEL


def _resolve_image_path(image_path, upload_folder):
    if os.path.isabs(image_path):
        return image_path
    normalized = os.path.normpath(image_path)
    marker = os.path.normpath(os.path.join('uploads', 'foto'))
    if normalized.lower().startswith(marker.lower() + os.sep):
        return os.path.join(os.path.dirname(os.path.dirname(upload_folder)), normalized)
    return os.path.join(upload_folder, os.path.basename(normalized))


def ekstrak_fitur_foto(image_path, canny_low=50, canny_high=150):
    image = cv2.imread(image_path)
    if image is None:
        raise ValueError(f'citra tidak dapat dibaca: {image_path}')

    resized = cv2.resize(image, DEFAULTS.image_size, interpolation=cv2.INTER_LANCZOS4)
    rgb = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
    batch = preprocess_input(rgb.astype(np.float32))[np.newaxis, ...]
    embedding = _embedding_model().predict(batch, verbose=0)[0].astype(np.float32)

    grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
    edges = cv2.Canny(grayscale, canny_low, canny_high)
    edge_density = float(edges.mean() / 255.0)
    return embedding, edge_density


def ekstrak_fitur_lokasi(lokasi_list, upload_folder, canny_low=50, canny_high=150, on_progress=None):
    """
    Ekstraksi embedding MobileNetV2 + kepadatan tepi per lokasi.
    on_progress(selesai, total) dipanggil tiap lokasi supaya UI bisa menampilkan persen.
    """
    fitur_dict = {}
    dilewati = []
    total = len(lokasi_list)

    for nomor, lokasi in enumerate(lokasi_list, start=1):
        foto_list = list(getattr(lokasi, 'foto_list', None) or [])
        if not foto_list:
            dilewati.append({'lokasi_id': lokasi.id, 'alasan': 'lokasi tidak memiliki foto'})
            if on_progress:
                on_progress(nomor, total)
            continue

        embeddings = []
        edge_densities = []
        errors = []
        for foto in foto_list:
            path = _resolve_image_path(foto.path_file, upload_folder)
            if not os.path.isfile(path):
                errors.append(
                    f"file tidak ditemukan: {getattr(foto, 'nama_file', foto.path_file)}"
                )
                continue
            try:
                embedding, edge_density = ekstrak_fitur_foto(
                    path, canny_low=canny_low, canny_high=canny_high
                )
            except (OSError, ValueError, cv2.error) as exc:
                errors.append(str(exc))
                continue
            embeddings.append(embedding)
            edge_densities.append(edge_density)

        if not embeddings:
            reason = '; '.join(errors) or 'tidak ada foto valid'
            dilewati.append({'lokasi_id': lokasi.id, 'alasan': reason})
            if on_progress:
                on_progress(nomor, total)
            continue

        fitur_dict[lokasi.id] = {
            'embedding': np.mean(np.stack(embeddings), axis=0),
            'kepadatan_tepi': float(np.mean(edge_densities)),
        }
        if on_progress:
            on_progress(nomor, total)

    return fitur_dict, dilewati


def klasterisasi(fitur_dict, n_cluster=4, pca_komponen=50, random_state=42):
    if len(fitur_dict) < n_cluster:
        raise ValueError(
            f'minimal {n_cluster} lokasi dengan foto valid diperlukan untuk klasterisasi'
        )
    if n_cluster < 2:
        raise ValueError('jumlah klaster minimal 2')

    lokasi_ids = list(fitur_dict)
    matrix = np.stack([np.asarray(fitur_dict[key]['embedding']) for key in lokasi_ids])
    scaled = StandardScaler().fit_transform(matrix)
    n_components = min(pca_komponen, scaled.shape[0], scaled.shape[1])
    if n_components < 1:
        raise ValueError('fitur visual tidak memiliki dimensi yang valid')

    pca = PCA(n_components=n_components, random_state=random_state)
    reduced = pca.fit_transform(scaled)
    model = KMeans(
        n_clusters=n_cluster,
        random_state=random_state,
        n_init=DEFAULTS.n_init,
    )
    labels = model.fit_predict(reduced)

    hasil = {}
    for index, lokasi_id in enumerate(lokasi_ids):
        cluster_id = int(labels[index])
        distance = float(np.linalg.norm(reduced[index] - model.cluster_centers_[cluster_id]))
        hasil[lokasi_id] = {'klaster': cluster_id, 'jarak_centroid': distance}
    return hasil, float(pca.explained_variance_ratio_.sum())


def urutkan_klaster_ke_tingkat(hasil_klaster, fitur_dict):
    edge_by_cluster = {}
    for lokasi_id, hasil in hasil_klaster.items():
        cluster_id = hasil['klaster']
        edge_by_cluster.setdefault(cluster_id, []).append(
            fitur_dict[lokasi_id]['kepadatan_tepi']
        )

    ordered_clusters = sorted(
        edge_by_cluster,
        key=lambda cluster_id: float(np.mean(edge_by_cluster[cluster_id])),
    )
    names = ('Baik', 'Sedang', 'Rusak Ringan', 'Rusak Berat')
    mapping = {}
    for cluster_id, name in zip(ordered_clusters, names):
        tingkat = TingkatKerusakan.query.filter_by(nama_tingkat=name).first()
        if tingkat is None:
            raise LookupError(f'tingkat kerusakan tidak ditemukan: {name}')
        mapping[cluster_id] = tingkat.id
    return mapping


def _persen_ekstraksi(persen_ekstraksi, selesai, total):
    """Peta (0..90% dari 280 lokasi) → (0..100%) supaya sisa waktu klasterisasi terlihat."""
    if not total:
        return 5
    return round(5 + (selesai / total) * persen_ekstraksi)


def jalankan_klasterisasi(config, upload_folder, pengguna_id,
                          on_progress=None, on_run=None, progress=None):
    """
    Jalankan klasterisasi menjadi baris review tanpa mengubah label yang sudah ada.

    on_progress(selesai, total)  — progres ekstraksi fitur per lokasi.
    on_run(run)                  — dipanggil setelah baris HasilLabeling tersimpan, agar
                                   pemanggil bisa memberi tahu UI ke mana harus redirect.
    progress(pct, step)          — progres gabungan 0..100 untuk UI.
    """
    def lapor(pct, step):
        if progress:
            progress(pct, step)

    try:
        lokasi_list = LokasiKerusakan.query.order_by(LokasiKerusakan.id).all()
        lapor(2, f'Memuat {len(lokasi_list)} lokasi…')
        fitur_dict, dilewati = ekstrak_fitur_lokasi(
            lokasi_list,
            upload_folder,
            canny_low=config.canny_low,
            canny_high=config.canny_high,
            on_progress=on_progress,
        )
        if not fitur_dict:
            run = HasilLabeling(
                config_id=config.id,
                jumlah_lokasi=0,
                jumlah_dilewati=len(dilewati),
                status='gagal',
                catatan='Tidak ada lokasi dengan foto valid untuk dilabeli.',
                pengguna_id=pengguna_id,
            )
            db.session.add(run)
            db.session.commit()
            return run

        lapor(92, 'Menjalankan PCA + K-Means…')
        hasil_klaster, variansi_pca = klasterisasi(
            fitur_dict,
            n_cluster=config.n_cluster,
            pca_komponen=config.pca_komponen,
            random_state=config.random_state,
        )
        mapping = urutkan_klaster_ke_tingkat(hasil_klaster, fitur_dict)
        distribution = {}
        for cluster_id, tingkat_id in mapping.items():
            tingkat = db.session.get(TingkatKerusakan, tingkat_id)
            if tingkat is not None:
                distribution[tingkat.nama_tingkat] = sum(
                    result['klaster'] == cluster_id for result in hasil_klaster.values()
                )

        run = HasilLabeling(
            config_id=config.id,
            jumlah_lokasi=len(fitur_dict),
            jumlah_dilewati=len(dilewati),
            variansi_pca=variansi_pca,
            distribusi_kelas=json.dumps(distribution, ensure_ascii=False),
            status='selesai',
            pengguna_id=pengguna_id,
        )
        db.session.add(run)
        db.session.flush()
        for lokasi_id, result in hasil_klaster.items():
            db.session.add(HasilLabelingItem(
                run_id=run.id,
                lokasi_id=lokasi_id,
                klaster=result['klaster'],
                kepadatan_tepi=fitur_dict[lokasi_id]['kepadatan_tepi'],
                jarak_centroid=result['jarak_centroid'],
                tingkat_kerusakan_id=mapping[result['klaster']],
            ))
        db.session.commit()
        lapor(100, 'Selesai.')
        if on_run:
            on_run(run)
        return run
    except Exception as exc:
        db.session.rollback()
        run = HasilLabeling(
            config_id=config.id,
            status='gagal',
            catatan=str(exc),
            pengguna_id=pengguna_id,
        )
        db.session.add(run)
        db.session.commit()
        return run


def terapkan_hasil(run):
    """Apply a completed review run exactly once."""
    if run.status != 'selesai' or run.is_diterapkan:
        return 0

    jumlah = 0
    for item in run.item_list:
        label = LabelKerusakan.query.filter_by(lokasi_id=item.lokasi_id).first()
        if label is None:
            label = LabelKerusakan(
                lokasi_id=item.lokasi_id,
                pengguna_id=run.pengguna_id,
            )
            db.session.add(label)
        label.tingkat_kerusakan_id = item.tingkat_kerusakan_id
        label.metode = 'klasterisasi'
        label.cluster_id = item.klaster
        label.kepadatan_tepi = item.kepadatan_tepi
        label.jarak_centroid = item.jarak_centroid
        label.hasil_labeling_id = run.id
        label.pengguna_id = run.pengguna_id
        jumlah += 1

    run.is_diterapkan = True
    run.diterapkan_at = utcnow()
    db.session.commit()
    return jumlah


def buang_hasil(run):
    """Discard a temporary run and its items without changing labels."""
    db.session.delete(run)
    db.session.commit()
