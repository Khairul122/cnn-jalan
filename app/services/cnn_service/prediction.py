"""Prediksi CV K-Fold, prediksi massal GIS, dan klasifikasi 1 foto baru (ensemble + TTA)."""
import os
import numpy as np
from PIL import Image

from app import db
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.label_kerusakan import LabelKerusakan

from .dataset import _preprocessed_subquery
from .training import train, save_model

_model_cache = {}   # path → (mtime, model)


def predict_cv(arsitektur, base_dir, on_progress=None):
    """
    K-Fold cross-validation prediction.
    Each photo's fold is predicted by a model trained on all OTHER folds.
    on_progress(fold_done, n_folds, epoch, total_epochs) — called each epoch + at fold completion.
    Returns list of {dokumentasi_id, prediksi, aktual, confidence}.
    """
    import gc
    from collections import defaultdict
    from types import SimpleNamespace
    from app.models.split_config import SplitConfig
    from app.models.split_item import SplitItem

    split_cfg = db.session.get(SplitConfig, arsitektur.split_config_id)
    n_splits  = split_cfg.n_splits

    prep_sq = _preprocessed_subquery()

    # Pre-fetch all split items (fold, dok_id, label, path) — release DB before training loop
    rows = (
        db.session.query(
            SplitItem.fold_index,
            SplitItem.dokumentasi_id,
            SplitItem.tingkat_kerusakan_id,
            DokumentasiFoto.path_file,
            prep_sq.c.prep_path,
        )
        .join(DokumentasiFoto, SplitItem.dokumentasi_id == DokumentasiFoto.id)
        .outerjoin(prep_sq, prep_sq.c.dokumentasi_id == SplitItem.dokumentasi_id)
        .filter(SplitItem.config_id == arsitektur.split_config_id)
        .all()
    )
    db.session.remove()

    fold_items = defaultdict(list)
    for r in rows:
        fold_items[r.fold_index].append(r)

    cfg_base = dict(
        split_config_id = arsitektur.split_config_id,
        input_size      = arsitektur.input_size,
        model_type      = arsitektur.model_type,
        dropout_rate    = arsitektur.dropout_rate,
        optimizer       = arsitektur.optimizer,
        learning_rate   = arsitektur.learning_rate,
        batch_size      = arsitektur.batch_size,
        epochs          = arsitektur.epochs,
        patience        = getattr(arsitektur, 'patience', 5),
    )

    results = []

    for fold_k in range(n_splits):
        cfg_obj = SimpleNamespace()
        for k, v in cfg_base.items():
            setattr(cfg_obj, k, v)
        cfg_obj.fold_val  = fold_k
        cfg_obj.id        = getattr(arsitektur, 'id', 0)  # agar arsitektur_id tercatat di log
        cfg_obj._cv_fold  = fold_k                         # label "[CV fold k]" di header log

        # Epoch-level progress callback for this fold
        def make_epoch_cb(fk):
            def cb(epoch, total, logs):
                if on_progress:
                    on_progress(fk, n_splits, epoch, total)
            return cb

        model, _ = train(cfg_obj, base_dir, on_epoch_end=make_epoch_cb(fold_k))

        # Simpan model tiap fold — dipakai sebagai ensemble saat klasifikasi foto baru
        # (lihat _ensemble_models_for/_predict_probs), bukan cuma dibuang setelah dipakai
        # prediksi fold ini saja.
        arsitektur_id = getattr(arsitektur, 'id', None)
        if arsitektur_id is not None:
            save_model(model, arsitektur_id, base_dir, suffix=f'_fold{fold_k}')

        for item in fold_items[fold_k]:
            # Utamakan denoise preprocessed agar konsisten dengan training, fallback ke original
            path_rel = item.prep_path if item.prep_path else item.path_file
            img_path = os.path.join(base_dir, 'app', 'static', path_rel)
            if not os.path.isfile(img_path):
                continue
            try:
                img = Image.open(img_path).convert('RGB').resize((cfg_base['input_size'], cfg_base['input_size']))
                arr = np.array(img, dtype=np.float32)
                probs = _predict_with_tta(model, arr)
                pred  = int(np.argmax(probs))
                conf  = float(np.max(probs))
                aktual = int(item.tingkat_kerusakan_id) - 1
            except Exception:
                continue
            results.append({
                'dokumentasi_id': item.dokumentasi_id,
                'prediksi':       pred,
                'aktual':         aktual,
                'confidence':     round(conf * 100, 2),
            })

        # Free memory before next fold
        del model
        try:
            import tensorflow as tf
            tf.keras.backend.clear_session()
        except Exception:
            pass
        gc.collect()

        if on_progress:
            on_progress(fold_k + 1, n_splits, 0, 0)

    return results


