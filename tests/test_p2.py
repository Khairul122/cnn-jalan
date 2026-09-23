import os
import tempfile
import unittest

import numpy as np
from openpyxl import Workbook

from app.models.label_kerusakan import LabelKerusakan
from app.services import cnn_service
from app.services.split_service import SplitService
from scripts.seed_data import read_excel


class P2Test(unittest.TestCase):
    def test_hitung_sdi(self):
        self.assertEqual(LabelKerusakan.hitung_sdi(0, 'halus', 0, 0), 0)
        self.assertEqual(LabelKerusakan.hitung_sdi(15, 'lebar', 12, 2), 135)

    def test_tingkat_dari_sdi(self):
        self.assertEqual(LabelKerusakan.tingkat_dari_sdi(50), 3)
        self.assertEqual(LabelKerusakan.tingkat_dari_sdi(150), 2)
        self.assertEqual(LabelKerusakan.tingkat_dari_sdi(150.01), 1)

    def test_split_service_is_stratified_and_deterministic(self):
        items = [{'dokumentasi_id': index, 'label_id': index % 3} for index in range(12)]
        first = SplitService.run(3, 42, items)
        second = SplitService.run(3, 42, items)

        self.assertEqual(first, second)
        distribution = SplitService.distribusi(first, {})
        self.assertEqual(
            {fold: dict(labels) for fold, labels in distribution.items()},
            {0: {0: 2, 1: 1, 2: 1}, 1: {0: 1, 1: 2, 2: 1}, 2: {0: 1, 1: 1, 2: 2}},
        )

    def test_read_excel_validates_and_maps_rows(self):
        path = os.path.join('tests', 'p2-valid.xlsx')
        try:
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(['Citra', 'x', 'y', 'P', 'L', 'Ket'])
            sheet.append(['foto-1', -5.1, 97.2, 2, 0.5, 'Ukur'])
            workbook.save(path)

            self.assertEqual(read_excel(path), [{
                'nama_citra': 'foto-1',
                'latitude': -5.1,
                'longitude': 97.2,
                'panjang': 2.0,
                'lebar': 0.5,
                'keterangan': 'Ukur',
            }])
        finally:
            if os.path.exists(path):
                os.remove(path)

    def test_group_aware_split_never_splits_a_group(self):
        # 20 foto, 4 varian tahap per foto (id foto = grup) → 80 sampel
        groups, labels = [], []
        for foto_id in range(20):
            label = foto_id % 3
            for _variant in range(4):
                groups.append(foto_id)
                labels.append(label)

        idx_fit, idx_inner = cnn_service._group_aware_split(
            groups, labels, test_size=0.15, seed=42)

        groups_fit = {groups[i] for i in idx_fit}
        groups_inner = {groups[i] for i in idx_inner}

        self.assertEqual(len(idx_fit) + len(idx_inner), len(groups))
        self.assertEqual(groups_fit & groups_inner, set())
        # Tiap foto full (semua 4 variannya) ada di tepat satu sisi
        for foto_id in groups_fit:
            self.assertEqual([groups[i] for i in idx_fit].count(foto_id), 4)
        for foto_id in groups_inner:
            self.assertEqual([groups[i] for i in idx_inner].count(foto_id), 4)

    def test_is_better_checkpoint_prefers_accuracy_over_loss(self):
        # Kandidat akurasi lebih tinggi menang meski val_loss-nya lebih tinggi juga
        # (reproduksi kasus nyata: loss terus turun tapi akurasi tidak ikut membaik).
        self.assertTrue(cnn_service._is_better_checkpoint(
            cand_acc=0.45, cand_loss=1.05, best_acc=0.33, best_loss=1.02))
        self.assertFalse(cnn_service._is_better_checkpoint(
            cand_acc=0.30, cand_loss=1.00, best_acc=0.45, best_loss=1.05))

    def test_is_better_checkpoint_uses_loss_as_tiebreaker(self):
        # Akurasi sama persis -> pilih yang val_loss-nya lebih rendah
        self.assertTrue(cnn_service._is_better_checkpoint(
            cand_acc=0.40, cand_loss=0.90, best_acc=0.40, best_loss=1.10))
        self.assertFalse(cnn_service._is_better_checkpoint(
            cand_acc=0.40, cand_loss=1.10, best_acc=0.40, best_loss=0.90))

    def test_predict_with_tta_averages_original_and_flipped(self):
        class FakeModel:
            def predict(self, batch, verbose=0):
                # baris 0 = gambar asli -> [1,0,0]; baris 1 = flip -> [0,1,0]
                return np.array([[1.0, 0.0, 0.0], [0.0, 1.0, 0.0]])

        img = np.zeros((4, 4, 3), dtype=np.float32)
        img[:, 0, :] = 9   # kolom kiri beda dari kanan -> flip menghasilkan array berbeda

        probs = cnn_service._predict_with_tta(FakeModel(), img)
        np.testing.assert_allclose(probs, [0.5, 0.5, 0.0])

    def test_predict_probs_with_averages_across_ensemble_models(self):
        class FakeModel:
            def __init__(self, value):
                self.value = value

            def predict(self, batch, verbose=0):
                return np.tile(self.value, (len(batch), 1))

        models = [FakeModel([1.0, 0.0, 0.0]), FakeModel([0.0, 0.0, 1.0])]
        img = np.zeros((4, 4, 3), dtype=np.float32)

        probs = cnn_service._predict_probs_with(models, img)
        np.testing.assert_allclose(probs, [0.5, 0.0, 0.5])

    def test_read_excel_rejects_duplicate_or_invalid_rows(self):
        path = os.path.join('tests', 'p2-invalid.xlsx')
        try:
            workbook = Workbook()
            sheet = workbook.active
            sheet.append(['Citra', 'x', 'y', 'P', 'L', 'Ket'])
            sheet.append(['foto-1', -5.1, 97.2, 2, 0.5, 'Ukur'])
            sheet.append(['foto-1', 'invalid', 97.2, 2, 0.5, 'Ukur'])
            workbook.save(path)

            with self.assertRaisesRegex(ValueError, 'Excel tidak valid'):
                read_excel(path)
        finally:
            if os.path.exists(path):
                os.remove(path)


if __name__ == '__main__':
    unittest.main()
