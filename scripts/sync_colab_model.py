"""Ganti SEMUA data model lama dengan model dari notebook Colab (MobileNetV2, fold 3 dari 5).

Dihapus : hasil_training, hasil_evaluasi, prediksi_model, arsitektur_config,
          split_item, split_config, dan file .keras di app/static/models.
Diisi   : split (StratifiedKFold 5, seed 42, label Kelas CSV), 1 arsitektur_config,
          riwayat epoch (dari output notebook), evaluasi fold 3, prediksi 280 foto.

Evaluasi dihitung dari CSV: tiap foto validasi diprediksi oleh model yang tidak melatihnya,
jadi hasilnya sama dengan `model.predict(val_dataset)` di Colab. Skrip berhenti kalau tidak
cocok dengan 52/56 dan distribusi validasi Colab.

Pakai: python scripts/sync_colab_model.py  (venv aktif; jalankan sync_colab.py dulu)
Bobot model (.keras) tidak ada di data-colab, jadi model_path kosong: model belum bisa
dipakai untuk klasifikasi foto baru sampai file .keras disalin ke app/static/models.
"""
import csv
import glob
import json
import os
import re
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)
DATA = os.path.join(BASE_DIR, 'data-colab')
NOTEBOOK = os.path.join(DATA, 'CNN_Kerusakan_Jalan_Lhokseumawe_(3).ipynb')
MODEL_DIR = os.path.join(BASE_DIR, 'app', 'static', 'models')

URUTAN_COLAB = ['Baik', 'Sedang', 'Rusak Ringan', 'Rusak Berat']
FOLD_VAL = 3          # 1-based di notebook; kolom fold_val & fold_index di DB 0-based
SEED = 42
NAMA = 'Colab MobileNetV2 (Fold 3 dari 5)'


def parse_epochs():
    with open(NOTEBOOK, encoding='utf-8') as f:
        cell = json.load(f)['cells'][8]
    teks = re.sub(r'\x1b\[[0-9;]*m', '', ''.join(''.join(o.get('text', [])) for o in cell['outputs']))
    pola = re.compile(r'accuracy: ([\d.]+) - loss: ([\d.]+) - val_accuracy: ([\d.]+) - val_loss: ([\d.]+)')
    return [dict(accuracy=float(a), loss=float(l), val_accuracy=float(va), val_loss=float(vl))
            for a, l, va, vl in pola.findall(teks)]