def predict_all(arsitektur, base_dir):
    """Jalankan inferensi pada semua foto yang punya koordinat + label. Pakai ensemble model
    fold CV + TTA kalau tersedia (lihat _resolve_prediction_models), fallback model tunggal."""
    models = _resolve_prediction_models(arsitektur, base_dir)

    prep_sq = _preprocessed_subquery()

    rows = (
        db.session.query(
            DokumentasiFoto.id,
            DokumentasiFoto.path_file,
            LabelKerusakan.tingkat_kerusakan_id,
            prep_sq.c.prep_path,
        )
        .join(LokasiKerusakan, DokumentasiFoto.lokasi_id == LokasiKerusakan.id)
        .join(LabelKerusakan, LabelKerusakan.lokasi_id == LokasiKerusakan.id)
        .outerjoin(prep_sq, prep_sq.c.dokumentasi_id == DokumentasiFoto.id)
        .filter(LokasiKerusakan.latitude != None)
        .all()
    )
    db.session.remove()

    input_size = arsitektur.input_size
    results = []
    for row in rows:
        # Utamakan denoise preprocessed agar konsisten dengan training, fallback ke original
        path_rel = row.prep_path if row.prep_path else row.path_file
        img_path = os.path.join(base_dir, 'app', 'static', path_rel)
        if not os.path.isfile(img_path):
            continue
        try:
            img = Image.open(img_path).convert('RGB').resize((input_size, input_size))
            arr = np.array(img, dtype=np.float32)
            probs = _predict_probs_with(models, arr)
            pred = int(np.argmax(probs))
            conf = float(np.max(probs))
            aktual = int(row.tingkat_kerusakan_id) - 1  # 0=Berat,1=Sedang,2=Ringan
        except Exception:
            continue

        results.append({
            'dokumentasi_id': row.id,
            'prediksi':       pred,
            'aktual':         aktual,
            'confidence':     round(conf * 100, 2),
        })

    return results


def _load_cached(model_file):
    from tensorflow import keras
    mtime = os.path.getmtime(model_file)
    hit = _model_cache.get(model_file)
    if hit and hit[0] == mtime:
        return hit[1]
    model = keras.models.load_model(model_file, compile=False)
    _model_cache[model_file] = (mtime, model)
    return model


def best_model():
    """
    ArsitekturConfig terbaik untuk klasifikasi foto baru. Utamakan config yang sudah punya
    hasil CV K-Fold (pred_type='cv', metrik resmi rata-rata 5 fold) dengan macro-F1 CV
    tertinggi. Fallback ke HasilEvaluasi.macro_f1 (1 fold, kurang bisa dipercaya) kalau
    belum ada satu pun config yang di-CV — konsisten dengan catatan di CLAUDE.md soal
    HasilEvaluasi bukan metrik resmi.
    """
    from app.models.arsitektur_config import ArsitekturConfig
    from app.models.hasil_evaluasi import HasilEvaluasi
    from app.services.metrics_service import cv_summary

    cv_scored = []
    for cfg in ArsitekturConfig.query.filter(
        ArsitekturConfig.status == 'selesai',
        ArsitekturConfig.model_path.isnot(None),
        ArsitekturConfig.pred_type == 'cv',
    ).all():
        summary = cv_summary(cfg)
        if summary:
            cv_scored.append((summary['macro_f1'], cfg))
    if cv_scored:
        cv_scored.sort(key=lambda t: t[0], reverse=True)
        return cv_scored[0][1]

    return (
        ArsitekturConfig.query
        .join(HasilEvaluasi, HasilEvaluasi.arsitektur_id == ArsitekturConfig.id)
        .filter(ArsitekturConfig.status == 'selesai', ArsitekturConfig.model_path.isnot(None))
        .order_by(HasilEvaluasi.macro_f1.desc())
        .first()
    )


