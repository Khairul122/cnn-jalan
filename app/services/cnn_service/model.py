"""Arsitektur Keras: transfer learning MobileNetV2/EfficientNetB0 + head klasifikasi."""

N_CLASSES = 3  # Berat=0, Sedang=1, Ringan=2


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
        loss=keras.losses.SparseCategoricalCrossentropy(),
        metrics=['accuracy'],
    )
    return model
