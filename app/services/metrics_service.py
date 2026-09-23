import numpy as np
from sklearn.metrics import confusion_matrix, f1_score, recall_score

from app import db
from app.models.prediksi_model import PrediksiModel
from app.models.split_item import SplitItem

KELAS = ('berat', 'sedang', 'ringan')


def cv_summary(arsitektur):
    """
    Metrik K-Fold CV dari prediksi CV (tiap foto diprediksi model yang tidak pernah melihatnya).
    Return None jika prediksi belum berupa CV. Semua nilai dalam persen.
    """
    if arsitektur.pred_type != 'cv':
        return None
    rows = (
        db.session.query(PrediksiModel.prediksi, PrediksiModel.aktual, SplitItem.fold_index)
        .join(SplitItem, (SplitItem.dokumentasi_id == PrediksiModel.dokumentasi_id)
                         & (SplitItem.config_id == arsitektur.split_config_id))
        .filter(PrediksiModel.arsitektur_id == arsitektur.id, PrediksiModel.aktual.isnot(None))
        .all()
    )
    if not rows:
        return None

    pred = np.array([r[0] for r in rows])
    aktual = np.array([r[1] for r in rows])
    fold = np.array([r[2] for r in rows])

    per_fold = [
        {'fold': int(k) + 1, 'n': int((fold == k).sum()),
         'akurasi': round(float((pred[fold == k] == aktual[fold == k]).mean() * 100), 1)}
        for k in sorted(set(fold.tolist()))
    ]
    accs = [f['akurasi'] for f in per_fold]
    akurasi = float((pred == aktual).mean() * 100)
    baseline = float(np.bincount(aktual, minlength=3).max() / len(aktual) * 100)
    recall = recall_score(aktual, pred, labels=[0, 1, 2], average=None, zero_division=0) * 100

    return {
        'n': int(len(aktual)),
        'akurasi': round(akurasi, 1),
        'std': round(float(np.std(accs)), 1),
        'macro_f1': round(float(f1_score(aktual, pred, labels=[0, 1, 2], average='macro', zero_division=0) * 100), 1),
        'recall': {k: round(float(v), 1) for k, v in zip(KELAS, recall)},
        'per_fold': per_fold,
        'baseline': round(baseline, 1),
        'selisih_baseline': round(akurasi - baseline, 1),
        'confusion_matrix': confusion_matrix(aktual, pred, labels=[0, 1, 2]).tolist(),
    }
