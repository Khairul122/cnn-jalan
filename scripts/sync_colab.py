"""Sinkronkan DB dengan hasil Colab (data-colab/hasil_klasifikasi_jalan.csv).

- label_kerusakan      <- kolom Kelas (label K-Means), metode 'klasterisasi'
- hasil_klasifikasi_cnn <- Kelas_Prediksi + Keyakinan (dibuat ulang)
- peta_kerusakan        <- dibuat ulang dari hasil klasifikasi (status draft)

Pakai: python scripts/sync_colab.py  (venv aktif)
Lokasi/foto tidak disentuh; nama_citra dan koordinat harus cocok dengan CSV.
"""
import csv
import os
import sys
from datetime import date

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)
CSV_PATH = os.path.join(BASE_DIR, 'data-colab', 'hasil_klasifikasi_jalan.csv')
AMBANG_CONFIDENCE = 0.5
CATATAN = 'Colab CNN_Kerusakan_Jalan_Lhokseumawe (MobileNetV2)'


def main():
    from app import create_app, db
    from app.models.dokumentasi_foto import DokumentasiFoto
    from app.models.hasil_klasifikasi_cnn import HasilKlasifikasiCnn
    from app.models.label_kerusakan import LabelKerusakan
    from app.models.lokasi_kerusakan import LokasiKerusakan
    from app.models.peta_kerusakan import PetaKerusakan
    from app.models.tingkat_kerusakan import TingkatKerusakan

    with open(CSV_PATH, encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    with create_app().app_context():
        tingkat = {t.nama_tingkat: t for t in TingkatKerusakan.query.all()}
        lokasi = {l.nama_citra: l for l in LokasiKerusakan.query.all()}

        galat = [r['Citra'] for r in rows
                 if r['Citra'] not in lokasi or r['Kelas'] not in tingkat or r['Kelas_Prediksi'] not in tingkat]
        for r in rows:
            l = lokasi.get(r['Citra'])
            if l and (abs(float(l.latitude) - float(r['x'])) > 1e-6 or abs(float(l.longitude) - float(r['y'])) > 1e-6):
                galat.append(r['Citra'] + ' (koordinat beda)')
        if galat:
            sys.exit('CSV tidak cocok dengan DB: ' + ', '.join(galat))

        # Urutan aman FK: peta -> hasil klasifikasi
        PetaKerusakan.query.delete()
        HasilKlasifikasiCnn.query.delete()
        db.session.flush()

        for r in rows:
            lok = lokasi[r['Citra']]
            label = LabelKerusakan.query.filter_by(lokasi_id=lok.id).first()
            if label is None:
                label = LabelKerusakan(lokasi_id=lok.id, pengguna_id=lok.pengguna_id)
                db.session.add(label)
            label.tingkat_kerusakan_id = tingkat[r['Kelas']].id
            label.metode = 'klasterisasi'
            label.cluster_id = label.kepadatan_tepi = label.jarak_centroid = label.hasil_labeling_id = None
            label.catatan = 'Label K-Means dari Colab'

            foto = DokumentasiFoto.query.filter_by(lokasi_id=lok.id).order_by(DokumentasiFoto.id).first()
            if foto is None:
                continue
            pred = tingkat[r['Kelas_Prediksi']]
            conf = float(r['Keyakinan'])
            hasil = HasilKlasifikasiCnn(
                dokumentasi_id=foto.id, jenis_kerusakan_id=None, tingkat_kerusakan_id=pred.id,
                confidence_score=conf, is_valid=conf >= AMBANG_CONFIDENCE, catatan=CATATAN)
            db.session.add(hasil)
            db.session.flush()
            db.session.add(PetaKerusakan(
                lokasi_id=lok.id, hasil_klasifikasi_id=hasil.id, status_pemetaan='draft',
                prioritas_perbaikan=pred.skor_prioritas, tanggal_pemetaan=date.today(),
                pengguna_id=lok.pengguna_id))
        db.session.commit()

        print('label   :', {t.nama_tingkat: LabelKerusakan.query.filter_by(tingkat_kerusakan_id=t.id).count() for t in tingkat.values()})
        print('klasif. :', HasilKlasifikasiCnn.query.count(), '| peta:', PetaKerusakan.query.count())


if __name__ == '__main__':
    main()
