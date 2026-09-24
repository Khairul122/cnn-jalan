"""Loop training 2-fase (frozen base + fine-tune) dan pemilihan checkpoint terbaik."""
import os
import logging
from datetime import datetime
import numpy as np

from .dataset import load_dataset, _group_aware_split
from .model import build_model, _apply_fine_tuning, uses_onehot_labels, parse_aug_off, N_CLASSES

SEED = 42
INNER_VAL_FRAC = 0.15   # porsi data training untuk early stopping
MIN_DELTA = 0.001


def _get_logger(arsitektur_id, base_dir):
    """Buat file logger untuk satu sesi training. Tulis ke app/static/logs/."""
    log_dir = os.path.join(base_dir, 'app', 'static', 'logs')
    os.makedirs(log_dir, exist_ok=True)
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(log_dir, f'training_{arsitektur_id}_{ts}.log')

    logger = logging.getLogger(f'cnn_training_{arsitektur_id}_{ts}')
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()

    fh = logging.FileHandler(log_path, encoding='utf-8')
    fh.setFormatter(logging.Formatter('%(asctime)s  %(message)s', datefmt='%H:%M:%S'))
    logger.addHandler(fh)
    logger.propagate = False
    return logger, log_path


def _is_better_checkpoint(cand_acc, cand_loss, best_acc, best_loss):
    """
    Kriteria checkpoint terbaik (dipakai memilih epoch & memilih Phase 1 vs Phase 2).
    Utamakan cand_acc/best_acc — di _fit_phase ini diisi BALANCED accuracy inner-val
    (rata-rata recall antar kelas), bukan akurasi mentah yang bias ke kelas mayoritas
    (Sedang) — root-cause log training menunjukkan model bisa dapat akurasi mentah tinggi
    cuma dengan sering menebak Sedang, sambil recall Ringan anjlok. val_loss dipakai
    hanya sebagai tiebreaker saat cand_acc sama dengan best_acc.
    """
    if cand_acc != best_acc:
        return cand_acc > best_acc
    return cand_loss < best_loss


HYPERPARAM_FIELDS = (
    'input_size', 'model_type', 'dropout_rate', 'optimizer', 'learning_rate', 'batch_size', 'epochs', 'patience',
    'mixup_alpha', 'label_smoothing', 'dense_units', 'dense_l2', 'skip_fine_tuning', 'aug_off',
)


def hyperparams(arsitektur):
    """Hiperparameter training dari ArsitekturConfig (atau objek serupa) sebagai dict. Satu sumber untuk
    snapshot controller, predict_cv, dan train_final, supaya CV/model final tidak diam-diam memakai
    default untuk field yang lupa disalin (sebelumnya predict_cv mengabaikan mixup/label smoothing/dense/Jalur A)."""
    return {k: getattr(arsitektur, k) for k in HYPERPARAM_FIELDS}


def _mixup_dataset(X, y_int, sample_weight, batch_size, alpha, n_classes, seed):
    """
    tf.data pipeline Mixup (Zhang et al. 2017, TODO.md P3): campur pasangan gambar+label
    secara acak dengan rasio lambda ~ Beta(alpha, alpha) di level batch — BUKAN layer
    preprocessing Keras biasa, karena butuh mencampur DUA sampel (layer Keras cuma
    transform 1 sampel per panggilan). sample_weight (dari class_weight per label asli)
    ikut dicampur dengan lambda yang sama, supaya penanganan imbalance kelas tetap jalan
    meski label sudah jadi soft/campuran (class_weight kwarg biasa tidak berlaku lagi untuk
    label non-integer). Dipakai lewat generator numpy murni (bukan primitif tf.data acak)
    karena data sudah di memori dan throughput data BUKAN bottleneck di training CPU-only
    ini — model forward/backward yang mendominasi waktu.
    Return tf.data.Dataset tak berujung (caller WAJIB set steps_per_epoch) yang yield
    (x, y_onehot, sample_weight).
    """
    import tensorflow as tf

    y_onehot_all = np.eye(n_classes, dtype=np.float32)[y_int]
    sw_all = np.asarray(sample_weight, dtype=np.float32)
    n = len(X)

    def gen():
        rng = np.random.RandomState(seed)
        while True:
            idx1 = rng.permutation(n)
            idx2 = rng.permutation(n)
            for start in range(0, n - batch_size + 1, batch_size):
                i1, i2 = idx1[start:start + batch_size], idx2[start:start + batch_size]
                lam = rng.beta(alpha, alpha, size=batch_size).astype(np.float32)
                lam_x = lam.reshape(-1, 1, 1, 1)
                lam_y = lam.reshape(-1, 1)
                xb = lam_x * X[i1] + (1 - lam_x) * X[i2]
                yb = lam_y * y_onehot_all[i1] + (1 - lam_y) * y_onehot_all[i2]
                wb = lam * sw_all[i1] + (1 - lam) * sw_all[i2]
                yield xb.astype(np.float32), yb, wb

    sig = (
        tf.TensorSpec(shape=(batch_size, *X.shape[1:]), dtype=tf.float32),
        tf.TensorSpec(shape=(batch_size, n_classes), dtype=tf.float32),
        tf.TensorSpec(shape=(batch_size,), dtype=tf.float32),
    )
    return tf.data.Dataset.from_generator(gen, output_signature=sig).prefetch(tf.data.AUTOTUNE)


