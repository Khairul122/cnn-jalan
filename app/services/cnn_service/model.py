"""Arsitektur Keras: transfer learning MobileNetV2/EfficientNetB0 + head klasifikasi."""

N_CLASSES = 3  # Berat=0, Sedang=1, Ringan=2


def _pixel_gaussian_noise_layer(stddev):
    """keras.layers.GaussianNoise bawaan membatasi stddev ke [0,1] (asumsi input
    ternormalisasi) — pipeline ini pakai skala piksel [0,255] sampai preprocess_input di
    dalam model, jadi reimplementasi kecil tanpa batasan itu (logika sama seperti layer
    bawaan: tambah noise saat training saja)."""
    from tensorflow import keras

    class _PixelGaussianNoise(keras.layers.Layer):
        def call(self, x, training=False):
            if training:
                return x + keras.random.normal(keras.ops.shape(x), stddev=stddev)
            return x

    return _PixelGaussianNoise()


def _make_optimizer(optimizer_name, learning_rate):
    from tensorflow import keras
    if optimizer_name == 'adam':
        return keras.optimizers.Adam(learning_rate=learning_rate)
    elif optimizer_name == 'sgd':
        return keras.optimizers.SGD(learning_rate=learning_rate, momentum=0.9)
    return keras.optimizers.RMSprop(learning_rate=learning_rate)


def uses_onehot_labels(mixup_alpha, label_smoothing):
    """True kalau training butuh label one-hot/soft (Mixup atau label smoothing aktif),
    dipakai model.py (pilih loss) dan training.py (pilih format y_fit/y_inner)."""
    return bool((mixup_alpha and mixup_alpha > 0) or (label_smoothing and label_smoothing > 0))


def _make_loss(mixup_alpha, label_smoothing=0):
    """SparseCategoricalCrossentropy untuk label integer biasa; CategoricalCrossentropy
    (dengan label_smoothing kalau diminta) begitu Mixup atau label smoothing aktif — keduanya
    butuh label one-hot/soft, SparseCategoricalCrossentropy di Keras ini tidak punya param
    label_smoothing sama sekali. Lihat training.py::_fit_phase untuk pemilihan format y."""
    from tensorflow import keras
    if uses_onehot_labels(mixup_alpha, label_smoothing):
        return keras.losses.CategoricalCrossentropy(label_smoothing=label_smoothing or 0)
    return keras.losses.SparseCategoricalCrossentropy()


def build_model(model_type, input_size, dropout_rate, optimizer_name, learning_rate,
                mixup_alpha=0, label_smoothing=0, dense_units=64, dense_l2=1e-4):
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
    # Color jitter ringan (TODO.md P3) — hue/saturation di atas brightness/contrast yang sudah ada
    x = keras.layers.RandomHue(0.05, value_range=(0, 255))(x)
    x = keras.layers.RandomSaturation((0.4, 0.6), value_range=(0, 255))(x)
    # Noise sensor kamera lapangan ringan, diterapkan setelah tahap denoise preprocessing
    # (gambar training sudah didenoise — noise ini melatih model tahan variasi sensor, bukan
    # membalikkan denoise)
    x = _pixel_gaussian_noise_layer(3.0)(x)
    # Cutout/Random Erasing — patch kecil (<10% luas), model tidak boleh cuma bergantung
    # pada satu titik kerusakan paling mencolok
    x = keras.layers.RandomErasing(factor=0.5, scale=(0.02, 0.08), value_range=(0, 255))(x)

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
    # Dense(64)/L2=1e-4 default — TODO.md P4 usul turunkan ke Dense(32) ATAU naikkan L2 ke
    # 1e-3 sebagai ablation; keduanya dibuat configurable (bukan hardcode salah satu) supaya
    # bisa dibandingkan lewat UI tanpa ubah kode.
    x = keras.layers.Dense(dense_units, activation='relu',
                           kernel_regularizer=keras.regularizers.L2(dense_l2))(x)
    x = keras.layers.Dropout(dropout_rate / 2)(x)
    out = keras.layers.Dense(N_CLASSES, activation='softmax',
                             kernel_regularizer=keras.regularizers.L2(dense_l2))(x)

    model = keras.Model(inp, out)
    model.compile(
        optimizer=_make_optimizer(optimizer_name, learning_rate),
        loss=_make_loss(mixup_alpha, label_smoothing),
        metrics=['accuracy'],
    )
    return model


def _apply_fine_tuning(model, model_type, learning_rate, optimizer_name, mixup_alpha=0, label_smoothing=0):
    """Unfreeze top layers of the base sub-model and recompile with lr/10."""
    from tensorflow import keras
    # Dataset kecil (~224-540 train): unfreeze sedikit layer saja untuk hindari overfitting.
    # Diperkecil 2026-09-23 (dari 15/25) — log training berulang kali menunjukkan train acc
    # naik ke 70%+ di Phase 2 sementara val macet ~35-45%, tanda fine-tuning terlalu dalam
    # untuk jumlah sampel training yang ada.
    # MobileNetV2 ~154 layers → unfreeze last 8
    # EfficientNetB0 ~238 layers → unfreeze last 12
    n_unfreeze = 8 if model_type == 'mobilenetv2' else 12

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
        optimizer=_make_optimizer(optimizer_name, learning_rate / 10),
        loss=_make_loss(mixup_alpha, label_smoothing),
        metrics=['accuracy'],
    )
    return model
