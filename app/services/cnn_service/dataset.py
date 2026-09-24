"""Muat dan perluas dataset training/validasi dari split K-Fold."""
import os
import hashlib
import numpy as np
from PIL import Image

from sqlalchemy import func
from app import db
from app.models.split_item import SplitItem
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.hasil_preprocessing import HasilPreprocessing

MIN_TRAIN_SAMPLES = 20
MIN_VAL_SAMPLES = 5

# Tahap preprocessing (urutan kumulatif pipeline); semuanya deterministik. Augmentasi training
# ada di dalam model (cnn_service/model.py), bukan di tahap preprocessing.
TRAIN_EXPAND_STEPS = ('resize', 'crop', 'normalisasi', 'denoise')


def _preprocessed_subquery():
    """Path 'denoise' per foto — dipakai untuk validasi/prediksi (1 gambar/foto,
    representatif untuk inferensi foto baru yang sesungguhnya).

    Aman tanpa filter config karena hasil_preprocessing hanya boleh berisi SATU config
    (config aktif): menjalankan preprocessing menggantikan semua hasil sebelumnya.
    """
    return (
        db.session.query(
            HasilPreprocessing.dokumentasi_id,
            func.max(HasilPreprocessing.path_output).label('prep_path'),
        )
        .filter(
            HasilPreprocessing.step_name == 'denoise',
            HasilPreprocessing.status == 'selesai',
            HasilPreprocessing.path_output != '',
        )
        .group_by(HasilPreprocessing.dokumentasi_id)
        .subquery()
    )


def foto_tanpa_preprocessing(split_config_id):
    """Jumlah foto di split yang belum punya hasil 'denoise'. Foto seperti ini diam-diam
    jatuh ke gambar asli saat training, padahal inferensi memakai gambar terproses."""
    sq = _preprocessed_subquery()
    return (
        db.session.query(func.count(SplitItem.id))
        .outerjoin(sq, sq.c.dokumentasi_id == SplitItem.dokumentasi_id)
        .filter(SplitItem.config_id == split_config_id, sq.c.prep_path.is_(None))
        .scalar()
    )


def _stage_map_for(doc_ids=None):
    """dokumentasi_id -> {step_name: path_output} untuk TRAIN_EXPAND_STEPS. Query langsung
    (bukan lewat subquery) supaya bisa dibatasi doc_ids untuk efisiensi."""
    q = (
        db.session.query(
            HasilPreprocessing.dokumentasi_id,
            HasilPreprocessing.step_name,
            func.max(HasilPreprocessing.path_output).label('prep_path'),
        )
        .filter(
            HasilPreprocessing.step_name.in_(TRAIN_EXPAND_STEPS),
            HasilPreprocessing.status == 'selesai',
            HasilPreprocessing.path_output != '',
        )
    )
    if doc_ids is not None:
        q = q.filter(HasilPreprocessing.dokumentasi_id.in_(list(doc_ids)))
    rows = q.group_by(HasilPreprocessing.dokumentasi_id, HasilPreprocessing.step_name).all()

    stage_map = {}
    for doc_id, step_name, path in rows:
        stage_map.setdefault(doc_id, {})[step_name] = path
    return stage_map


def _file_hash(path_rel, base_dir):
    """MD5 isi file (bukan nama path) — dipakai mendeteksi tahap yang hasilnya identik
    byte-per-byte, misal 'crop' == 'resize' saat preprocessing_config.crop_enabled=False."""
    img_path = os.path.join(base_dir, 'app', 'static', path_rel)
    try:
        with open(img_path, 'rb') as f:
            return hashlib.md5(f.read()).hexdigest()
    except OSError:
        return None


def distinct_stage_paths(doc_id, stage_map, base_dir):
    """
    Path tahap non-acak (TRAIN_EXPAND_STEPS) untuk 1 foto, dengan tahap yang KONTEN
    file-nya identik (bukan cuma nama tahapnya beda) di-dedup — supaya gambar yang sama
    tidak dihitung/dipakai dua kali sebagai sampel terpisah (misal saat crop_enabled=False
    atau denoise_method='none', tahap tsb jadi salinan tahap sebelumnya tanpa transformasi).
    """
    stages = stage_map.get(doc_id, {})
    seen_hashes, paths = set(), []
    for step in TRAIN_EXPAND_STEPS:
        path_rel = stages.get(step)
        if not path_rel:
            continue
        h = _file_hash(path_rel, base_dir)
        if h is not None and h in seen_hashes:
            continue
        if h is not None:
            seen_hashes.add(h)
        paths.append(path_rel)
    return paths


def effective_sample_count(doc_ids, base_dir):
    """Jumlah sampel training/val efektif per set foto setelah dedup konten identik antar
    tahap. Dipakai split_controller untuk statistik UI, konsisten dengan load_dataset."""
    if not doc_ids:
        return 0
    stage_map = _stage_map_for(doc_ids)
    total = 0
    for doc_id in doc_ids:
        n = len(distinct_stage_paths(doc_id, stage_map, base_dir))
        total += n if n > 0 else 1
    return total


def _group_aware_split(groups, labels, test_size, seed):
    """
    Seperti train_test_split, tapi men-split di level GRUP (foto), bukan level sampel.
    Semua sampel dengan group id yang sama selalu jatuh di sisi yang sama (fit ATAU inner-val),
    tidak pernah dua-duanya — mencegah kebocoran sampel nyaris-identik (varian tahap
    preprocessing dari foto yang sama) antara data fit dan data validasi internal.

    groups, labels: array/list sepanjang jumlah sampel.
    Return (idx_a, idx_b) — index sampel untuk sisi 'fit' dan 'inner-val'.
    """
    from sklearn.model_selection import train_test_split as _tts

    groups = np.asarray(groups)
    labels = np.asarray(labels)

    uniq_groups, first_pos = np.unique(groups, return_index=True)
    uniq_labels = labels[first_pos]

    grp_a, grp_b = _tts(uniq_groups, test_size=test_size, stratify=uniq_labels, random_state=seed)
    set_b = set(grp_b.tolist())

    mask_b = np.array([g in set_b for g in groups])
    idx_a = np.where(~mask_b)[0]
    idx_b = np.where(mask_b)[0]
    return idx_a, idx_b