def main():
    import numpy as np
    from sklearn.metrics import classification_report, confusion_matrix
    from sklearn.model_selection import StratifiedKFold

    from app import create_app, db
    from app.kelas import KEYS, N_KELAS
    from app.models.arsitektur_config import ArsitekturConfig
    from app.models.dokumentasi_foto import DokumentasiFoto
    from app.models.hasil_evaluasi import HasilEvaluasi
    from app.models.hasil_training import HasilTraining
    from app.models.lokasi_kerusakan import LokasiKerusakan
    from app.models.prediksi_model import PrediksiModel
    from app.models.split_config import SplitConfig
    from app.models.split_item import SplitItem
    from app.models.tingkat_kerusakan import TingkatKerusakan

    with open(os.path.join(DATA, 'hasil_klasifikasi_jalan.csv'), encoding='utf-8') as f:
        rows = list(csv.DictReader(f))
    # Indeks Colab (Baik=0..Rusak Berat=3) -> indeks app (Rusak Berat=0..Baik=3)
    ke_app = {n: N_KELAS - 1 - i for i, n in enumerate(URUTAN_COLAB)}
    y = np.array([ke_app[r['Kelas']] for r in rows])
    pred = np.array([ke_app[r['Kelas_Prediksi']] for r in rows])

    folds = list(StratifiedKFold(5, shuffle=True, random_state=SEED).split(np.zeros(len(y)), y))
    idx_val = folds[FOLD_VAL - 1][1]
    cm = confusion_matrix(y[idx_val], pred[idx_val], labels=list(range(N_KELAS)))
    benar = int(np.trace(cm))
    distribusi = [int(cm[i].sum()) for i in range(N_KELAS)]        # urutan app: Berat, Ringan, Sedang, Baik
    if (len(idx_val), benar, distribusi) != (56, 52, [13, 21, 10, 12]):
        sys.exit(f'Split tidak cocok dengan Colab: n={len(idx_val)} benar={benar} dist={distribusi}')

    epochs = parse_epochs()
    if not epochs:
        sys.exit('Riwayat epoch tidak terbaca dari notebook.')
    rep = classification_report(y[idx_val], pred[idx_val], labels=list(range(N_KELAS)),
                                target_names=list(KEYS), output_dict=True, zero_division=0)

    with create_app().app_context():
        foto = {l.nama_citra: DokumentasiFoto.query.filter_by(lokasi_id=l.id).order_by(DokumentasiFoto.id).first()
                for l in LokasiKerusakan.query.all()}
        tingkat_id = {n: t.id for n, t in ((t.nama_tingkat, t) for t in TingkatKerusakan.query.all())}
        pengguna_id = LokasiKerusakan.query.first().pengguna_id
        if any(foto.get(r['Citra']) is None for r in rows):
            sys.exit('Ada citra CSV tanpa foto di DB.')

        for m in (HasilTraining, HasilEvaluasi, PrediksiModel, ArsitekturConfig, SplitItem, SplitConfig):
            m.query.delete()
        db.session.flush()
        hapus = glob.glob(os.path.join(MODEL_DIR, '*.keras'))
        for p in hapus:
            os.remove(p)

        split = SplitConfig(nama='Colab StratifiedKFold5-seed42', n_splits=5, random_state=SEED,
                            radius_grup_m=0, label_sumber='tingkat', total_data=len(rows), pengguna_id=pengguna_id)
        db.session.add(split)
        db.session.flush()
        fold_of = {}
        for k, (_, val) in enumerate(folds):
            for i in val:
                fold_of[int(i)] = k
        for i, r in enumerate(rows):
            db.session.add(SplitItem(config_id=split.id, dokumentasi_id=foto[r['Citra']].id,
                                     tingkat_kerusakan_id=tingkat_id[r['Kelas']], fold_index=fold_of[i]))

        cfg = ArsitekturConfig(
            nama=NAMA, model_type='mobilenetv2', input_size=224, learning_rate=0.001, batch_size=32,
            epochs=80, patience=15, dropout_rate=0.5, optimizer='adam', mixup_alpha=0, label_smoothing=0,
            dense_units=64, dense_l2=0.01, skip_fine_tuning=False, aug_off='',
            split_config_id=split.id, fold_val=FOLD_VAL - 1, status='selesai',
            model_path=None, final_model_path=None, pred_type='single', pengguna_id=pengguna_id)
        db.session.add(cfg)
        db.session.flush()

        for n, e in enumerate(epochs, start=1):
            db.session.add(HasilTraining(arsitektur_id=cfg.id, epoch=n, **e))
        db.session.add(HasilEvaluasi(
            arsitektur_id=cfg.id, total_data_val=len(idx_val), akurasi=round(benar / len(idx_val) * 100, 2),
            confusion_matrix=json.dumps(cm.tolist()),
            per_class=json.dumps({k: {m: round(rep[k][m] * 100, 2) for m in ('precision', 'recall', 'f1-score')} for k in KEYS}),
            macro_precision=round(rep['macro avg']['precision'] * 100, 2),
            macro_recall=round(rep['macro avg']['recall'] * 100, 2),
            macro_f1=round(rep['macro avg']['f1-score'] * 100, 2)))
        for i, r in enumerate(rows):
            db.session.add(PrediksiModel(arsitektur_id=cfg.id, dokumentasi_id=foto[r['Citra']].id,
                                         prediksi=int(pred[i]), aktual=int(y[i]),
                                         confidence=float(r['Keyakinan']), probabilitas=None))
        db.session.commit()
        print(f'file .keras dihapus: {len(hapus)} | epoch: {len(epochs)} | akurasi fold {FOLD_VAL}: {benar}/{len(idx_val)}')
        print('confusion matrix (Berat, Ringan, Sedang, Baik):', cm.tolist())


if __name__ == '__main__':
    main()
