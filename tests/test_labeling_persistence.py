import json
import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

from app import create_app, db
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.hasil_labeling import HasilLabeling
from app.models.hasil_labeling_item import HasilLabelingItem
from app.models.label_kerusakan import LabelKerusakan
from app.models.labeling_config import LabelingConfig
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.pengguna import Pengguna
from app.models.tingkat_kerusakan import TingkatKerusakan
from app.services import labeling_service
from tests.isolated_app import make_isolated_app, release_isolated_app


class LabelingPersistenceTest(unittest.TestCase):
    def setUp(self):
        self.app, self.database_path = make_isolated_app('labeling-test-secret')
        with self.app.app_context():
            db.create_all()
            self.user = Pengguna(nama='Admin Uji', email='labeling@example.test', role='admin')
            self.user.set_password('uji-password')
            db.session.add(self.user)
            db.session.add_all([
                TingkatKerusakan(id=1, nama_tingkat='Rusak Berat', warna_peta='#111111', skor_prioritas=4),
                TingkatKerusakan(id=2, nama_tingkat='Rusak Ringan', warna_peta='#222222', skor_prioritas=3),
                TingkatKerusakan(id=3, nama_tingkat='Sedang', warna_peta='#333333', skor_prioritas=2),
                TingkatKerusakan(id=4, nama_tingkat='Baik', warna_peta='#444444', skor_prioritas=1),
            ])
            db.session.commit()
            self.config = LabelingConfig(nama_config='Uji', pengguna_id=self.user.id)
            db.session.add(self.config)
            self.location = LokasiKerusakan(
                nama_citra='uji.jpg', latitude=1, longitude=2, pengguna_id=self.user.id
            )
            db.session.add(self.location)
            db.session.commit()
            self.user_id = self.user.id
            self.config_id = self.config.id
            self.location_id = self.location.id

    def tearDown(self):
        release_isolated_app(self.app, self.database_path)

    def test_run_persists_items_without_writing_labels(self):
        with self.app.app_context():
            features = {
                self.location_id: {'embedding': [1.0, 2.0], 'kepadatan_tepi': 0.2}
            }
            with mock.patch.object(labeling_service, 'ekstrak_fitur_lokasi', return_value=(features, [])), \
                 mock.patch.object(labeling_service, 'klasterisasi', return_value=({self.location_id: {
                     'klaster': 0, 'jarak_centroid': 0.4}}, 0.9)), \
                 mock.patch.object(labeling_service, 'urutkan_klaster_ke_tingkat', return_value={0: 4}):
                run = labeling_service.jalankan_klasterisasi(
                    self.config, self.app.config['UPLOAD_FOLDER'], self.user_id
                )

            self.assertEqual(run.status, 'selesai')
            self.assertFalse(run.is_diterapkan)
            self.assertEqual(run.item_list[0].tingkat_kerusakan_id, 4)
            self.assertIsNone(LabelKerusakan.query.filter_by(lokasi_id=self.location_id).first())

    def test_apply_upserts_and_is_idempotent(self):
        with self.app.app_context():
            run = HasilLabeling(
                config_id=self.config_id, pengguna_id=self.user_id,
                jumlah_lokasi=1, distribusi_kelas=json.dumps({'Baik': 1}),
            )
            db.session.add(run)
            db.session.flush()
            db.session.add(HasilLabelingItem(
                run_id=run.id, lokasi_id=self.location_id, klaster=0,
                kepadatan_tepi=0.2, jarak_centroid=0.4, tingkat_kerusakan_id=4,
            ))
            db.session.commit()

            self.assertEqual(labeling_service.terapkan_hasil(run), 1)
            first = LabelKerusakan.query.filter_by(lokasi_id=self.location_id).one()
            self.assertEqual(first.metode, 'klasterisasi')
            self.assertTrue(run.is_diterapkan)
            self.assertEqual(labeling_service.terapkan_hasil(run), 0)
            self.assertEqual(LabelKerusakan.query.filter_by(lokasi_id=self.location_id).count(), 1)

    def test_discard_removes_run_items_but_preserves_existing_label(self):
        with self.app.app_context():
            label = LabelKerusakan(
                lokasi_id=self.location_id, tingkat_kerusakan_id=3,
                metode='manual', pengguna_id=self.user_id,
            )
            db.session.add(label)
            run = HasilLabeling(
                config_id=self.config_id, pengguna_id=self.user_id, jumlah_lokasi=1
            )
            db.session.add(run)
            db.session.flush()
            db.session.add(HasilLabelingItem(
                run_id=run.id, lokasi_id=self.location_id, klaster=0,
                kepadatan_tepi=0.2, jarak_centroid=0.4, tingkat_kerusakan_id=4,
            ))
            db.session.commit()
            run_id = run.id

            labeling_service.buang_hasil(run)

            self.assertIsNone(db.session.get(HasilLabeling, run_id))
            self.assertEqual(LabelKerusakan.query.filter_by(lokasi_id=self.location_id).one().tingkat_kerusakan_id, 3)


if __name__ == '__main__':
    unittest.main()
