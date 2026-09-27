"""Hasil run klasterisasi harus langsung jadi label tanpa klik "Terapkan".

Regression test untuk bug: halaman /split/new hanya membaca `label_kerusakan`
(padahal tabel itu hanya terisi oleh endpoint Terapkan), sehingga tombol "Buat Split K-Fold"
tetap `disabled` meski labeling sudah selesai — dan begitu training dicek,
`jumlah_label_basi` ikut menghitung 280 item sebagai "label berubah".

Jalankan: .\\.venv\\Scripts\\python.exe -m unittest tests.test_label_source -v
"""
import json
import re
import unittest

from app import db
from app.controllers.split_controller import _get_labeled_items
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.hasil_labeling import HasilLabeling
from app.models.hasil_labeling_item import HasilLabelingItem
from app.models.label_kerusakan import LabelKerusakan
from app.models.labeling_config import LabelingConfig
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.pengguna import Pengguna
from app.models.split_config import SplitConfig
from app.models.split_item import SplitItem
from app.models.tingkat_kerusakan import TingkatKerusakan
from app.services import label_source
from app.services.split_service import jumlah_label_basi
from tests.isolated_app import make_isolated_app, release_isolated_app

PASSWORD = 'uji-password-123'
LEVELS = [
    (1, 'Rusak Berat', 4),
    (2, 'Rusak Ringan', 3),
    (3, 'Sedang', 2),
    (4, 'Baik', 1),
]
# lokasi_id relatif → tingkat tiap run (di-resolve oleh _buat_run)
RUN_A = [1, 2, 4]


def _token(html):
    match = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert match, 'token CSRF tidak ditemukan di halaman login'
    return match.group(1)


