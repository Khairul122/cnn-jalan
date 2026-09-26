"""Kosongkan semua data hasil proses supaya pipeline bisa diuji manual dari awal.

Dipertahankan : pengguna, master (jenis/tingkat kerusakan), lokasi_kerusakan + dokumentasi_foto,
                seluruh file foto (uploads/foto), konfigurasi Colab (preprocessing, labeling, augmentasi).
Dihapus       : label, hasil labeling, hasil preprocessing (+ file), augmentasi (+ file), split, arsitektur,
                training, evaluasi, prediksi, klasifikasi, peta, file .keras dan log training,
                serta konfigurasi preprocessing dan labeling selain Colab.

Pakai: python scripts/reset_data_uji.py
"""
import glob
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)
STATIC = os.path.join(BASE_DIR, 'app', 'static')
NAMA_PREP = 'Colab: resize 256, crop 224, denoise NL-Means'
NAMA_LABEL = 'Colab: MobileNetV2 + PCA 50 + K-Means 4'
NAMA_AUG = 'Colab: parameter augmentasi notebook (tidak perlu dijalankan)'

TABEL = (
    'hasil_training', 'hasil_evaluasi', 'prediksi_model', 'arsitektur_config', 'split_item', 'split_config',
    'hasil_preprocessing', 'hasil_augmentasi', 'peta_kerusakan', 'hasil_klasifikasi_cnn',
    'evaluasi_model', 'label_kerusakan', 'hasil_labeling_item', 'hasil_labeling',
)
FOLDER_FILE = (('uploads/preprocessed', '*'), ('uploads/augmented', '*'), ('models', '*.keras'), ('logs', '*.log'))


def main():
    from sqlalchemy import text
    from app import create_app, db

    with create_app().app_context():
        db.session.execute(text('SET FOREIGN_KEY_CHECKS = 0'))
        for t in TABEL:
            n = db.session.execute(text(f'SELECT COUNT(*) FROM `{t}`')).scalar()
            db.session.execute(text(f'TRUNCATE TABLE `{t}`'))
            print(f'  {t:24s} {n:5d} baris dihapus')
        n = db.session.execute(text('DELETE FROM preprocessing_config WHERE nama_config <> :n'), {'n': NAMA_PREP}).rowcount
        print(f'  {"preprocessing_config":24s} {n:5d} baris dihapus (config Colab dipertahankan)')
        n = db.session.execute(text('DELETE FROM labeling_config WHERE nama_config <> :n'), {'n': NAMA_LABEL}).rowcount
        print(f'  {"labeling_config":24s} {n:5d} baris dihapus (config Colab dipertahankan)')
        n = db.session.execute(text('DELETE FROM augmentasi_config WHERE nama_config <> :n'), {'n': NAMA_AUG}).rowcount
        print(f'  {"augmentasi_config":24s} {n:5d} baris dihapus (config Colab dipertahankan)')
        db.session.execute(text('SET FOREIGN_KEY_CHECKS = 1'))
        db.session.commit()

        for tabel in ('lokasi_kerusakan', 'dokumentasi_foto', 'preprocessing_config', 'labeling_config', 'augmentasi_config'):
            print(f'  dipertahankan {tabel:20s} {db.session.execute(text(f"SELECT COUNT(*) FROM `{tabel}`")).scalar()} baris')

    for sub, pola in FOLDER_FILE:
        files = [f for f in glob.glob(os.path.join(STATIC, sub, pola)) if os.path.isfile(f) and not f.endswith('.gitkeep')]
        for f in files:
            os.remove(f)
        print(f'  file dihapus app/static/{sub}: {len(files)}')
    print(f'  foto dipertahankan: {len(os.listdir(os.path.join(STATIC, "uploads", "foto")))}')


if __name__ == '__main__':
    main()
