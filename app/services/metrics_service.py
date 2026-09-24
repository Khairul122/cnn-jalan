import numpy as np
import json

from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score

from app import db
from app.models.prediksi_model import PrediksiModel
from app.models.split_item import SplitItem

from app.kelas import KEYS as KELAS, N_KELAS

LABELS = list(range(N_KELAS))


def cv_summary(arsitektur):
    """
    Metrik K-Fold CV dari prediksi CV (tiap foto diprediksi model yang tidak pernah melihatnya).
    Return None jika prediksi belum berupa CV. Semua nilai dalam persen.
    """
    if arsitektur.pred_type != 'cv':
        return None
    rows = (
        db.session.query(PrediksiModel.prediksi, PrediksiModel.aktual, SplitItem.fold_index, PrediksiModel.probabilitas)
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
    baseline = float(np.bincount(aktual, minlength=N_KELAS).max() / len(aktual) * 100)
    recall = recall_score(aktual, pred, labels=LABELS, average=None, zero_division=0) * 100
    precision = precision_score(aktual, pred, labels=LABELS, average=None, zero_division=0) * 100
    f1 = f1_score(aktual, pred, labels=LABELS, average=None, zero_division=0) * 100
    salah = aktual != pred
    # Kelas berjenjang (ordinal): salah ke kelas bersebelahan lebih ringan daripada melompat jauh.
    bersebelahan = int((np.abs(aktual - pred) == 1).sum())
    # Cross-entropy (negative log-likelihood) kelas sebenarnya: menilai kalibrasi confidence, bukan cuma argmax.
    # None untuk prediksi lama yang belum menyimpan probabilitas.
    probs = [json.loads(r[3]) if r[3] else None for r in rows]
    loss = None
    if all(p is not None for p in probs):
        p_benar = np.array([p[a] for p, a in zip(probs, aktual)], dtype=float)
        loss = round(float(-np.log(np.clip(p_benar, 1e-7, 1.0)).mean()), 3)

    return {
        'n': int(len(aktual)),
        'akurasi': round(akurasi, 1),
        'std': round(float(np.std(accs)), 1),
        'macro_f1': round(float(f1_score(aktual, pred, labels=LABELS, average='macro', zero_division=0) * 100), 1),
        'recall': {k: round(float(v), 1) for k, v in zip(KELAS, recall)},
        'precision': {k: round(float(v), 1) for k, v in zip(KELAS, precision)},
        'f1': {k: round(float(v), 1) for k, v in zip(KELAS, f1)},
        'kesalahan': {'total': int(salah.sum()), 'bersebelahan': bersebelahan,
                      'jauh': int(salah.sum()) - bersebelahan},
        'cross_entropy': loss,
        'per_fold': per_fold,
        'baseline': round(baseline, 1),
        'selisih_baseline': round(akurasi - baseline, 1),
        'confusion_matrix': confusion_matrix(aktual, pred, labels=LABELS).tolist(),
    }


def cv_ulangan(daftar):
    """
    Ringkasan Repeated K-Fold: gabungan hasil beberapa run CV (tiap run = satu split/seed berbeda, hiperparameter sama).
    daftar: list of (nama, cv_summary dict). Return None bila kurang dari 2 run. std = simpangan baku ANTAR-RUN
    (ddof=1), berbeda dari `std` di cv_summary yang antar-fold dalam satu run.
    """
    if len(daftar) < 2:
        return None

    def agg(values):
        arr = np.array(values, dtype=float)
        return {'mean': round(float(arr.mean()), 1), 'std': round(float(arr.std(ddof=1)), 1),
                'min': round(float(arr.min()), 1), 'max': round(float(arr.max()), 1)}

    return {
        'n_run': len(daftar),
        'runs': [{'nama': n, 'akurasi': cv['akurasi'], 'macro_f1': cv['macro_f1'], 'baseline': cv['baseline'],
                  'selisih_baseline': cv['selisih_baseline']} for n, cv in daftar],
        'akurasi': agg([cv['akurasi'] for _, cv in daftar]),
        'macro_f1': agg([cv['macro_f1'] for _, cv in daftar]),
        'baseline': agg([cv['baseline'] for _, cv in daftar]),
        'selisih_baseline': agg([cv['selisih_baseline'] for _, cv in daftar]),
        'recall': {k: agg([cv['recall'][k] for _, cv in daftar]) for k in KELAS},
    }
