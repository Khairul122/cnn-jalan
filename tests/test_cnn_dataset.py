"""
Tes load_dataset: training diperluas memakai semua tahap preprocessing non-acak (dengan
dedup konten identik); val/fold uji TETAP 1 gambar/foto (tahap denoise, fallback original)
supaya sebanding dengan predict_all/predict_cv/cv_summary.
Jalankan dari root project:
  .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -t . -v

Memakai database dev. Semua baris uji dibuat sementara dan dihapus di tearDown.
"""
import os
import uuid
import unittest
from unittest import mock

from PIL import Image

from app import create_app, db
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.hasil_preprocessing import HasilPreprocessing
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.pengguna import Pengguna
from app.models.preprocessing_config import PreprocessingConfig
from app.models.split_config import SplitConfig
from app.models.split_item import SplitItem
from app.services import cnn_service

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class CnnDatasetTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.tag = uuid.uuid4().hex[:8]
        with cls.app.app_context():
            u = Pengguna(nama='Uji CNN', email=f'cnn-{cls.tag}@example.test', role='admin')
            u.set_password('uji-password-123')
            db.session.add(u)
            db.session.commit()
            cls.user_id = u.id

            lokasi = LokasiKerusakan.query.order_by(LokasiKerusakan.id).first()
        assert lokasi is not None, 'butuh minimal 1 lokasi di database (jalankan seed_data.py)'
        cls.lokasi_id = lokasi.id

    def setUp(self):
        self.split_ids, self.prep_config_ids, self.prep_ids = [], [], []
        self.temp_files, self.foto_extra_ids = [], []

    def tearDown(self):
        with self.app.app_context():
            for pid in self.prep_ids:
                HasilPreprocessing.query.filter_by(id=pid).delete()
            for cid in self.prep_config_ids:
                PreprocessingConfig.query.filter_by(id=cid).delete()
            for sid in self.split_ids:
                SplitItem.query.filter_by(config_id=sid).delete()
                SplitConfig.query.filter_by(id=sid).delete()
            for fid in self.foto_extra_ids:
                DokumentasiFoto.query.filter_by(id=fid).delete()
            db.session.commit()
        for path in self.temp_files:
            if os.path.isfile(path):
                os.remove(path)

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            Pengguna.query.filter_by(id=cls.user_id).delete()
            db.session.commit()

    # ── helpers ────────────────────────────────────────────────
    def make_split(self):
        with self.app.app_context():
            sp = SplitConfig(nama=f'cnn-uji-{self.tag}', split_type='kfold', n_splits=3,
                             random_state=1, label_sumber='tingkat', total_data=0,
                             pengguna_id=self.user_id)
            db.session.add(sp)
            db.session.commit()
            self.split_ids.append(sp.id)
            return sp.id

    def add_item(self, split_id, foto_id, fold, tingkat):
        with self.app.app_context():
            db.session.add(SplitItem(config_id=split_id, dokumentasi_id=foto_id,
                                     tingkat_kerusakan_id=tingkat, fold_index=fold))
            db.session.commit()

    def make_foto(self, suffix='a'):
        """
        Foto BARU (bukan foto seed produksi) tanpa riwayat preprocessing sama sekali.
        Wajib dipakai kapan pun tes butuh dokumentasi_id yang dijamin bersih — foto seed
        produksi sudah semua dipreprocessing, dan _stage_map_for memilih path lewat
        MAX(path_output) lintas SEMUA baris (termasuk punya proses lain), jadi memakai
        foto seed bisa membuat tes flaky (kadang file test menang, kadang file produksi asli
        yang menang tergantung urutan string).
        """
        rel_dir = os.path.join('uploads', 'foto')
        abs_dir = os.path.join(BASE_DIR, 'app', 'static', rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        fname = f'{self.tag}_original_{suffix}.jpg'
        abs_path = os.path.join(abs_dir, fname)
        Image.new('RGB', (8, 8), 'green').save(abs_path, 'JPEG')
        self.temp_files.append(abs_path)
        with self.app.app_context():
            foto = DokumentasiFoto(lokasi_id=self.lokasi_id, nama_file=fname,
                                   path_file=f'uploads/foto/{fname}')
            db.session.add(foto)
            db.session.commit()
            self.foto_extra_ids.append(foto.id)
            return foto.id

    def make_prep_config(self):
        with self.app.app_context():
            cfg = PreprocessingConfig(nama_config=f'cnn-uji-{self.tag}', pengguna_id=self.user_id)
            db.session.add(cfg)
            db.session.commit()
            self.prep_config_ids.append(cfg.id)
            return cfg.id

    def add_prep(self, foto_id, config_id, step_name, color='blue'):
        rel_dir = os.path.join('uploads', 'preprocessed')
        abs_dir = os.path.join(BASE_DIR, 'app', 'static', rel_dir)
        os.makedirs(abs_dir, exist_ok=True)
        fname = f'{self.tag}_{step_name}_{foto_id}.jpg'
        abs_path = os.path.join(abs_dir, fname)
        # quality=100 supaya warna solid tidak ikut dikompresi beda antar file (hash tetap konsisten)
        Image.new('RGB', (8, 8), color).save(abs_path, 'JPEG', quality=100)
        self.temp_files.append(abs_path)
        rel_path = f'uploads/preprocessed/{fname}'
        with self.app.app_context():
            h = HasilPreprocessing(dokumentasi_id=foto_id, config_id=config_id, step_name=step_name,
                                   path_output=rel_path, status='selesai')
            db.session.add(h)
            db.session.commit()
            self.prep_ids.append(h.id)

    # ── tes ────────────────────────────────────────────────────
    def test_train_expands_but_val_stays_single_image(self):
        """
        Training diperluas ke semua tahap; val/fold uji TETAP 1 gambar/foto (tahap denoise)
        -- supaya sebanding dengan predict_all/predict_cv/cv_summary yang juga 1 gambar/foto
        (keputusan 2026-09-23, lihat docstring load_dataset).
        """
        sid = self.make_split()
        cfg_id = self.make_prep_config()
        foto_train, foto_val = self.make_foto('train'), self.make_foto('val')

        # Tiap tahap punya warna (=konten) BERBEDA -> 4 gambar unik, tidak boleh di-dedup.
        colors = {'resize': 'blue', 'crop': 'red', 'normalisasi': 'green', 'denoise': 'yellow'}
        for step, color in colors.items():
            self.add_prep(foto_train, cfg_id, step, color=color)
            self.add_prep(foto_val, cfg_id, step, color=color)

        self.add_item(sid, foto_train, fold=0, tingkat=1)
        self.add_item(sid, foto_val, fold=1, tingkat=2)

        with self.app.app_context(), \
             mock.patch.object(cnn_service.dataset, 'MIN_TRAIN_SAMPLES', 1), \
             mock.patch.object(cnn_service.dataset, 'MIN_VAL_SAMPLES', 1):
            X_train, y_train, groups_train, X_val, y_val, groups_val = cnn_service.load_dataset(
                sid, fold_val=1, input_size=32, base_dir=BASE_DIR)

        self.assertEqual(len(X_train), 4)   # 4 tahap → 4 sampel dari 1 foto training
        self.assertTrue((y_train == 0).all())   # tingkat=1 → label 0
        self.assertEqual(set(groups_train.tolist()), {foto_train})

        # Val/fold uji TETAP 1 gambar per foto (tahap denoise), tidak ikut diperbanyak.
        self.assertEqual(len(X_val), 1)
        self.assertEqual(y_val[0], 1)   # tingkat=2 → label 1
        self.assertEqual(groups_val[0], foto_val)

    def test_train_dedupes_identical_stage_content(self):
        """
        Reproduksi kasus nyata: preprocessing_config.crop_enabled=False membuat tahap
        'crop' identik byte-per-byte dengan 'resize' (preprocessing_service hanya
        menyalin gambar tanpa transformasi). Tanpa dedup, foto ini akan dihitung 4
        sampel padahal cuma 3 gambar unik (resize=crop, normalisasi, denoise).
        """
        sid = self.make_split()
        cfg_id = self.make_prep_config()
        foto_train = self.make_foto('dedup')

        self.add_prep(foto_train, cfg_id, 'resize', color='blue')
        self.add_prep(foto_train, cfg_id, 'crop', color='blue')       # identik dengan resize
        self.add_prep(foto_train, cfg_id, 'normalisasi', color='green')
        self.add_prep(foto_train, cfg_id, 'denoise', color='yellow')

        self.add_item(sid, foto_train, fold=0, tingkat=1)

        with self.app.app_context(), mock.patch.object(cnn_service.dataset, 'MIN_TRAIN_SAMPLES', 1):
            X_train, y_train, groups_train, X_val, y_val, groups_val = cnn_service.load_dataset(
                sid, fold_val=None, input_size=32, base_dir=BASE_DIR)

        self.assertEqual(len(X_train), 3)   # bukan 4 — 'crop' duplikat 'resize' di-skip
        self.assertEqual(groups_train.tolist(), [foto_train] * 3)

    def test_train_falls_back_to_original_without_preprocessing(self):
        sid = self.make_split()
        foto_train = self.make_foto()
        self.add_item(sid, foto_train, fold=0, tingkat=3)

        with self.app.app_context(), mock.patch.object(cnn_service.dataset, 'MIN_TRAIN_SAMPLES', 1):
            X_train, y_train, groups_train, X_val, y_val, groups_val = cnn_service.load_dataset(
                sid, fold_val=None, input_size=32, base_dir=BASE_DIR)

        self.assertEqual(len(X_train), 1)   # tanpa preprocessing → 1 sampel original, bukan gagal
        self.assertEqual(groups_train[0], foto_train)

    def test_val_falls_back_to_original_without_denoise(self):
        sid = self.make_split()
        foto_val = self.make_foto('valfallback')
        self.add_item(sid, foto_val, fold=0, tingkat=2)

        with self.app.app_context(), \
             mock.patch.object(cnn_service.dataset, 'MIN_TRAIN_SAMPLES', 0), \
             mock.patch.object(cnn_service.dataset, 'MIN_VAL_SAMPLES', 1):
            X_train, y_train, groups_train, X_val, y_val, groups_val = cnn_service.load_dataset(
                sid, fold_val=0, input_size=32, base_dir=BASE_DIR)

        self.assertEqual(len(X_val), 1)   # tanpa denoise -> fallback ke foto original, bukan gagal
        self.assertEqual(y_val[0], 1)     # tingkat=2 -> label 1
        self.assertEqual(groups_val[0], foto_val)


if __name__ == '__main__':
    unittest.main()