class LabelSourceTest(unittest.TestCase):
    def setUp(self):
        self.app, self.database_path = make_isolated_app('label-source-secret')
        with self.app.app_context():
            db.create_all()
            user = Pengguna(nama='Admin Uji', email='label-source@example.test', role='admin')
            user.set_password(PASSWORD)
            db.session.add(user)
            for level_id, name, score in LEVELS:
                db.session.add(TingkatKerusakan(
                    id=level_id, nama_tingkat=name, warna_peta='#123456', skor_prioritas=score,
                ))
            db.session.commit()
            self.user_id = user.id

            db.session.add(LabelingConfig(
                nama_config='Konfigurasi Uji', pengguna_id=self.user_id, is_default=True,
            ))
            db.session.commit()

            self.lokasi_ids, self.foto_ids = [], []
            for n in range(3):
                lokasi = LokasiKerusakan(
                    nama_citra=f'uji-{n}.jpg', latitude=5.18, longitude=97.14,
                    pengguna_id=self.user_id,
                )
                db.session.add(lokasi)
                db.session.flush()
                db.session.add(DokumentasiFoto(
                    lokasi_id=lokasi.id, nama_file=f'uji-{n}.jpg',
                    path_file=f'uploads/foto/uji-{n}.jpg',
                ))
                self.lokasi_ids.append(lokasi.id)
            db.session.commit()
            self.foto_ids = [r.id for r in db.session.query(DokumentasiFoto.id).all()]

    def tearDown(self):
        release_isolated_app(self.app, self.database_path)

    def _buat_run(self, tingkat_per_lokasi, status='selesai'):
        """Run klasterisasi baru; `tingkat_per_lokasi` sepanjang self.lokasi_ids."""
        with self.app.app_context():
            config = LabelingConfig.query.one()
            run = HasilLabeling(
                config_id=config.id, pengguna_id=self.user_id, jumlah_lokasi=len(self.lokasi_ids),
                jumlah_dilewati=0, variansi_pca=0.9,
                distribusi_kelas=json.dumps({'uji': len(self.lokasi_ids)}), status=status,
            )
            db.session.add(run)
            db.session.flush()
            for lokasi_id, tingkat in zip(self.lokasi_ids, tingkat_per_lokasi):
                db.session.add(HasilLabelingItem(
                    run_id=run.id, lokasi_id=lokasi_id, klaster=0,
                    kepadatan_tepi=0.2, jarak_centroid=0.4, tingkat_kerusakan_id=tingkat,
                ))
            db.session.commit()
            return run.id

    def _client(self):
        client = self.app.test_client()
        token = _token(client.get('/auth/login').get_data(as_text=True))
        response = client.post('/auth/login', data={
            'email': 'label-source@example.test', 'password': PASSWORD, 'csrf_token': token,
        })
        self.assertEqual(response.status_code, 302, 'login gagal')
        return client

    def _buat_split(self, tingkat_per_lokasi):
        """Split yang kelasnya diambil dari run, seperti split.new hasilnya."""
        with self.app.app_context():
            split = SplitConfig(
                nama='uji-split', n_splits=3, random_state=42, label_sumber='tingkat',
                total_data=len(self.foto_ids), pengguna_id=self.user_id,
            )
            db.session.add(split)
            db.session.flush()
            for fold, (foto_id, tingkat) in enumerate(
                zip(self.foto_ids, tingkat_per_lokasi)
            ):
                db.session.add(SplitItem(
                    config_id=split.id, dokumentasi_id=foto_id,
                    tingkat_kerusakan_id=tingkat, fold_index=fold % 3,
                ))
            db.session.commit()
            return split.id

    # ── inti bug ───────────────────────────────────────────────
    def test_run_selesai_jadi_label_tanpa_klik_terapkan(self):
        self._buat_run(RUN_A)
        with self.app.app_context():
            self.assertEqual(LabelKerusakan.query.count(), 0,
                             'prasyarat: Terapkan belum dijalankan')
            labels = label_source.label_map()
            self.assertEqual(labels, dict(zip(self.lokasi_ids, RUN_A)))

            items = _get_labeled_items()
            self.assertEqual(len(items), 3, 'split harus melihat 3 foto berlabel')
            self.assertEqual([i['label_id'] for i in items], RUN_A)

    def test_tombol_buat_split_aktif(self):
        self._buat_run(RUN_A)
        response = self._client().get('/split/new')
        self.assertEqual(response.status_code, 200, response.get_data(as_text=True)[:500])
        body = response.get_data(as_text=True)
        self.assertIn('3 foto berlabel', body)
        self.assertNotIn('class="btn btn--primary" disabled', body,
                         'tombol Buat Split K-Fold masih disabled')

    def test_dashboard_hitung_label_dari_run(self):
        self._buat_run(RUN_A)
        body = self._client().get('/dashboard').get_data(as_text=True)
        self.assertIn('data-val="3"', body, 'KPI "berlabel" dashboard tidak ikut berubah')

    def test_label_basi_nol_selama_run_tidak_berubah(self):
        run_id = self._buat_run(RUN_A)
        split_id = self._buat_split(RUN_A)
        with self.app.app_context():
            self.assertEqual(jumlah_label_basi(split_id), 0,
                             'training akan ditolak sebagai "label berubah"')

            item = HasilLabelingItem.query.filter_by(
                run_id=run_id, lokasi_id=self.lokasi_ids[0]).one()
            item.tingkat_kerusakan_id = 3
            db.session.commit()
            self.assertEqual(jumlah_label_basi(split_id), 1,
                             'run berubah → item split yang kelasnya beda harus ditandai basi')

    # ── aturan prioritas ───────────────────────────────────────
    def test_label_manual_mengalahkan_run(self):
        self._buat_run(RUN_A)
        with self.app.app_context():
            db.session.add(LabelKerusakan(
                lokasi_id=self.lokasi_ids[0], tingkat_kerusakan_id=3,
                metode='manual', pengguna_id=self.user_id,
            ))
            db.session.commit()
            labels = label_source.label_map()
            self.assertEqual(labels[self.lokasi_ids[0]], 3, 'override manual harus menang')
            self.assertEqual(labels[self.lokasi_ids[1]], RUN_A[1])

    def test_label_hasil_terapkan_dipakai_ketika_tidak_ada_run_selesai(self):
        with self.app.app_context():
            db.session.add(LabelKerusakan(
                lokasi_id=self.lokasi_ids[0], tingkat_kerusakan_id=2,
                metode='klasterisasi', pengguna_id=self.user_id,
            ))
            db.session.commit()
            self.assertEqual(label_source.label_map(), {self.lokasi_ids[0]: 2})

            # run yang masih 'proses' tidak boleh dihitung
            self._buat_run(RUN_A, status='proses')
            self.assertEqual(label_source.label_map(), {self.lokasi_ids[0]: 2})
            self.assertIsNone(label_source.active_run())

    def test_run_terbaru_mengalahkan_label_hasil_terapkan(self):
        with self.app.app_context():
            db.session.add(LabelKerusakan(
                lokasi_id=self.lokasi_ids[0], tingkat_kerusakan_id=2,
                metode='klasterisasi', pengguna_id=self.user_id,
            ))
            db.session.commit()
        self._buat_run(RUN_A)
        with self.app.app_context():
            self.assertEqual(label_source.label_map()[self.lokasi_ids[0]], RUN_A[0],
                             'hasil klasterisasi terbaru harus menimpa label Terapkan lama')


if __name__ == '__main__':
    unittest.main()