def _fit_phase(model, data, epochs, batch_size, class_weight, patience, lr_patience, min_lr,
               logger, offset, total_epochs, on_epoch_end, fine_tuning=False, mixup_alpha=0,
               label_smoothing=0):
    """
    Satu fase training. EarlyStopping & ReduceLROnPlateau memantau inner_val_loss (metrik
    stabil untuk kontrol training). Pemilihan BOBOT TERBAIK memakai kriteria
    _is_better_checkpoint dengan BALANCED accuracy inner-val (rata-rata recall antar kelas,
    bukan akurasi mentah yang bias ke kelas mayoritas/Sedang — lihat docstring
    _is_better_checkpoint), val_loss sbg tiebreaker. Fold uji dievaluasi tiap epoch untuk
    laporan/grafik saja, tidak pernah dipakai untuk memutuskan apa pun.
    Return (bobot_terbaik, inner_val_loss_terbaik, history, inner_val_balanced_acc_terbaik).
    """
    from tensorflow import keras
    from sklearn.metrics import balanced_accuracy_score

    X_fit, y_fit, X_inner, y_inner, X_fold, y_fold = data
    hist  = {'loss': [], 'accuracy': [], 'val_loss': [], 'val_accuracy': []}
    state = {'best_loss': float('inf'), 'best_acc': -1.0, 'weights': None,
             'lr': float(model.optimizer.learning_rate)}

    class _Track(keras.callbacks.Callback):
        def on_epoch_end(self, epoch, logs=None):
            lg = logs or {}
            inner_loss = lg.get('val_loss', float('inf'))

            if len(X_inner):
                inner_pred = np.argmax(self.model.predict(X_inner, verbose=0), axis=1)
                inner_bal_acc = float(balanced_accuracy_score(y_inner, inner_pred))
            else:
                inner_bal_acc = 0.0

            if _is_better_checkpoint(inner_bal_acc, inner_loss, state['best_acc'], state['best_loss']):
                state['best_acc']  = inner_bal_acc
                state['best_loss'] = inner_loss
                state['weights']   = self.model.get_weights()

            if len(X_fold):
                probs     = self.model.predict(X_fold, verbose=0)
                fold_acc  = float(np.mean(np.argmax(probs, axis=1) == y_fold))
                fold_loss = float(-np.mean(np.log(probs[np.arange(len(y_fold)), y_fold] + 1e-9)))
            else:   # model final: tidak ada fold uji, tampilkan inner-val
                fold_acc, fold_loss = inner_bal_acc, inner_loss

            lr = float(self.model.optimizer.learning_rate)
            note = f' ← LR turun dari {state["lr"]:.2e}' if lr < state['lr'] - 1e-10 else ''
            state['lr'] = lr
            logger.info(
                f'  {offset + epoch + 1:5d}  {lg.get("loss", 0):.4f}   {lg.get("accuracy", 0):.4f}   '
                f'{inner_loss:.4f}   {lg.get("val_accuracy", 0):.4f}   {inner_bal_acc:.4f}   '
                f'{fold_loss:.4f}   {fold_acc:.4f}   {lr:.2e}{note}'
            )
            for k, v in (('loss', lg.get('loss', 0)), ('accuracy', lg.get('accuracy', 0)),
                         ('val_loss', fold_loss), ('val_accuracy', fold_acc)):
                hist[k].append(float(v))
            if on_epoch_end:
                on_epoch_end(offset + epoch + 1, total_epochs, {
                    'loss': lg.get('loss', 0), 'accuracy': lg.get('accuracy', 0),
                    'val_loss': fold_loss, 'val_accuracy': fold_acc,
                    'fine_tuning': fine_tuning,
                })

    callbacks = [
        keras.callbacks.EarlyStopping(monitor='val_loss', patience=patience,
                                      min_delta=MIN_DELTA, mode='min', verbose=0),
        keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=lr_patience,
                                          min_lr=min_lr, verbose=0),
        _Track(),
    ]

    if mixup_alpha and mixup_alpha > 0:
        if len(X_fit) < batch_size:
            # Model sudah dikompilasi dengan loss one-hot; jatuh ke jalur label integer akan crash di fit().
            raise ValueError(f'Mixup butuh minimal satu batch penuh: data fit {len(X_fit)} < batch_size {batch_size}.')
        # Mixup aktif: model dikompilasi dgn CategoricalCrossentropy (lihat model.py::_make_loss)
        # -> validation_data juga wajib one-hot. class_weight kwarg TIDAK dipakai lagi di sini
        # karena sudah dibaurkan ke sample_weight per-batch di dalam dataset (lihat _mixup_dataset).
        sample_weight = np.array([class_weight.get(int(lbl), 1.0) for lbl in y_fit], dtype=np.float32)
        train_ds = _mixup_dataset(X_fit, y_fit, sample_weight, batch_size, mixup_alpha, N_CLASSES, SEED)
        steps_per_epoch = len(X_fit) // batch_size
        y_inner_onehot = np.eye(N_CLASSES, dtype=np.float32)[y_inner]
        model.fit(
            train_ds, steps_per_epoch=steps_per_epoch,
            validation_data=(X_inner, y_inner_onehot),
            epochs=epochs, verbose=0, callbacks=callbacks,
        )
    elif label_smoothing and label_smoothing > 0:
        # Label smoothing tanpa Mixup: model dikompilasi dgn CategoricalCrossentropy juga
        # (SparseCategoricalCrossentropy di Keras ini tidak punya param label_smoothing) —
        # cukup one-hot y_fit/y_inner biasa, TANPA campur-baur antar sampel (beda dari Mixup).
        # class_weight tetap dipakai lewat sample_weight array biasa (bukan generator).
        y_fit_onehot = np.eye(N_CLASSES, dtype=np.float32)[y_fit]
        y_inner_onehot = np.eye(N_CLASSES, dtype=np.float32)[y_inner]
        sample_weight = np.array([class_weight.get(int(lbl), 1.0) for lbl in y_fit], dtype=np.float32)
        model.fit(
            X_fit, y_fit_onehot, validation_data=(X_inner, y_inner_onehot),
            sample_weight=sample_weight,
            epochs=epochs, batch_size=batch_size, verbose=0, callbacks=callbacks,
        )
    else:
        model.fit(
            X_fit, y_fit, validation_data=(X_inner, y_inner),
            epochs=epochs, batch_size=batch_size, class_weight=class_weight, verbose=0,
            callbacks=callbacks,
        )
    if state['weights'] is None:
        state['weights'] = model.get_weights()
    return state['weights'], state['best_loss'], hist, state['best_acc']


