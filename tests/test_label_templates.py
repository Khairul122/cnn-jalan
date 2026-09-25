"""Menjaga setiap route labeling benar-benar merender HTML.

py_compile hanya memeriksa sintaks Python, tidak pernah menyentuh template.
Test ini menutup celah itu pada kondisi terisi maupun kosong.

  .\\.venv\\Scripts\\python.exe -m unittest tests.test_label_templates -v
"""
import json
import os
import re
import tempfile
import unittest

from app import create_app, db
from app.models.hasil_labeling import HasilLabeling
from app.models.hasil_labeling_item import HasilLabelingItem
from app.models.labeling_config import LabelingConfig
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.pengguna import Pengguna
from app.models.tingkat_kerusakan import TingkatKerusakan

PASSWORD = 'uji-password-123'
LEVELS = [
    (1, 'Rusak Berat', 4),
    (2, 'Rusak Ringan', 3),
    (3, 'Sedang', 2),
    (4, 'Baik', 1),
]


def _token(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, 'token CSRF tidak ditemukan di halaman login'
    return match.group(1)


class LabelTemplateRenderTest(unittest.TestCase):
    def setUp(self):
        self.database = tempfile.NamedTemporaryFile(suffix='.sqlite', delete=False)
        self.database.close()
        os.environ['DATABASE_URL'] = f'sqlite:///{self.database.name}'
        os.environ['SECRET_KEY'] = 'label-template-secret'
        self.app = create_app()
        with self.app.app_context():
            db.create_all()
            user = Pengguna(nama='Admin Uji', email='template@example.test', role='admin')
            user.set_password(PASSWORD)
            db.session.add(user)
            for level_id, name, score in LEVELS:
                db.session.add(
                    TingkatKerusakan(
                        id=level_id, nama_tingkat=name,
                        warna_peta='#123456', skor_prioritas=score,
                    )
                )
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
        os.unlink(self.database.name)

    def _client(self):
        client = self.app.test_client()
        token = _token(client.get('/auth/login').get_data(as_text=True))
        response = client.post(
            '/auth/login',
            data={'email': 'template@example.test', 'password': PASSWORD, 'csrf_token': token},
        )
        self.assertEqual(response.status_code, 302, 'login gagal')
        return client

    def _seed_content(self):
        with self.app.app_context():
            config = LabelingConfig(
                nama_config='Default Uji', pengguna_id=self.user_id, is_default=True
            )
            lokasi = LokasiKerusakan(
                nama_citra='uji-1.jpg', latitude=1, longitude=2, pengguna_id=self.user_id
            )
            db.session.add_all([config, lokasi])
            db.session.commit()
            run = HasilLabeling(
                config_id=config.id, pengguna_id=self.user_id, jumlah_lokasi=1,
                jumlah_dilewati=0, variansi_pca=0.9,
                distribusi_kelas=json.dumps({'Baik': 1}), status='selesai',
            )
            db.session.add(run)
            db.session.flush()
            db.session.add(HasilLabelingItem(
                run_id=run.id, lokasi_id=lokasi.id, klaster=0,
                kepadatan_tepi=0.2, jarak_centroid=0.4, tingkat_kerusakan_id=4,
            ))
            db.session.commit()
            return lokasi.id, run.id

    def test_pages_render_with_data(self):
        lokasi_id, run_id = self._seed_content()
        client = self._client()
        pages = [
            '/label/',
            f'/label/{lokasi_id}/edit',
            '/label/config/new',
            f'/label/review/{run_id}',
        ]
        for path in pages:
            with self.subTest(path=path):
                response = client.get(path)
                self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:500])

    def test_index_renders_empty_state_without_data(self):
        client = self._client()
        response = client.get('/label/')
        self.assertEqual(response.status_code, 200)
        body = response.get_data(as_text=True)
        self.assertIn('Belum ada konfigurasi', body)
        self.assertIn('Belum ada lokasi jalan', body)

    def test_review_page_renders_applied_run_without_apply_controls(self):
        lokasi_id, run_id = self._seed_content()
        with self.app.app_context():
            run = db.session.get(HasilLabeling, run_id)
            run.is_diterapkan = True
            db.session.commit()

        client = self._client()
        body = client.get(f'/label/review/{run_id}').get_data(as_text=True)
        self.assertNotIn('/buang', body, 'run yang sudah diterapkan tidak boleh menawarkan buang')


if __name__ == '__main__':
    unittest.main()
