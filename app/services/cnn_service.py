import os
import logging
import numpy as np
from datetime import datetime
from PIL import Image

from sqlalchemy import func
from app import db
from app.models.split_item import SplitItem
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.label_kerusakan import LabelKerusakan
from app.models.hasil_preprocessing import HasilPreprocessing


N_CLASSES = 3  # Berat=0, Sedang=1, Ringan=2


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


def _make_optimizer(optimizer_name, learning_rate):
    from tensorflow import keras
    if optimizer_name == 'adam':
        return keras.optimizers.Adam(learning_rate=learning_rate)
    elif optimizer_name == 'sgd':
        return keras.optimizers.SGD(learning_rate=learning_rate, momentum=0.9)
    return keras.optimizers.RMSprop(learning_rate=learning_rate)


def build_model(model_type, input_size, dropout_rate, optimizer_name, learning_rate):
    from tensorflow import keras

    inp = keras.Input(shape=(input_size, input_size, 3))

    # Augmentasi — aktif hanya saat training=True, mati saat predict/evaluate
    # Hanya augmentasi yang realistis untuk foto jalan (perspektif kendaraan horizontal):
    # - Flip vertikal DIHAPUS: menghasilkan gambar tidak realistis (jalan terbalik)
    # - Rotation dikurangi ke ±18° (kemiringan kendaraan wajar, bukan 90°)
    x = keras.layers.RandomFlip('horizontal')(inp)
    x = keras.layers.RandomRotation(0.05)(x)
    x = keras.layers.RandomZoom(0.2)(x)
    x = keras.layers.RandomTranslation(0.1, 0.1)(x)
    x = keras.layers.RandomBrightness(0.3)(x)
    x = keras.layers.RandomContrast(0.3)(x)

    if model_type == 'mobilenetv2':
        x = keras.applications.mobilenet_v2.preprocess_input(x)
        base = keras.applications.MobileNetV2(
            input_shape=(input_size, input_size, 3),
            include_top=False, weights='imagenet',
        )
    else:
        x = keras.applications.efficientnet.preprocess_input(x)
        base = keras.applications.EfficientNetB0(
            input_shape=(input_size, input_size, 3),
            include_top=False, weights='imagenet',
        )

    base.trainable = False
    x = base(x, training=False)
    x = keras.layers.GlobalAveragePooling2D()(x)
    x = keras.layers.Dropout(dropout_rate)(x)
    # Dense intermediate + L2 untuk dataset kecil (mencegah overfitting)
    # Dense(64) cukup untuk 3-class dengan 224 training samples — Dense(128) terlalu besar
    x = keras.layers.Dense(64, activation='relu',
                           kernel_regularizer=keras.regularizers.L2(1e-4))(x)
    x = keras.layers.Dropout(dropout_rate / 2)(x)
    out = keras.layers.Dense(N_CLASSES, activation='softmax',
                             kernel_regularizer=keras.regularizers.L2(1e-4))(x)

    model = keras.Model(inp, out)
    model.compile(
        optimizer=_make_optimizer(optimizer_name, learning_rate),
        loss=keras.losses.SparseCategoricalCrossentropy(),
        metrics=['accuracy'],
    )
    return model


def _apply_fine_tuning(model, model_type, learning_rate, optimizer_name):
    """Unfreeze top layers of the base sub-model and recompile with lr/5."""
    from tensorflow import keras
    # Dataset kecil (~224 train): unfreeze sedikit layer saja untuk hindari overfitting
    # MobileNetV2 ~154 layers → unfreeze last 15
    # EfficientNetB0 ~238 layers → unfreeze last 25
    n_unfreeze = 15 if model_type == 'mobilenetv2' else 25

    base = None
    for layer in model.layers:
        if hasattr(layer, 'layers') and len(layer.layers) > 10:
            base = layer
            break
    if base is None:
        return model

    base.trainable = True
    fine_tune_from = max(0, len(base.layers) - n_unfreeze)
    for i, layer in enumerate(base.layers):
        # Keep BatchNorm layers frozen to preserve ImageNet statistics
        if layer.__class__.__name__ == 'BatchNormalization':
            layer.trainable = False
        else:
            layer.trainable = (i >= fine_tune_from)

    model.compile(
        optimizer=_make_optimizer(optimizer_name, learning_rate / 5),
        loss=keras.losses.SparseCategoricalCrossentropy(),
        metrics=['accuracy'],
    )
    return model