def load_dataset(split_config_id, fold_val, input_size, base_dir):
    """
    Muat dataset untuk satu fold.

    Training: diperluas memakai semua tahap non-acak yang tersedia (resize, crop,
    normalisasi, denoise) sebagai sampel terpisah dengan label yang sama → dataset
    bertambah tanpa foto baru. 'augmentasi' dikecualikan (acak, tidak reproducible). Tahap
    yang KONTEN file-nya identik dengan tahap lain di foto yang sama (misal 'crop' ==
    'resize' saat preprocessing_config.crop_enabled=False) di-dedup lewat
    distinct_stage_paths — supaya gambar yang sama tidak dihitung dua kali dengan bobot
    ganda. Foto yang belum dipreprocessing sama sekali fallback ke 1 sampel original.

    Validasi/fold uji: KEMBALI ke 1 gambar per foto (utamakan tahap denoise, fallback
    original) — SAMA seperti predict_all/predict_cv/klasifikasi foto baru. Keputusan
    2026-09-23: sempat dicoba ikut diperluas seperti training, tapi itu membuat evaluate()
    (HasilEvaluasi, "Akurasi Model Final") mengukur pada sampel yang saling BERKORELASI
    (beberapa versi dari foto yang sama, bukan titik data independen) — sehingga tidak lagi
    sebanding dengan cv_summary()/predict_cv (yang selalu 1 gambar/foto) dan membuat angka
    akurasi antar-run jadi lebih berisik tanpa manfaat nyata (val tidak butuh "lebih banyak
    data", val cuma butuh representatif).

    groups_train (dokumentasi_id per sampel training) dikembalikan agar pemanggil bisa
    beroperasi di level foto — dipakai _group_aware_split di train() supaya varian tahap
    dari foto yang sama tidak saling bocor antara data fit dan inner-val.
    """
    prep_sq = _preprocessed_subquery()   # 1 path 'denoise' per foto → dipakai untuk val

    rows = (
        db.session.query(
            SplitItem.dokumentasi_id,
            SplitItem.fold_index,
            SplitItem.tingkat_kerusakan_id,
            DokumentasiFoto.path_file,
            prep_sq.c.prep_path,
        )
        .join(DokumentasiFoto, SplitItem.dokumentasi_id == DokumentasiFoto.id)
        .outerjoin(prep_sq, prep_sq.c.dokumentasi_id == SplitItem.dokumentasi_id)
        .filter(SplitItem.config_id == split_config_id)
        .all()
    )
    stage_map = _stage_map_for({r.dokumentasi_id for r in rows})
    # Release DB connection back to pool before the slow image-loading loop
    db.session.remove()

    def _load(path_rel):
        img_path = os.path.join(base_dir, 'app', 'static', path_rel)
        if not os.path.isfile(img_path):
            return None
        try:
            img = Image.open(img_path).convert('RGB').resize((input_size, input_size))
            return np.array(img, dtype=np.float32)  # [0,255] — preprocess_input ada di dalam model
        except Exception:
            return None

    X_train, y_train, groups_train = [], [], []
    X_val, y_val, groups_val = [], [], []
    skipped = 0
    prep_used = 0
    expanded = 0

    for row in rows:
        is_val = fold_val is not None and row.fold_index == fold_val   # fold_val None → model final, semua data untuk training
        label = int(row.tingkat_kerusakan_id) - 1

        if is_val:
            path_rel = row.prep_path or row.path_file
            arr = _load(path_rel)
            if arr is None:
                skipped += 1
                continue
            if row.prep_path:
                prep_used += 1
            X_val.append(arr)
            y_val.append(label)
            groups_val.append(row.dokumentasi_id)
            continue

        paths = distinct_stage_paths(row.dokumentasi_id, stage_map, base_dir)
        added = 0
        for path_rel in paths:
            arr = _load(path_rel)
            if arr is None:
                continue
            X_train.append(arr)
            y_train.append(label)
            groups_train.append(row.dokumentasi_id)
            added += 1
            prep_used += 1
        if added == 0:
            arr = _load(row.path_file)
            if arr is None:
                skipped += 1
                continue
            X_train.append(arr)
            y_train.append(label)
            groups_train.append(row.dokumentasi_id)
        elif added > 1:
            expanded += 1

    if prep_used > 0 or skipped > 0:
        print(f'[load_dataset] train={len(X_train)} val={len(X_val)} '
              f'({prep_used} preprocessed dari {expanded} foto training diperbanyak, skip={skipped})')

    if len(X_train) < MIN_TRAIN_SAMPLES:
        raise ValueError(
            f'Dataset training terlalu kecil ({len(X_train)} gambar). '
            f'Periksa path file — {skipped} gambar gagal dimuat.'
        )
    if fold_val is not None and len(X_val) < MIN_VAL_SAMPLES:
        raise ValueError(
            f'Dataset validasi terlalu kecil ({len(X_val)} gambar). '
            f'Periksa fold_val={fold_val} dan path file.'
        )

    return (
        np.array(X_train, dtype=np.float32),
        np.array(y_train, dtype=np.int32),
        np.array(groups_train, dtype=np.int64),
        np.array(X_val, dtype=np.float32),
        np.array(y_val, dtype=np.int32),
        np.array(groups_val, dtype=np.int64),
    )
