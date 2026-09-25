import json
import os
from dataclasses import dataclass

import cv2
import numpy as np
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.applications.mobilenet_v2 import MobileNetV2, preprocess_input

from app.models.hasil_labeling import HasilLabeling
from app.models.hasil_labeling_item import HasilLabelingItem
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


def ekstrak_fitur_lokasi(lokasi_list, upload_folder, canny_low=50, canny_high=150):
    fitur_dict = {}
    dilewati = []

    for lokasi in lokasi_list:
        foto_list = list(getattr(lokasi, 'foto_list', None) or [])
        if not foto_list:
            dilewati.append({'lokasi_id': lokasi.id, 'alasan': 'lokasi tidak memiliki foto'})
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
            continue

        fitur_dict[lokasi.id] = {
            'embedding': np.mean(np.stack(embeddings), axis=0),
            'kepadatan_tepi': float(np.mean(edge_densities)),
        }

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
