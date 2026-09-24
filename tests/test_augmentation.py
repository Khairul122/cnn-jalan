"""Tes layanan augmentasi (tahap terpisah dari preprocessing): reproducibility, flag per transformasi, validasi parameter."""
import unittest

import numpy as np

from app.services import augmentation_service as aug


def _gambar(seed=0, size=48):
    return (np.random.RandomState(seed).rand(size, size, 3) * 255).astype(np.uint8)


class AugmentationServiceTest(unittest.TestCase):
    def test_keys_match_model_augmentation_layers(self):
        from app.services.cnn_service.model import AUG_KEYS
        self.assertEqual(aug.KUNCI, AUG_KEYS)
        self.assertEqual(tuple(aug.DEFAULT_PARAMS), AUG_KEYS)

    def test_same_seed_doc_copy_is_reproducible_and_copies_differ(self):
        arr, params = _gambar(), aug.default_params()
        a = aug.augment_array(arr, params, aug.rng_untuk(42, 7, 1))
        b = aug.augment_array(arr, params, aug.rng_untuk(42, 7, 1))
        c = aug.augment_array(arr, params, aug.rng_untuk(42, 7, 2))
        d = aug.augment_array(arr, params, aug.rng_untuk(43, 7, 1))
        self.assertTrue(np.array_equal(a, b))
        self.assertFalse(np.array_equal(a, c))     # salinan lain
        self.assertFalse(np.array_equal(a, d))     # seed lain
        self.assertEqual((a.shape, a.dtype), (arr.shape, np.uint8))

    def test_all_transforms_disabled_returns_identical_image(self):
        arr = _gambar()
        params = aug.default_params()
        for v in params.values():
            v['aktif'] = False
        self.assertTrue(np.array_equal(aug.augment_array(arr, params, aug.rng_untuk(1, 1, 1)), arr))

    def test_single_transform_changes_image_and_flag_off_does_not(self):
        arr = _gambar()
        params = aug.default_params()
        for v in params.values():
            v['aktif'] = False
        params['brightness']['aktif'] = True
        self.assertFalse(np.array_equal(aug.augment_array(arr, params, aug.rng_untuk(1, 1, 1)), arr))
        params['brightness']['aktif'] = False
        params['flip']['aktif'] = True
        params['flip']['p'] = 1.0
        self.assertTrue(np.array_equal(aug.augment_array(arr, params, aug.rng_untuk(1, 1, 1)), arr[:, ::-1]))

    def test_normalisasi_params_validates(self):
        self.assertEqual(aug.normalisasi_params({})['zoom']['faktor'], 0.2)
        for buruk in ({'tidak_ada': {'aktif': True}}, {'zoom': {'salah': 1}}, {'flip': {'p': 2}},
                      {'rotasi': {'derajat': 200}}, {'erasing': {'luas_min': 0.5, 'luas_maks': 0.1}}):
            with self.assertRaises(ValueError):
                aug.normalisasi_params(buruk)


if __name__ == '__main__':
    unittest.main()
