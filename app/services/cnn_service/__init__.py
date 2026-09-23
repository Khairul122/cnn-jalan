"""
Package layanan CNN — dipecah dari 1 file (`cnn_service.py`, ~925 baris) jadi beberapa
modul per tanggung jawab (2026-09-23):

- `dataset.py`    — muat & perluas data training/validasi dari split K-Fold
- `model.py`      — arsitektur Keras (MobileNetV2/EfficientNetB0 + head klasifikasi)
- `training.py`   — loop training 2-fase, pemilihan checkpoint terbaik
- `evaluation.py` — evaluasi 1 model pada 1 fold (BUKAN metrik CV resmi)
- `prediction.py` — prediksi CV K-Fold, prediksi massal GIS, klasifikasi foto baru
                     (ensemble model fold + TTA)

Pemanggil lain (controller, tes) tetap `from app.services import cnn_service` lalu
`cnn_service.<nama>` — semua nama publik direekspor di sini, jadi tidak ada pemanggil
yang perlu diubah. Pengecualian: tes yang me-`mock.patch.object` konstanta/helper (mis.
`MIN_TRAIN_SAMPLES`, `_load_cached`) harus patch di modul TEMPAT nama itu didefinisikan
(`cnn_service.dataset.MIN_TRAIN_SAMPLES`, `cnn_service.prediction._load_cached`, dst) —
bukan di `cnn_service` langsung — karena Python me-resolve nama global di modul tempat
fungsi itu didefinisikan, bukan di tempat nama itu diimpor ulang.
"""
from . import dataset, model, training, evaluation, prediction

from .dataset import (
    TRAIN_EXPAND_STEPS,
    MIN_TRAIN_SAMPLES,
    MIN_VAL_SAMPLES,
    load_dataset,
    effective_sample_count,
    distinct_stage_paths,
    _group_aware_split,
    _preprocessed_subquery,
    _stage_map_for,
    _file_hash,
)
from .model import (
    N_CLASSES,
    build_model,
    _make_optimizer,
    _apply_fine_tuning,
)
from .training import (
    SEED,
    INNER_VAL_FRAC,
    MIN_DELTA,
    train,
    train_final,
    save_model,
    _fit_phase,
    _is_better_checkpoint,
    _get_logger,
)
from .evaluation import evaluate
from .prediction import (
    predict_cv,
    predict_all,
    predict_image,
    best_model,
    _load_cached,
    _predict_with_tta,
    _predict_probs_with,
    _ensemble_models_for,
    _resolve_prediction_models,
)

__all__ = [
    'dataset', 'model', 'training', 'evaluation', 'prediction',
    'TRAIN_EXPAND_STEPS', 'MIN_TRAIN_SAMPLES', 'MIN_VAL_SAMPLES', 'load_dataset',
    'effective_sample_count', 'distinct_stage_paths',
    'N_CLASSES', 'build_model',
    'SEED', 'INNER_VAL_FRAC', 'MIN_DELTA', 'train', 'train_final', 'save_model',
    'evaluate',
    'predict_cv', 'predict_all', 'predict_image', 'best_model',
]
