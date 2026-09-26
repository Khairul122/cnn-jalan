"""Self-check overlay progres: route progress ada, dan store progres thread-safe
hanya berisi data yang bisa di-JSON-kan (bukan objek SQLAlchemy / datetime).
Jalankan: .\\.venv\\Scripts\\python.exe -m unittest tests.test_loading_progress -v
"""
import json
import unittest

from app.controllers import augmentasi_controller as ac
from app.controllers import label_controller as lc
from app.controllers import preprocessing_controller as pc


class LoadingProgressTest(unittest.TestCase):

    def test_route_progress_ada(self):
        from app import create_app
        rules = {r.rule for r in create_app().url_map.iter_rules()}
        for rule in ('/label/progress/<int:config_id>',
                     '/preprocessing/progress/<int:config_id>',
                     '/augmentasi/progress/<int:config_id>',
                     '/split/progress',
                     '/klasifikasi/progress',
                     '/arsitektur/<int:config_id>/evaluasi-progress'):
            self.assertIn(rule, rules)

    def test_route_hapus_tersedia(self):
        """Setiap halaman proses punya route hapus untuk datanya."""
        from app import create_app
        rules = {r.rule for r in create_app().url_map.iter_rules()}
        for rule in ('/label/hapus-semua',
                     '/label/run/<int:run_id>/delete',
                     '/preprocessing/config/<int:config_id>/reset-hasil',
                     '/augmentasi/hasil/reset',
                     '/split/<int:config_id>/delete',
                     '/split/<int:config_id>/reset',
                     '/arsitektur/<int:config_id>/training-delete',
                     '/arsitektur/<int:config_id>/evaluasi-delete',
                     '/arsitektur/<int:config_id>/prediksi-delete',
                     '/klasifikasi/hasil/<int:hasil_id>/delete',
                     '/klasifikasi/riwayat/hapus-semua'):
            self.assertIn(rule, rules)

    def test_progress_store_thread_safe_dan_json_safe(self):
        from app.progress_store import ProgressStore
        s = ProgressStore()
        s.set(1, {'status': 'running', 'pct': 10, 'step': 'x'})
        s.sederhanakan(1, pct=60)
        prog = s.get(1)
        json.dumps(prog)                       # ValueError bila ada objek non-JSON
        self.assertEqual(prog['pct'], 60)
        self.assertEqual(prog['step'], 'x')    # field lain tetap
        s.pop(1)
        self.assertIsNone(s.get(1))

    def test_progress_preprocessing_json_safe(self):
        pc._progress.clear()
        pc._simpan_progress(7, {'status': 'running', 'pct': 50, 'current': 14, 'total': 28})
        prog = pc._progress_aktif(7)
        json.dumps(prog)                       # ValueError bila ada objek non-JSON
        self.assertEqual(prog['pct'], 50)

    def test_selesaikan_menyimpan_reload(self):
        pc._progress.clear()
        pc._selesaikan(9)                      # thread asli juga tanpa request context
        prog = pc._progress_aktif(9)
        self.assertEqual(prog['status'], 'selesai')
        self.assertTrue(prog['reload'].endswith('proses=selesai'))

    def test_progress_label_json_safe(self):
        lc._progress.clear()
        lc._progress.set(1, {'config_id': 3, 'status': 'running', 'pct': None, 'step': 'x'})
        json.dumps(lc._progress.get(1))
        lc._progres(1, pct=40, status='running')
        self.assertEqual(lc._progress.get(1)['pct'], 40)

    def test_progress_augmentasi_json_safe(self):
        ac._progress.clear()
        ac._simpan_progress(2, {'status': 'running', 'pct': 10, 'current': 28, 'total': 280})
        self.assertEqual(json.dumps(ac._sisa_progress(2))[0], '{')


if __name__ == '__main__':
    unittest.main()
