import os
import tempfile
import unittest

import numpy as np
from openpyxl import Workbook

from app.services import cnn_service
from app.services.split_service import SplitService
from scripts.seed_data import read_excel


class P2Test(unittest.TestCase):
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

    def test_five_crop_flip_views_shape_and_flip_correctness(self):
        img = np.zeros((20, 20, 3), dtype=np.float32)
        img[:, :10, :] = 9   # separuh kiri beda dari kanan -> flip menghasilkan array berbeda

        views = cnn_service._five_crop_flip_views(img, crop_frac=0.875)

        self.assertEqual(len(views), 10)   # 5 crop x (asli + flip)
        for v in views:
            self.assertEqual(v.shape, img.shape)   # di-resize balik ke ukuran asli
        # tiap pasang (asli, flip) harus berbeda satu sama lain (crop kiri-kanan tidak simetris)
        for i in range(0, 10, 2):
            self.assertFalse(np.array_equal(views[i], views[i + 1]))
            np.testing.assert_allclose(views[i], views[i + 1][:, ::-1, :])

    def test_predict_with_tta_averages_all_views(self):
        class FakeModel:
            def predict(self, batch, verbose=0):
                self.last_batch_size = len(batch)
                # baris ganjil -> [1,0,0], baris genap -> [0,1,0] (independen dari isi gambar)
                return np.array([[1.0, 0.0, 0.0] if i % 2 == 0 else [0.0, 1.0, 0.0]
                                  for i in range(len(batch))])

        img = np.zeros((20, 20, 3), dtype=np.float32)
        img[:, :10, :] = 9

        model = FakeModel()
        probs = cnn_service._predict_with_tta(model, img)
        self.assertEqual(model.last_batch_size, 10)   # 5-crop x flip
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

    def test_mixup_dataset_yields_soft_labels_over_all_classes(self):
        from app.services.cnn_service.training import _mixup_dataset
        from app.kelas import N_KELAS
        X = np.random.RandomState(0).rand(16, 4, 4, 3).astype(np.float32)
        y = np.arange(16) % N_KELAS
        sw = np.array([0.5, 1.0, 1.5, 2.0] * 4, dtype=np.float32)
        ds = _mixup_dataset(X, y, sw, batch_size=4, alpha=0.4, n_classes=N_KELAS, seed=1)
        for xb, yb, wb in ds.take(3):
            self.assertEqual(xb.shape, (4, 4, 4, 3))
            self.assertEqual(yb.shape, (4, N_KELAS))
            np.testing.assert_allclose(yb.numpy().sum(axis=1), 1.0, atol=1e-5)   # tiap baris distribusi valid
            self.assertTrue(((wb.numpy() >= 0.5 - 1e-6) & (wb.numpy() <= 2.0 + 1e-6)).all())

    def test_loss_is_categorical_only_when_mixup_or_label_smoothing(self):
        from tensorflow import keras
        from app.services.cnn_service.model import _make_loss, uses_onehot_labels
        self.assertFalse(uses_onehot_labels(0, 0))
        self.assertTrue(uses_onehot_labels(0.2, 0))
        self.assertTrue(uses_onehot_labels(0, 0.1))
        self.assertIsInstance(_make_loss(0, 0), keras.losses.SparseCategoricalCrossentropy)
        self.assertIsInstance(_make_loss(0.2, 0), keras.losses.CategoricalCrossentropy)
        self.assertEqual(_make_loss(0, 0.1).label_smoothing, 0.1)

    def test_augmentation_layers_can_be_disabled_per_layer(self):
        from app.services.cnn_service.model import AUG_KEYS, _augmentation_layers, parse_aug_off
        self.assertEqual(len(_augmentation_layers()), len(AUG_KEYS))
        self.assertEqual(len(_augmentation_layers('zoom,erasing')), len(AUG_KEYS) - 2)
        self.assertEqual(_augmentation_layers(AUG_KEYS), [])
        self.assertEqual(parse_aug_off('zoom, erasing'), ('zoom', 'erasing'))
        self.assertEqual(parse_aug_off(''), ())
        with self.assertRaises(ValueError):
            parse_aug_off('zoom,tidak_ada')

    def test_hyperparams_cover_every_training_field_and_reach_train_final(self):
        from unittest import mock
        from app.models.arsitektur_config import ArsitekturConfig
        cfg = ArsitekturConfig(id=1, split_config_id=1, input_size=224, model_type='mobilenetv2', dropout_rate=0.3,
                               optimizer='adam', learning_rate=1e-4, batch_size=16, epochs=5, patience=5,
                               mixup_alpha=0.2, label_smoothing=0.1, dense_units=32, dense_l2=1e-3,
                               skip_fine_tuning=True, aug_off='zoom')
        hp = cnn_service.hyperparams(cfg)
        self.assertEqual(set(hp), set(cnn_service.training.HYPERPARAM_FIELDS))
        with mock.patch.object(cnn_service.training, 'train', return_value=('m', None)) as train:
            cnn_service.train_final(cfg, base_dir='.')
        dipakai = train.call_args.args[0]
        for k, v in hp.items():   # sebelumnya model final memakai default untuk field yang lupa disalin
            self.assertEqual(getattr(dipakai, k), v, k)

    def test_preprocessing_pipeline_has_four_steps_and_no_augmentation(self):
        from types import SimpleNamespace
        from PIL import Image
        from app.services.preprocessing_service import PreprocessingService
        cfg = SimpleNamespace(target_width=32, target_height=32, resize_method='LANCZOS', resize_mode='stretch',
                              illum_correction=False, crop_enabled=True, crop_width=24, crop_height=24,
                              norm_method='none', denoise_method='bilateral', denoise_ksize=3)
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, 'a.png')
            Image.new('RGB', (40, 30), 'gray').save(path)
            steps = PreprocessingService.run_pipeline_steps(path, cfg)
        self.assertEqual([k for k, _, _ in steps], ['resize', 'crop', 'normalisasi', 'denoise'])
        self.assertEqual(steps[0][1].size, (32, 32))
        self.assertEqual(steps[-1][1].size, (24, 24))


if __name__ == '__main__':
    unittest.main()