def load_dataset(split_config_id, fold_val, input_size, base_dir):
    # Subquery: path_output terbaru (step=denoise) per dokumentasi_id
    # path_output diawali timestamp sehingga MAX() = yang paling baru
    prep_sq = (
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

    rows = (
        db.session.query(
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
    # Release DB connection back to pool before the slow image-loading loop
    db.session.remove()

    X_train, y_train, X_val, y_val = [], [], [], []
    skipped = 0
    prep_used = 0

    for row in rows:
        is_val = (row.fold_index == fold_val)

        # Train dan val sama-sama utamakan denoise preprocessed agar distribusi konsisten.
        # Fallback ke original jika foto belum dipreprocessing.
        if row.prep_path:
            path_rel = row.prep_path
            prep_used += 1
        else:
            path_rel = row.path_file

        img_path = os.path.join(base_dir, 'app', 'static', path_rel)
        if not os.path.isfile(img_path):
            skipped += 1
            continue
        try:
            img = Image.open(img_path).convert('RGB').resize((input_size, input_size))
            arr = np.array(img, dtype=np.float32)  # [0,255] — preprocess_input ada di dalam model
        except Exception:
            skipped += 1
            continue

        label = int(row.tingkat_kerusakan_id) - 1

        if is_val:
            X_val.append(arr)
            y_val.append(label)
        else:
            X_train.append(arr)
            y_train.append(label)

    if prep_used > 0 or skipped > 0:
        print(f'[load_dataset] train={len(X_train)} val={len(X_val)} '
              f'({prep_used} preprocessed, {len(X_train)+len(X_val)-prep_used} original), skip={skipped}')


    if len(X_train) < 20:
        raise ValueError(
            f'Dataset training terlalu kecil ({len(X_train)} gambar). '
            f'Periksa path file — {skipped} gambar gagal dimuat.'
        )
    if len(X_val) < 5:
        raise ValueError(
            f'Dataset validasi terlalu kecil ({len(X_val)} gambar). '
            f'Periksa fold_val={fold_val} dan path file.'
        )

    return (
        np.array(X_train, dtype=np.float32),
        np.array(y_train, dtype=np.int32),
        np.array(X_val, dtype=np.float32),
        np.array(y_val, dtype=np.int32),
    )


def train(arsitektur, base_dir, on_epoch_end=None):
    import tempfile
    import time
    from tensorflow import keras

    _aid = getattr(arsitektur, 'id', None)
    arsitektur_id = _aid if _aid is not None else '?'
    logger, log_path = _get_logger(_aid if _aid is not None else 0, base_dir)
    t_start = time.time()

    is_cv = getattr(arsitektur, '_cv_fold', None)
    cv_label = f' [CV fold {is_cv}]' if is_cv is not None else ''
    logger.info('=' * 60)
    logger.info(f'TRAINING START — arsitektur_id={arsitektur_id}{cv_label}')
    logger.info(f'  model_type   : {arsitektur.model_type}')
    logger.info(f'  epochs       : {arsitektur.epochs}')
    logger.info(f'  learning_rate: {arsitektur.learning_rate}')
    logger.info(f'  batch_size   : {arsitektur.batch_size}')
    logger.info(f'  dropout_rate : {arsitektur.dropout_rate}')
    logger.info(f'  optimizer    : {arsitektur.optimizer}')
    logger.info(f'  split_config : {arsitektur.split_config_id}  fold_val={arsitektur.fold_val}')
    logger.info('=' * 60)

    X_train, y_train, X_val, y_val = load_dataset(
        arsitektur.split_config_id,
        arsitektur.fold_val,
        arsitektur.input_size,
        base_dir,
    )

    if len(X_train) == 0:
        raise ValueError('Tidak ada data training yang berhasil dimuat.')
    if len(X_val) == 0:
        raise ValueError('Tidak ada data validasi yang berhasil dimuat.')

    # Log distribusi kelas
    from collections import Counter
    train_dist = Counter(y_train.tolist())
    val_dist   = Counter(y_val.tolist())
    label_name = {0: 'Berat', 1: 'Sedang', 2: 'Ringan'}
    logger.info(f'DATASET: train={len(X_train)}  val={len(X_val)}')
    logger.info('  Train distribusi: ' + '  '.join(f'{label_name[k]}={v}' for k, v in sorted(train_dist.items())))
    logger.info('  Val   distribusi: ' + '  '.join(f'{label_name[k]}={v}' for k, v in sorted(val_dist.items())))

    from sklearn.utils.class_weight import compute_class_weight
    cw = compute_class_weight('balanced', classes=np.unique(y_train), y=y_train)
    class_weight = dict(enumerate(cw))
    logger.info('  class_weight: ' + '  '.join(f'{label_name[k]}={v:.3f}' for k, v in sorted(class_weight.items())))

    # Minimum patience=20 untuk dataset kecil — val_accuracy dari ~56 sampel sangat noisy (1 sample = ~1.8%)
    patience   = max(getattr(arsitektur, 'patience', 5), 20)
    ft_epochs  = max(20, arsitektur.epochs // 2)   # fine-tune epochs ≈ 1/2 of main epochs
    total_epochs = arsitektur.epochs + ft_epochs

    # ── Phase 1: frozen base ─────────────────────────────────────────
    model    = build_model(arsitektur.model_type, arsitektur.input_size,
                           arsitektur.dropout_rate, arsitektur.optimizer,
                           arsitektur.learning_rate)
    tmp1     = os.path.join(tempfile.gettempdir(), f'best_p1_{id(model)}.keras')

    logger.info(f'PHASE 1  epochs_max={arsitektur.epochs}  patience={patience}')
    logger.info('  [Checkpoint: val_accuracy (simpan model terbaik)  |  EarlyStopping & LR: val_loss (lebih stabil)]')
    logger.info('  Epoch  loss      acc       val_loss  val_acc   lr')

    cbs1 = [
        # Checkpoint monitor val_accuracy agar model tersimpan = epoch dengan val_accuracy tertinggi.
        # EarlyStopping & ReduceLROnPlateau tetap monitor val_loss (lebih stabil/kontinyu).
        keras.callbacks.ModelCheckpoint(tmp1, monitor='val_accuracy', save_best_only=True,
                                        mode='max', verbose=0),
        keras.callbacks.EarlyStopping(monitor='val_loss', patience=patience,
                                      min_delta=0.001, mode='min',
                                      restore_best_weights=False, verbose=0),
        keras.callbacks.ReduceLROnPlateau(monitor='val_loss', factor=0.5,
                                          patience=patience // 2, min_lr=1e-6, verbose=0),
    ]

    _prev_lr1 = [float(arsitektur.learning_rate)]

    class _LogCb1(keras.callbacks.Callback):
        def on_epoch_end(self, epoch, logs=None):
            lg = logs or {}
            current_lr = float(self.model.optimizer.learning_rate)
            lr_note = ''
            if current_lr < _prev_lr1[0] - 1e-10:
                lr_note = f' ← LR turun dari {_prev_lr1[0]:.2e}'
                _prev_lr1[0] = current_lr
            logger.info(
                f'  {epoch+1:5d}  {lg.get("loss",0):.4f}    {lg.get("accuracy",0):.4f}    '
                f'{lg.get("val_loss",0):.4f}    {lg.get("val_accuracy",0):.4f}   '
                f'{current_lr:.2e}{lr_note}'
            )
            if on_epoch_end:
                on_epoch_end(epoch + 1, total_epochs, lg)
    cbs1.append(_LogCb1())

    h1 = model.fit(X_train, y_train, validation_data=(X_val, y_val),
                   epochs=arsitektur.epochs, batch_size=arsitektur.batch_size,
                   class_weight=class_weight, verbose=0, callbacks=cbs1)

    p1_best_val_acc = max(h1.history.get('val_accuracy', [0]))
    p1_best_val_loss = min(h1.history.get('val_loss', [999]))
    logger.info(
        f'PHASE 1 SELESAI  epoch={len(h1.history["loss"])}  '
        f'best_val_loss={p1_best_val_loss:.4f}  best_val_acc={p1_best_val_acc:.4f}'
    )

    if os.path.exists(tmp1):
        model = keras.models.load_model(tmp1, compile=False)
        model.compile(
            optimizer=_make_optimizer(arsitektur.optimizer, arsitektur.learning_rate),
            loss=keras.losses.SparseCategoricalCrossentropy(),
            metrics=['accuracy'],
        )
        os.remove(tmp1)

    # Simpan model Phase 1 terbaik sebagai fallback sebelum fine-tuning mengubahnya
    tmp1_fallback = os.path.join(tempfile.gettempdir(), f'fallback_p1_{id(model)}.keras')
    model.save(tmp1_fallback)

    p1_len = len(h1.history['loss'])

    # ── Phase 2: fine-tune top layers ────────────────────────────────
    model = _apply_fine_tuning(model, arsitektur.model_type,
                               arsitektur.learning_rate, arsitektur.optimizer)
    tmp2  = os.path.join(tempfile.gettempdir(), f'best_p2_{id(model)}.keras')

    logger.info(f'PHASE 2 (fine-tune)  epochs_max={ft_epochs}  lr={arsitektur.learning_rate/5:.2e}')
    logger.info('  Epoch  loss      acc       val_loss  val_acc   lr')

    cbs2 = [
        # Phase 2: semua callback monitor val_accuracy (konsisten — tujuan utama adalah akurasi)
        keras.callbacks.ModelCheckpoint(tmp2, monitor='val_accuracy', save_best_only=True,
                                        mode='max', initial_value_threshold=p1_best_val_acc,
                                        verbose=0),
        keras.callbacks.EarlyStopping(monitor='val_accuracy', patience=max(10, patience // 2),
                                      min_delta=0.001, mode='max',
                                      restore_best_weights=False, verbose=0),
        keras.callbacks.ReduceLROnPlateau(monitor='val_accuracy', factor=0.5, mode='max',
                                          patience=max(5, patience // 4), min_lr=1e-7, verbose=0),
    ]

    offset = p1_len
    _prev_lr2 = [float(arsitektur.learning_rate / 5)]

    class _LogCb2(keras.callbacks.Callback):
        def on_epoch_end(self, epoch, logs=None):
            lg = logs or {}
            current_lr = float(self.model.optimizer.learning_rate)
            lr_note = ''
            if current_lr < _prev_lr2[0] - 1e-10:
                lr_note = f' ← LR turun dari {_prev_lr2[0]:.2e}'
                _prev_lr2[0] = current_lr
            logger.info(
                f'  {epoch+1:5d}  {lg.get("loss",0):.4f}    {lg.get("accuracy",0):.4f}    '
                f'{lg.get("val_loss",0):.4f}    {lg.get("val_accuracy",0):.4f}   '
                f'{current_lr:.2e}{lr_note}'
            )
            if on_epoch_end:
                on_epoch_end(offset + epoch + 1, total_epochs, {**lg, 'fine_tuning': True})
    cbs2.append(_LogCb2())

    h2 = model.fit(X_train, y_train, validation_data=(X_val, y_val),
                   epochs=ft_epochs, batch_size=arsitektur.batch_size,
                   class_weight=class_weight, verbose=0, callbacks=cbs2)

    p2_best_val_acc  = max(h2.history.get('val_accuracy', [0]))
    p2_best_val_loss = min(h2.history.get('val_loss', [999]))
    if os.path.exists(tmp2):
        logger.info(
            f'PHASE 2 SELESAI  epoch={len(h2.history["loss"])}  '
            f'best_val_loss={p2_best_val_loss:.4f}  best_val_acc={p2_best_val_acc:.4f}  '
            f'→ MELAMPAUI Phase 1, pakai model Phase 2'
        )
        model = keras.models.load_model(tmp2, compile=False)
        model.compile(
            optimizer=_make_optimizer(arsitektur.optimizer, arsitektur.learning_rate / 10),
            loss=keras.losses.SparseCategoricalCrossentropy(),
            metrics=['accuracy'],
        )
        os.remove(tmp2)
    else:
        # Phase 2 tidak membaik — kembalikan ke model terbaik Phase 1
        logger.info(
            f'PHASE 2 SELESAI  epoch={len(h2.history["loss"])}  '
            f'best_val_loss={p2_best_val_loss:.4f}  best_val_acc={p2_best_val_acc:.4f}  '
            f'→ tidak melampaui Phase 1, pakai fallback Phase 1'
        )
        model = keras.models.load_model(tmp1_fallback, compile=False)

    if os.path.exists(tmp1_fallback):
        os.remove(tmp1_fallback)

    # Merge both phase histories
    history_dict = {}
    for key in ('loss', 'accuracy', 'val_loss', 'val_accuracy'):
        history_dict[key] = (
            [float(v) for v in h1.history.get(key, [])] +
            [float(v) for v in h2.history.get(key, [])]
        )

    elapsed = time.time() - t_start
    logger.info(f'TRAINING SELESAI  total_epoch={len(history_dict["loss"])}  waktu={elapsed/60:.1f} menit')
    logger.info(f'  val_accuracy terbaik keseluruhan: {max(history_dict["val_accuracy"]):.4f}')
    logger.info('=' * 60)
    for handler in logger.handlers:
        handler.close()

    return model, history_dict


def save_model(model, arsitektur_id, base_dir):
    folder = os.path.join(base_dir, 'app', 'static', 'models')
    os.makedirs(folder, exist_ok=True)
    filename = f'model_{arsitektur_id}.keras'
    model.save(os.path.join(folder, filename))
    return f'models/{filename}'


def evaluate(arsitektur, base_dir):
    import json
    from tensorflow import keras
    from sklearn.metrics import confusion_matrix, classification_report

    model_file = os.path.join(base_dir, 'app', 'static', arsitektur.model_path)
    model = keras.models.load_model(model_file, compile=False)

    _, _, X_val, y_val = load_dataset(
        arsitektur.split_config_id,
        arsitektur.fold_val,
        arsitektur.input_size,
        base_dir,
    )

    if len(X_val) == 0:
        raise ValueError('Tidak ada data validasi yang berhasil dimuat.')

    y_pred = np.argmax(model.predict(X_val, verbose=0), axis=1)

    cm = confusion_matrix(y_val, y_pred, labels=[0, 1, 2]).tolist()
    akurasi = float(np.sum(y_pred == y_val) / len(y_val))

    report = classification_report(
        y_val, y_pred,
        labels=[0, 1, 2],
        target_names=['berat', 'sedang', 'ringan'],
        output_dict=True,
        zero_division=0,
    )

    return {
        'total_data_val': int(len(y_val)),
        'akurasi':        round(akurasi * 100, 2),
        'confusion_matrix': json.dumps(cm),
        'per_class': {
            'berat':   {k: round(report['berat'][k] * 100, 2)   for k in ('precision', 'recall', 'f1-score')},
            'sedang':  {k: round(report['sedang'][k] * 100, 2)  for k in ('precision', 'recall', 'f1-score')},
            'ringan':  {k: round(report['ringan'][k] * 100, 2)  for k in ('precision', 'recall', 'f1-score')},
        },
        'macro': {
            'precision': round(report['macro avg']['precision'] * 100, 2),
            'recall':    round(report['macro avg']['recall'] * 100, 2),
            'f1':        round(report['macro avg']['f1-score'] * 100, 2),
        },
    }


def predict_cv(arsitektur, base_dir, on_progress=None):
    """
    K-Fold cross-validation prediction.
    Each photo's fold is predicted by a model trained on all OTHER folds.
    on_progress(fold_done, n_folds, epoch, total_epochs) — called each epoch + at fold completion.
    Returns list of {dokumentasi_id, prediksi, aktual, confidence}.
    """
    import gc
    from collections import defaultdict
    from app.models.split_config import SplitConfig
    from app.models.split_item import SplitItem

    split_cfg = SplitConfig.query.get(arsitektur.split_config_id)
    n_splits  = split_cfg.n_splits

    # Subquery: path denoise preprocessed per dokumentasi_id
    prep_sq = (
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
        class _Cfg:
            pass
        cfg_obj = _Cfg()
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

        for item in fold_items[fold_k]:
            # Utamakan denoise preprocessed agar konsisten dengan training, fallback ke original
            path_rel = item.prep_path if item.prep_path else item.path_file
            img_path = os.path.join(base_dir, 'app', 'static', path_rel)
            if not os.path.isfile(img_path):
                continue
            try:
                img = Image.open(img_path).convert('RGB').resize((cfg_base['input_size'], cfg_base['input_size']))
                arr = np.array(img, dtype=np.float32)[np.newaxis]
                probs = model.predict(arr, verbose=0)[0]
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
    """Jalankan inferensi pada semua foto yang punya koordinat + label."""
    from tensorflow import keras

    model_file = os.path.join(base_dir, 'app', 'static', arsitektur.model_path)
    model = keras.models.load_model(model_file, compile=False)

    # Subquery: path denoise preprocessed per dokumentasi_id
    prep_sq = (
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
            arr = np.array(img, dtype=np.float32)[np.newaxis]
            probs = model.predict(arr, verbose=0)[0]
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