def train(arsitektur, base_dir, on_epoch_end=None):
    import time
    from collections import Counter
    from tensorflow import keras
    from sklearn.utils.class_weight import compute_class_weight

    keras.utils.set_random_seed(SEED)

    _aid = getattr(arsitektur, 'id', None)
    arsitektur_id = _aid if _aid is not None else '?'
    logger, log_path = _get_logger(_aid if _aid is not None else 0, base_dir)
    t_start = time.time()

    is_cv = getattr(arsitektur, '_cv_fold', None)
    cv_label = f' [CV fold {is_cv}]' if is_cv is not None else ''
    if arsitektur.fold_val is None:
        cv_label = ' [MODEL FINAL, semua data]'
    logger.info('=' * 60)
    logger.info(f'TRAINING START — arsitektur_id={arsitektur_id}{cv_label}')
    for k in ('model_type', 'epochs', 'learning_rate', 'batch_size', 'dropout_rate', 'optimizer'):
        logger.info(f'  {k:13s}: {getattr(arsitektur, k)}')
    logger.info(f'  split_config : {arsitektur.split_config_id}  fold_val={arsitektur.fold_val}')
    logger.info('=' * 60)

    X_train, y_train, groups_train, X_fold, y_fold, _groups_fold = load_dataset(
        arsitektur.split_config_id, arsitektur.fold_val, arsitektur.input_size, base_dir)

    # Inner-val: potongan data training untuk early stopping. Fold uji tetap murni.
    # Split di level foto (groups_train), bukan level sampel — varian tahap preprocessing
    # dari foto yang sama tidak boleh terpisah antara fit dan inner-val (cegah leakage).
    idx_fit, idx_inner = _group_aware_split(
        groups_train, y_train, test_size=INNER_VAL_FRAC, seed=SEED)
    X_fit,   y_fit   = X_train[idx_fit],   y_train[idx_fit]
    X_inner, y_inner = X_train[idx_inner], y_train[idx_inner]

    from app.kelas import LABEL as label_name

    def dist(y):
        return '  '.join(f'{label_name[k]}={v}' for k, v in sorted(Counter(y.tolist()).items()))

    logger.info(f'DATASET: fit={len(X_fit)}  inner_val={len(X_inner)}  fold_uji={len(X_fold)}')
    logger.info(f'  Fit        : {dist(y_fit)}')
    logger.info(f'  Inner val  : {dist(y_inner)}')
    logger.info(f'  Fold uji   : {dist(y_fold)}')

    cw = compute_class_weight('balanced', classes=np.unique(y_fit), y=y_fit)
    class_weight = dict(enumerate(cw))
    logger.info('  class_weight: ' + '  '.join(f'{label_name[k]}={v:.3f}' for k, v in sorted(class_weight.items())))

    # Minimum patience=20: inner-val kecil (~34-40 foto unik) — EarlyStopping/ReduceLROnPlateau
    # tetap pantau val_loss (kontrol kapan berhenti/turunkan LR), tapi PEMILIHAN bobot
    # terbaik pakai inner_val BALANCED accuracy (lihat _is_better_checkpoint) karena akurasi
    # mentah/val_loss bisa membaik cuma dengan makin sering menebak Sedang (mayoritas).
    patience     = max(getattr(arsitektur, 'patience', 5), 20)
    ft_epochs    = max(20, arsitektur.epochs // 2)
    total_epochs = arsitektur.epochs + ft_epochs
    data = (X_fit, y_fit, X_inner, y_inner, X_fold, y_fold)
    head = '  Epoch  loss     acc      in_loss  in_acc   in_bal   uji_loss uji_acc  lr'
    mixup_alpha = getattr(arsitektur, 'mixup_alpha', 0) or 0
    label_smoothing = getattr(arsitektur, 'label_smoothing', 0) or 0
    dense_units = getattr(arsitektur, 'dense_units', None) or 64
    dense_l2 = getattr(arsitektur, 'dense_l2', None) or 1e-4
    skip_fine_tuning = bool(getattr(arsitektur, 'skip_fine_tuning', False))
    aug_off = parse_aug_off(getattr(arsitektur, 'aug_off', '') or '')
    if aug_off:
        logger.info(f'  augmentasi dimatikan : {", ".join(aug_off)}')
    if mixup_alpha:
        logger.info(f'  mixup_alpha  : {mixup_alpha} (Mixup aktif — loss CategoricalCrossentropy, class_weight via sample_weight)')
    if label_smoothing:
        logger.info(f'  label_smoothing : {label_smoothing}')
    if skip_fine_tuning:
        logger.info('  skip_fine_tuning : True (Jalur A — backbone beku penuh, Phase 2 dilewati, TODO.md P4)')
    if dense_units != 64 or dense_l2 != 1e-4:
        logger.info(f'  dense_units={dense_units}  dense_l2={dense_l2} (default 64/1e-4, TODO.md P4)')

    # ── Phase 1: base frozen ──────────────────────────────────────────
    model = build_model(arsitektur.model_type, arsitektur.input_size,
                        arsitektur.dropout_rate, arsitektur.optimizer, arsitektur.learning_rate,
                        mixup_alpha=mixup_alpha, label_smoothing=label_smoothing,
                        dense_units=dense_units, dense_l2=dense_l2, aug_off=aug_off)
    logger.info(f'PHASE 1  epochs_max={arsitektur.epochs}  patience={patience}')
    logger.info('  [Early stopping/LR: inner_val_loss | Pilihan epoch: inner_val_balanced_acc (loss tiebreaker) | uji_* hanya laporan]')
    logger.info(head)
    p1_weights, p1_loss, h1, p1_bal = _fit_phase(
        model, data, arsitektur.epochs, arsitektur.batch_size, class_weight,
        patience, patience // 2, 1e-6, logger, 0, total_epochs, on_epoch_end,
        mixup_alpha=mixup_alpha, label_smoothing=label_smoothing)
    logger.info(f'PHASE 1 SELESAI  epoch={len(h1["loss"])}  best_inner_val_bal_acc={p1_bal:.4f}  (loss={p1_loss:.4f})')

    if skip_fine_tuning:
        # Jalur A (TODO.md P4): backbone beku penuh, tidak ada Phase 2 sama sekali.
        model.set_weights(p1_weights)
        history_dict = h1
        logger.info('PHASE 2 DILEWATI (skip_fine_tuning=True) — pakai bobot Phase 1 apa adanya')
    else:
        # ── Phase 2: fine-tune layer teratas ──────────────────────────
        total_epochs = len(h1['loss']) + ft_epochs   # fase 1 bisa berhenti lebih awal → progress tetap mencapai 100%
        model.set_weights(p1_weights)
        model = _apply_fine_tuning(model, arsitektur.model_type, arsitektur.learning_rate,
                                   arsitektur.optimizer, mixup_alpha=mixup_alpha,
                                   label_smoothing=label_smoothing)
        logger.info(f'PHASE 2 (fine-tune)  epochs_max={ft_epochs}  lr={arsitektur.learning_rate / 10:.2e}')
        logger.info(head)
        p2_weights, p2_loss, h2, p2_bal = _fit_phase(
            model, data, ft_epochs, arsitektur.batch_size, class_weight,
            max(10, patience // 2), max(5, patience // 4), 1e-7,
            logger, len(h1['loss']), total_epochs, on_epoch_end, fine_tuning=True,
            mixup_alpha=mixup_alpha, label_smoothing=label_smoothing)

        if _is_better_checkpoint(p2_bal, p2_loss, p1_bal, p1_loss):
            model.set_weights(p2_weights)
            pilihan = 'Phase 2 (inner_val_balanced_acc lebih baik)'
        else:
            model.set_weights(p1_weights)
            pilihan = 'Phase 1 (fine-tuning tidak memperbaiki inner_val_balanced_acc)'
        logger.info(f'PHASE 2 SELESAI  epoch={len(h2["loss"])}  best_inner_val_bal_acc={p2_bal:.4f}  (loss={p2_loss:.4f})  → pakai {pilihan}')

        history_dict = {k: h1[k] + h2[k] for k in h1}
    logger.info(f'TRAINING SELESAI  total_epoch={len(history_dict["loss"])}  waktu={(time.time() - t_start) / 60:.1f} menit')
    logger.info('=' * 60)
    for handler in logger.handlers:
        handler.close()

    return model, history_dict


def train_final(arsitektur, base_dir, on_epoch_end=None):
    """
    Latih model final pada SELURUH data (tanpa fold uji) dengan hiperparameter yang sama.
    Early stopping tetap memakai inner-val. Akurasi yang dilaporkan tetap dari K-Fold CV,
    bukan dari model ini (tidak ada data uji yang tersisa).
    """
    from types import SimpleNamespace

    cfg = SimpleNamespace(id=arsitektur.id, split_config_id=arsitektur.split_config_id, fold_val=None,
                          **hyperparams(arsitektur))
    model, _ = train(cfg, base_dir, on_epoch_end=on_epoch_end)
    return model


def save_model(model, arsitektur_id, base_dir, suffix=''):
    folder = os.path.join(base_dir, 'app', 'static', 'models')
    os.makedirs(folder, exist_ok=True)
    filename = f'model_{arsitektur_id}{suffix}.keras'
    model.save(os.path.join(folder, filename))
    return f'models/{filename}'
