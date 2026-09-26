"""Buat konfigurasi yang dipakai notebook Colab (idempotent).

- preprocessing_config : resize 256 (cv2 Lanczos4), crop tengah 224, denoise fastNlMeans (h=7)
- labeling_config      : MobileNetV2 + PCA 50 + K-Means 4 klaster, seed 42, Canny 50/150
- arsitektur_config    : semua config yang ada namanya "Colab..." diberi profil 'colab'
- --jalankan-preprocessing : proses seluruh foto dengan config Colab (menggantikan hasil_preprocessing lama)

Pakai: python scripts/buat_konfigurasi_colab.py [--jalankan-preprocessing]
"""
import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)

NAMA_PREP = 'Colab: resize 256, crop 224, denoise NL-Means'
NAMA_LABEL = 'Colab: MobileNetV2 + PCA 50 + K-Means 4'


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--jalankan-preprocessing', action='store_true')
    args = ap.parse_args()

    from app import create_app, db
    from app.models.arsitektur_config import ArsitekturConfig
    from app.models.labeling_config import LabelingConfig
    from app.models.pengguna import Pengguna
    from app.models.preprocessing_config import PreprocessingConfig

    app = create_app()
    with app.app_context():
        pengguna_id = Pengguna.query.order_by(Pengguna.id).first().id

        prep = PreprocessingConfig.query.filter_by(nama_config=NAMA_PREP).first() or PreprocessingConfig()
        prep.nama_config = NAMA_PREP
        prep.target_width = prep.target_height = 256
        prep.resize_method, prep.resize_mode, prep.illum_correction = 'LANCZOS_CV', 'stretch', False
        prep.crop_enabled, prep.crop_width, prep.crop_height = True, 224, 224
        prep.norm_method, prep.denoise_method, prep.denoise_ksize = 'none', 'nlmeans', 3
        prep.pengguna_id = prep.pengguna_id or pengguna_id
        PreprocessingConfig.query.update({'is_default': False})
        prep.is_default = True
        db.session.add(prep)

        lab = LabelingConfig.query.filter_by(nama_config=NAMA_LABEL).first() or LabelingConfig()
        lab.nama_config, lab.n_cluster, lab.pca_komponen, lab.random_state = NAMA_LABEL, 4, 50, 42
        lab.canny_low, lab.canny_high = 50, 150
        lab.pengguna_id = lab.pengguna_id or pengguna_id
        LabelingConfig.query.update({'is_default': False})
        lab.is_default = True
        db.session.add(lab)

        n_arsitektur = ArsitekturConfig.query.filter(ArsitekturConfig.nama.like('Colab%')).update(
            {'profil': 'colab', 'aug_off': 'hue,saturasi,noise,erasing'}, synchronize_session=False)
        db.session.commit()
        print(f'preprocessing_config #{prep.id}, labeling_config #{lab.id}, arsitektur diberi profil colab: {n_arsitektur}')
        prep_id = prep.id

    if args.jalankan_preprocessing:
        app.config['WTF_CSRF_ENABLED'] = False
        client = app.test_client()
        with client.session_transaction() as s:
            s['_user_id'] = '1'
            s['_fresh'] = True
        r = client.post(f'/preprocessing/run/{prep_id}', follow_redirects=False)
        print('preprocessing:', r.status_code)


if __name__ == '__main__':
    main()
