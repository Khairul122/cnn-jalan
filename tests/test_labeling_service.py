import tempfile
import unittest
from types import SimpleNamespace
from unittest import mock

import numpy as np

from app import create_app, db
from app.models.tingkat_kerusakan import TingkatKerusakan
from app.services import labeling_service
from tests.isolated_app import make_isolated_app, release_isolated_app


class LabelingServiceContractTest(unittest.TestCase):
    def test_default_configuration_matches_validated_notebook(self):
        defaults = labeling_service.DEFAULTS

        self.assertEqual(defaults.image_size, (224, 224))
        self.assertEqual(defaults.canny_low, 50)
        self.assertEqual(defaults.canny_high, 150)
        self.assertEqual(defaults.pca_components, 50)
        self.assertEqual(defaults.n_clusters, 4)
        self.assertEqual(defaults.random_state, 42)
        self.assertEqual(defaults.n_init, 10)

    def test_cluster_order_maps_lowest_edges_to_good_and_highest_to_heavy_damage(self):
        feature_map = {
            10: {'kepadatan_tepi': 0.10},
            11: {'kepadatan_tepi': 0.30},
            12: {'kepadatan_tepi': 0.50},
            13: {'kepadatan_tepi': 0.90},
        }
        clusters = {
            10: {'klaster': 2},
            11: {'klaster': 0},
            12: {'klaster': 3},
            13: {'klaster': 1},
        }

        app, database_path = make_isolated_app('labeling-service-secret')
        try:
            with app.app_context():
                db.create_all()
                levels = {
                    'Baik': 4,
                    'Sedang': 3,
                    'Rusak Ringan': 2,
                    'Rusak Berat': 1,
                }
                for name, level_id in levels.items():
                    db.session.add(
                        TingkatKerusakan(
                            id=level_id, nama_tingkat=name, warna_peta='#000000', skor_prioritas=level_id
                        )
                    )
                db.session.commit()
                mapping = labeling_service.urutkan_klaster_ke_tingkat(clusters, feature_map)
        finally:
            release_isolated_app(app, database_path)

        self.assertEqual(mapping, {0: 3, 1: 1, 2: 4, 3: 2})

    def test_clusterization_is_deterministic_for_same_random_state(self):
        feature_map = {
            index: {
                'embedding': np.array([float(index), float(index % 2)]),
                'kepadatan_tepi': index / 10,
            }
            for index in range(8)
        }

        first, first_variance = labeling_service.klasterisasi(
            feature_map, n_cluster=2, pca_komponen=2, random_state=42
        )
        second, second_variance = labeling_service.klasterisasi(
            feature_map, n_cluster=2, pca_komponen=2, random_state=42
        )

        self.assertEqual(first, second)
        self.assertEqual(first_variance, second_variance)

    def test_location_feature_extraction_skips_missing_images_with_reason(self):
        with tempfile.TemporaryDirectory() as folder:
            locations = [
                SimpleNamespace(
                    id=1,
                    foto_list=[SimpleNamespace(path_file='uploads/foto/absent.jpg')],
                ),
                SimpleNamespace(id=2, foto_list=[]),
            ]

            features, skipped = labeling_service.ekstrak_fitur_lokasi(locations, folder)

        self.assertEqual(features, {})
        self.assertEqual({row['lokasi_id'] for row in skipped}, {1, 2})
        self.assertTrue(all(row['alasan'] for row in skipped))


if __name__ == '__main__':
    unittest.main()
