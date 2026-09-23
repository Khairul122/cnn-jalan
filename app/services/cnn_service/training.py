"""Loop training 2-fase (frozen base + fine-tune) dan pemilihan checkpoint terbaik."""
import os
import logging
from datetime import datetime
import numpy as np

from .dataset import load_dataset, _group_aware_split
from .model import build_model, _apply_fine_tuning

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


def _fit_phase(model, data, epochs, batch_size, class_weight, patience, lr_patience, min_lr,
               logger, offset, total_epochs, on_epoch_end, fine_tuning=False):
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

    model.fit(
        X_fit, y_fit, validation_data=(X_inner, y_inner),
        epochs=epochs, batch_size=batch_size, class_weight=class_weight, verbose=0,
        callbacks=[
            keras.callbacks.EarlyStopping(monitor='val_loss', patience=patience,
                                          min_delta=MIN_DELTA, mode='min', verbose=0),
            keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5, patience=lr_patience,
                                              min_lr=min_lr, verbose=0),
            _Track(),
        ],
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

    label_name = {0: 'Berat', 1: 'Sedang', 2: 'Ringan'}

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

    # ── Phase 1: base frozen ──────────────────────────────────────────
    model = build_model(arsitektur.model_type, arsitektur.input_size,
                        arsitektur.dropout_rate, arsitektur.optimizer, arsitektur.learning_rate)
    logger.info(f'PHASE 1  epochs_max={arsitektur.epochs}  patience={patience}')
    logger.info('  [Early stopping/LR: inner_val_loss | Pilihan epoch: inner_val_balanced_acc (loss tiebreaker) | uji_* hanya laporan]')
    logger.info(head)
    p1_weights, p1_loss, h1, p1_bal = _fit_phase(
        model, data, arsitektur.epochs, arsitektur.batch_size, class_weight,
        patience, patience // 2, 1e-6, logger, 0, total_epochs, on_epoch_end)
    logger.info(f'PHASE 1 SELESAI  epoch={len(h1["loss"])}  best_inner_val_bal_acc={p1_bal:.4f}  (loss={p1_loss:.4f})')

    # ── Phase 2: fine-tune layer teratas ──────────────────────────────
    total_epochs = len(h1['loss']) + ft_epochs   # fase 1 bisa berhenti lebih awal → progress tetap mencapai 100%
    model.set_weights(p1_weights)
    model = _apply_fine_tuning(model, arsitektur.model_type,
                               arsitektur.learning_rate, arsitektur.optimizer)
    logger.info(f'PHASE 2 (fine-tune)  epochs_max={ft_epochs}  lr={arsitektur.learning_rate / 10:.2e}')
    logger.info(head)
    p2_weights, p2_loss, h2, p2_bal = _fit_phase(
        model, data, ft_epochs, arsitektur.batch_size, class_weight,
        max(10, patience // 2), max(5, patience // 4), 1e-7,
        logger, len(h1['loss']), total_epochs, on_epoch_end, fine_tuning=True)

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

    cfg = SimpleNamespace(
        id=arsitektur.id, split_config_id=arsitektur.split_config_id, fold_val=None,
        input_size=arsitektur.input_size, model_type=arsitektur.model_type,
        dropout_rate=arsitektur.dropout_rate, optimizer=arsitektur.optimizer,
        learning_rate=arsitektur.learning_rate, batch_size=arsitektur.batch_size,
        epochs=arsitektur.epochs, patience=getattr(arsitektur, 'patience', 5),
    )
    model, _ = train(cfg, base_dir, on_epoch_end=on_epoch_end)
    return model


def save_model(model, arsitektur_id, base_dir, suffix=''):
    folder = os.path.join(base_dir, 'app', 'static', 'models')
    os.makedirs(folder, exist_ok=True)
    filename = f'model_{arsitektur_id}{suffix}.keras'
    model.save(os.path.join(folder, filename))
    return f'models/{filename}'
