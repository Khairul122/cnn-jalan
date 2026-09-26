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
                     '/augmentasi/progress/<int:config_id>'):
            self.assertIn(rule, rules)

    def test_progress_preprocessing_json_safe(self):
        pc._progress.clear()
        pc._simpan_progress(7, {'status': 'running', 'pct': 50, 'current': 14, 'total': 28})
        prog = pc._progress_aktif(7)
        json.dumps(prog)                       # ValueError bila ada objek non-JSON
        self.assertEqual(prog['pct'], 50)

    def test_selesaikan_menyimpan_reload(self):
        from app import create_app
        pc._progress.clear()
        app = create_app()
        with app.test_request_context():       # url_for butuh context request, sama seperti thread
            pc._selesaikan(9)
        prog = pc._progress_aktif(9)
        self.assertEqual(prog['status'], 'selesai')
        self.assertTrue(prog['reload'].endswith('proses=selesai'))

    def test_progress_label_json_safe(self):
        lc._progress.clear()
        lc._progress[1] = {'config_id': 3, 'status': 'running', 'pct': None, 'step': 'x'}
        json.dumps(next(iter(lc._progress.values())))
        lc._progres(1, pct=40, status='running')
        self.assertEqual(lc._progress[1]['pct'], 40)

    def test_progress_augmentasi_json_safe(self):
        ac._progress.clear()
        ac._simpan_progress(2, {'status': 'running', 'pct': 10, 'current': 28, 'total': 280})
        self.assertEqual(json.dumps(ac._sisa_progress(2))[0], '{')


if __name__ == '__main__':
    unittest.main()