def _five_crop_flip_views(img_arr, crop_frac=0.875):
    """
    5-crop (tengah + 4 sudut) di crop_frac dari ukuran asli, di-resize balik ke ukuran asli,
    masing-masing digandakan dengan flip horizontal → 10 view. Teknik TTA standar (mis.
    torchvision FiveCrop) diperluas dengan flip, dipakai _predict_with_tta.
    """
    h, w = img_arr.shape[:2]
    ch, cw = max(1, int(h * crop_frac)), max(1, int(w * crop_frac))
    positions = [
        ((h - ch) // 2, (w - cw) // 2),   # tengah
        (0, 0),                            # kiri atas
        (0, w - cw),                       # kanan atas
        (h - ch, 0),                       # kiri bawah
        (h - ch, w - cw),                  # kanan bawah
    ]
    views = []
    for top, left in positions:
        crop = img_arr[top:top + ch, left:left + cw]
        resized = Image.fromarray(crop.astype(np.uint8)).resize((w, h), Image.Resampling.BILINEAR)
        resized = np.array(resized, dtype=np.float32)
        views.append(resized)
        views.append(resized[:, ::-1, :])
    return views


def _predict_with_tta(model, img_arr):
    """
    Rata-ratakan probabilitas prediksi dari 5-crop (tengah + 4 sudut) × flip horizontal =
    10 view (diperluas dari flip-only, TODO.md P3). Flip horizontal representatif untuk foto
    jalan (perspektif kendaraan simetris kiri-kanan), sama seperti augmentasi
    RandomFlip('horizontal') yang dipakai saat training.
    img_arr: array [H, W, 3] float32 [0,255], belum di-batch. Return: vektor probabilitas [3].
    """
    batch = np.stack(_five_crop_flip_views(img_arr))
    probs = model.predict(batch, verbose=0)
    return probs.mean(axis=0)


def _ensemble_models_for(arsitektur, base_dir):
    """
    Model tiap fold CV untuk arsitektur ini (disimpan predict_cv sejak 2026-09-23), urut
    fold 0..N-1. List kosong kalau CV belum pernah dijalankan sejak fold-model disimpan —
    caller lalu fallback ke model tunggal.
    """
    folder = os.path.join(base_dir, 'app', 'static', 'models')
    arsitektur_id = getattr(arsitektur, 'id', None)
    models, k = [], 0
    while arsitektur_id is not None:
        path = os.path.join(folder, f'model_{arsitektur_id}_fold{k}.keras')
        if not os.path.isfile(path):
            break
        models.append(_load_cached(path))
        k += 1
    return models


def _resolve_prediction_models(arsitektur, base_dir):
    """
    Model-model yang dipakai untuk memprediksi arsitektur ini: seluruh model fold CV kalau
    sudah tersimpan (ensemble, lebih stabil — rata-rata 5 model yang masing-masing dilatih
    dari data berbeda), atau 1 model tunggal (final kalau ada, else model fold biasa) kalau
    belum. Panggil SEKALI per sesi prediksi (bukan per-foto) — caller lain (predict_all)
    memprediksi banyak foto sekaligus dengan model yang sama.
    """
    fold_models = _ensemble_models_for(arsitektur, base_dir)
    if fold_models:
        return fold_models
    rel_path = getattr(arsitektur, 'final_model_path', None) or arsitektur.model_path
    return [_load_cached(os.path.join(base_dir, 'app', 'static', rel_path))]


def _predict_probs_with(models, img_arr):
    """Rata-ratakan probabilitas TTA (flip horizontal) dari 1 atau beberapa model (ensemble)."""
    return np.mean([_predict_with_tta(m, img_arr) for m in models], axis=0)


def predict_image(arsitektur, img_path, base_dir, prep_config=None):
    """
    Prediksi satu foto → (kelas 0..2, confidence 0..1). Pakai ensemble model fold CV + TTA
    kalau tersedia (lihat _resolve_prediction_models), fallback ke model tunggal + TTA.
    Bila prep_config diberikan, foto diproses dengan pipeline yang sama seperti data training
    (hasil tahap denoise); jika tidak, hanya di-resize.
    """
    from app.services.preprocessing_service import PreprocessingService

    if prep_config is not None:
        steps = dict((k, im) for k, im, _ in PreprocessingService.run_pipeline_steps(img_path, prep_config))
        img = steps['denoise']
    else:
        img = Image.open(img_path)
    img = img.convert('RGB').resize((arsitektur.input_size, arsitektur.input_size))
    models = _resolve_prediction_models(arsitektur, base_dir)
    probs = _predict_probs_with(models, np.array(img, dtype=np.float32))
    return int(np.argmax(probs)), float(np.max(probs))
