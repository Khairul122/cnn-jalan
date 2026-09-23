"""
Tes perbaikan P1. Jalankan dari root project:
  .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -t . -v

Memakai database dev. Semua baris uji dibuat sementara dan dihapus di tearDown; aksi yang bisa
mengganggu server yang sedang berjalan (memulai training, mengubah status) memakai mock/rollback.
"""
import io
import os
import re
import tempfile
import unittest
import uuid
from types import SimpleNamespace
from unittest import mock

import numpy as np

from PIL import Image
from werkzeug.datastructures import FileStorage

from app import create_app, db
from app.models.arsitektur_config import ArsitekturConfig
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.label_kerusakan import LabelKerusakan
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.pengguna import Pengguna
from app.models.prediksi_model import PrediksiModel
from app.models.split_config import SplitConfig
from app.models.split_item import SplitItem
from app.services import cnn_service
from app.services.metrics_service import cv_summary
from app.services.split_service import jumlah_label_basi
from app.uploads import UploadError, validate_image

PASSWORD = 'uji-password-123'


def _token(html):
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


def _png_bytes():
    buf = io.BytesIO()
    Image.new('RGB', (8, 8), 'red').save(buf, 'PNG')
    return buf.getvalue()


class P1Test(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.tag = uuid.uuid4().hex[:8]
        with cls.app.app_context():
            u = Pengguna(nama='Uji admin', email=f'p1-{cls.tag}@example.test', role='admin')
            u.set_password(PASSWORD)
            db.session.add(u)
            db.session.commit()
            cls.user_id, cls.email = u.id, u.email
            fotos = (db.session.query(DokumentasiFoto.id, DokumentasiFoto.lokasi_id)
                     .order_by(DokumentasiFoto.id).limit(6).all())
        assert len(fotos) == 6, 'butuh minimal 6 foto di database (jalankan seed_data.py)'
        cls.fotos = fotos

    def setUp(self):
        self.split_ids, self.arsi_ids, self.label_ids = [], [], []

    def tearDown(self):
        with self.app.app_context():
            for aid in self.arsi_ids:
                PrediksiModel.query.filter_by(arsitektur_id=aid).delete()
                ArsitekturConfig.query.filter_by(id=aid).delete()
            for sid in self.split_ids:
                SplitItem.query.filter_by(config_id=sid).delete()
                SplitConfig.query.filter_by(id=sid).delete()
            for lid in self.label_ids:
                LabelKerusakan.query.filter_by(id=lid).delete()
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            Pengguna.query.filter_by(id=cls.user_id).delete()
            db.session.commit()

    # ── helpers ────────────────────────────────────────────────
    def client(self):
        c = self.app.test_client()
        tok = _token(c.get('/auth/login').get_data(as_text=True))
        r = c.post('/auth/login', data={'email': self.email, 'password': PASSWORD, 'csrf_token': tok})
        self.assertEqual(r.status_code, 302)
        return c

    def make_split(self, nama='uji'):
        with self.app.app_context():
            sp = SplitConfig(nama=f'{nama}-{self.tag}', split_type='kfold', n_splits=3, random_state=1,
                             label_sumber='tingkat', total_data=0, pengguna_id=self.user_id)
            db.session.add(sp)
            db.session.commit()
            self.split_ids.append(sp.id)
            return sp.id

    def make_arsitektur(self, split_id, status='draft', pred_type='none'):
        with self.app.app_context():
            a = ArsitekturConfig(nama=f'uji-{self.tag}', split_config_id=split_id, status=status,
                                 pred_type=pred_type, pengguna_id=self.user_id)
            db.session.add(a)
            db.session.commit()
            self.arsi_ids.append(a.id)
            return a.id

    def add_item(self, split_id, foto, fold, tingkat):
        with self.app.app_context():
            db.session.add(SplitItem(config_id=split_id, dokumentasi_id=foto[0],
                                     tingkat_kerusakan_id=tingkat, fold_index=fold))
            db.session.commit()

    def add_label(self, lokasi_id, tingkat):
        with self.app.app_context():
            assert LabelKerusakan.query.filter_by(lokasi_id=lokasi_id).first() is None, \
                'lokasi uji sudah punya label nyata; tes dihentikan agar data tidak tertimpa'
            lb = LabelKerusakan(lokasi_id=lokasi_id, tingkat_kerusakan_id=tingkat, pengguna_id=self.user_id)
            db.session.add(lb)
            db.session.commit()
            self.label_ids.append(lb.id)

    # ── split basi ─────────────────────────────────────────────
    def test_jumlah_label_basi(self):
        sid = self.make_split()
        foto = self.fotos[0]
        self.add_label(foto[1], tingkat=1)
        self.add_item(sid, foto, fold=0, tingkat=2)     # kelas tersimpan beda dari label
        with self.app.app_context():
            self.assertEqual(jumlah_label_basi(sid), 1)
            LabelKerusakan.query.filter_by(id=self.label_ids[0]).update({'tingkat_kerusakan_id': 2})
            db.session.commit()
            self.assertEqual(jumlah_label_basi(sid), 0)

    def test_train_refused_when_split_stale(self):
        sid = self.make_split()
        foto = self.fotos[0]
        self.add_label(foto[1], tingkat=1)
        self.add_item(sid, foto, fold=0, tingkat=3)
        aid = self.make_arsitektur(sid)
        c = self.client()
        tok = _token(c.get('/arsitektur/').get_data(as_text=True))
        with mock.patch('app.controllers.arsitektur_controller.threading.Thread') as thread:
            c.post(f'/arsitektur/{aid}/train', data={'csrf_token': tok})
            thread.assert_not_called()
        with self.app.app_context():
            self.assertEqual(db.session.get(ArsitekturConfig, aid).status, 'draft')

    # ── start ganda ────────────────────────────────────────────
    def test_double_start_is_refused(self):
        sid = self.make_split()                       # tanpa item → tidak dianggap basi
        aid = self.make_arsitektur(sid, status='training')
        c = self.client()
        tok = _token(c.get('/arsitektur/').get_data(as_text=True))
        with mock.patch('app.controllers.arsitektur_controller.threading.Thread') as thread:
            r = c.post(f'/arsitektur/{aid}/train', data={'csrf_token': tok})
            self.assertEqual(r.status_code, 302)
            thread.assert_not_called()
        with self.app.app_context():
            self.assertEqual(db.session.get(ArsitekturConfig, aid).status, 'training')

    def test_single_start_claims_status(self):
        sid = self.make_split()
        aid = self.make_arsitektur(sid, status='draft')
        c = self.client()
        tok = _token(c.get('/arsitektur/').get_data(as_text=True))
        with mock.patch('app.controllers.arsitektur_controller.threading.Thread') as thread:
            c.post(f'/arsitektur/{aid}/train', data={'csrf_token': tok})
            thread.assert_called_once()
        with self.app.app_context():
            self.assertEqual(db.session.get(ArsitekturConfig, aid).status, 'training')

    def test_tandai_training_terputus(self):
        from app.controllers.arsitektur_controller import tandai_training_terputus
        sid = self.make_split()
        aid = self.make_arsitektur(sid, status='training')
        with self.app.app_context():
            # commit diganti flush lalu rollback: server yang sedang berjalan tidak ikut terpengaruh
            with mock.patch.object(db.session, 'commit', db.session.flush):
                self.assertGreaterEqual(tandai_training_terputus(), 1)
                self.assertEqual(db.session.get(ArsitekturConfig, aid).status, 'gagal')
            db.session.rollback()
            self.assertEqual(db.session.get(ArsitekturConfig, aid).status, 'training')

    # ── ekspor CSV ─────────────────────────────────────────────
    def test_export_filename_is_sanitized(self):
        with self.app.app_context():
            sp = SplitConfig(nama='a"b\r\nX-Evil: 1/../x', split_type='kfold', n_splits=3, random_state=1,
                             label_sumber='tingkat', total_data=0, pengguna_id=self.user_id)
            db.session.add(sp)
            db.session.commit()
            self.split_ids.append(sp.id)
        r = self.client().get(f'/split/{self.split_ids[0]}/export')
        self.assertEqual(r.status_code, 200)
        disp = r.headers['Content-Disposition']
        self.assertRegex(disp, r'^attachment; filename="[A-Za-z0-9_.\-]+\.csv"$')
        self.assertNotIn('X-Evil', r.headers)

    # ── upload & klasifikasi ───────────────────────────────────
    def test_validate_image(self):
        ok = FileStorage(io.BytesIO(_png_bytes()), filename='a.png')
        validate_image(ok)
        self.assertEqual(ok.stream.tell(), 0)
        with self.assertRaises(UploadError):
            validate_image(FileStorage(io.BytesIO(b'bukan gambar'), filename='a.jpg'))
        with self.assertRaises(UploadError):
            validate_image(FileStorage(io.BytesIO(_png_bytes()), filename='a.exe'))

    def test_klasifikasi_rejects_bad_location_and_missing_model(self):
        c = self.client()
        tok = _token(c.get('/klasifikasi/upload').get_data(as_text=True))
        with self.app.app_context():
            n_foto = DokumentasiFoto.query.count()
            model_ada = cnn_service.best_model() is not None
        r = c.post('/klasifikasi/upload', data={'csrf_token': tok, 'lokasi_id': '999999',
                                                'foto': (io.BytesIO(_png_bytes()), 'a.png')},
                   content_type='multipart/form-data')
        self.assertEqual(r.status_code, 200)
        self.assertIn('lokasi yang valid', r.get_data(as_text=True))
        if not model_ada:   # tanpa model terlatih: tidak boleh ada data acak yang tersimpan
            r = c.post('/klasifikasi/upload', data={'csrf_token': tok, 'lokasi_id': str(self.fotos[0][1]),
                                                    'foto': (io.BytesIO(_png_bytes()), 'a.png')},
                       content_type='multipart/form-data')
            self.assertIn('Belum ada model terlatih', r.get_data(as_text=True))
        with self.app.app_context():
            self.assertEqual(DokumentasiFoto.query.count(), n_foto)

    # ── ringkasan CV ───────────────────────────────────────────
    def test_cv_summary(self):
        sid = self.make_split()
        aid = self.make_arsitektur(sid, status='selesai', pred_type='cv')
        # 6 foto, 2 fold: fold 1 benar 2 dari 3, fold 2 benar 1 dari 3
        aktual = [0, 1, 2, 0, 1, 2]
        pred = [0, 1, 0, 0, 0, 0]
        with self.app.app_context():
            for i, foto in enumerate(self.fotos):
                db.session.add(SplitItem(config_id=sid, dokumentasi_id=foto[0],
                                         tingkat_kerusakan_id=aktual[i] + 1, fold_index=i // 3))
                db.session.add(PrediksiModel(arsitektur_id=aid, dokumentasi_id=foto[0],
                                             prediksi=pred[i], aktual=aktual[i], confidence=90))
            db.session.commit()
            res = cv_summary(db.session.get(ArsitekturConfig, aid))
            self.assertEqual(res['n'], 6)
            self.assertEqual(res['akurasi'], 50.0)          # 3 dari 6 benar
            self.assertEqual([f['akurasi'] for f in res['per_fold']], [66.7, 33.3])
            self.assertEqual(res['baseline'], 33.3)
            self.assertEqual(res['recall']['berat'], 100.0)
            self.assertEqual(res['recall']['ringan'], 0.0)
            c = self.client()
            for path in (f'/arsitektur/{aid}', f'/arsitektur/{aid}/gis'):
                page = c.get(path)
                self.assertEqual(page.status_code, 200, path)
                self.assertIn('Cross Validation', page.get_data(as_text=True), path)
            single = db.session.get(ArsitekturConfig, aid)
            single.pred_type = 'single'
            self.assertIsNone(cv_summary(single))
            db.session.rollback()

    def test_best_model_none_without_evaluation(self):
        sid = self.make_split()
        self.make_arsitektur(sid, status='selesai')      # selesai tapi tanpa HasilEvaluasi
        with self.app.app_context():
            hit = cnn_service.best_model()
            self.assertTrue(hit is None or hit.id not in self.arsi_ids)


    # ── model final (semua data) ───────────────────────────────
    def _post_final(self, aid):
        c = self.client()
        tok = _token(c.get('/arsitektur/').get_data(as_text=True))
        with mock.patch('app.controllers.arsitektur_controller.threading.Thread') as thread:
            c.post(f'/arsitektur/{aid}/train-final', data={'csrf_token': tok})
        return thread

    def test_train_final_requires_finished_model(self):
        aid = self.make_arsitektur(self.make_split(), status='draft')
        self._post_final(aid).assert_not_called()

    def test_train_final_no_double_start(self):
        from app.controllers import arsitektur_controller as ac
        aid = self.make_arsitektur(self.make_split(), status='selesai')
        ac._final_progress[aid] = True
        try:
            self._post_final(aid).assert_not_called()
        finally:
            ac._final_progress.pop(aid, None)

    def test_train_final_starts_once(self):
        from app.controllers import arsitektur_controller as ac
        aid = self.make_arsitektur(self.make_split(), status='selesai')
        try:
            self._post_final(aid).assert_called_once()
            self.assertIn(aid, ac._final_progress)
        finally:
            ac._final_progress.pop(aid, None)

    def test_predict_image_prefers_final_model(self):
        fake = mock.Mock()
        fake.predict.return_value = np.array([[0.1, 0.7, 0.2]])
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as f:
            f.write(_png_bytes())
        try:
            cfg = SimpleNamespace(final_model_path='models/m_final.keras', model_path='models/m.keras', input_size=8)
            with mock.patch.object(cnn_service.prediction, '_load_cached', return_value=fake) as load:
                kelas, conf = cnn_service.predict_image(cfg, f.name, 'X')
                self.assertTrue(load.call_args[0][0].replace(os.sep, '/').endswith('static/models/m_final.keras'))
                self.assertEqual(kelas, 1)
                self.assertAlmostEqual(conf, 0.7, places=5)
                cfg.final_model_path = None
                cnn_service.predict_image(cfg, f.name, 'X')
                self.assertTrue(load.call_args[0][0].replace(os.sep, '/').endswith('static/models/m.keras'))
        finally:
            os.remove(f.name)


if __name__ == '__main__':
    unittest.main()
