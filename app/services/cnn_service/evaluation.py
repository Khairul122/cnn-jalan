"""Evaluasi 1 model pada 1 fold (bukan metrik CV resmi — lihat metrics_service.cv_summary)."""
import os
import numpy as np

from app.kelas import KEYS, N_KELAS
from .dataset import load_dataset


def evaluate(arsitektur, base_dir):
    import json
    from tensorflow import keras
    from sklearn.metrics import confusion_matrix, classification_report

    model_file = os.path.join(base_dir, 'app', 'static', arsitektur.model_path)
    model = keras.models.load_model(model_file, compile=False)

    _, _, _, X_val, y_val, _ = load_dataset(
        arsitektur.split_config_id,
        arsitektur.fold_val,
        arsitektur.input_size,
        base_dir,
    )

    if len(X_val) == 0:
        raise ValueError('Tidak ada data validasi yang berhasil dimuat.')

    y_pred = np.argmax(model.predict(X_val, verbose=0), axis=1)

    cm = confusion_matrix(y_val, y_pred, labels=list(range(N_KELAS))).tolist()
    akurasi = float(np.sum(y_pred == y_val) / len(y_val))

    report = classification_report(
        y_val, y_pred,
        labels=list(range(N_KELAS)),
        target_names=list(KEYS),
        output_dict=True,
        zero_division=0,
    )

    return {
        'total_data_val': int(len(y_val)),
        'akurasi':        round(akurasi * 100, 2),
        'confusion_matrix': json.dumps(cm),
        'per_class': {
            key: {k: round(report[key][k] * 100, 2) for k in ('precision', 'recall', 'f1-score')}
            for key in KEYS
        },
        'macro': {
            'precision': round(report['macro avg']['precision'] * 100, 2),
            'recall':    round(report['macro avg']['recall'] * 100, 2),
            'f1':        round(report['macro avg']['f1-score'] * 100, 2),
        },
    }
