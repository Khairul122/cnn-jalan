"""Profil training 'colab' meniru notebook: augmentasi, kepala model, dan fine-tuning."""
import unittest

from app.services.cnn_service.model import (
    _apply_fine_tuning, _augmentation_layers_colab, build_model,
)


class TestColabProfile(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.std = build_model('mobilenetv2', 224, 0.5, 'adam', 0.001, dense_l2=0.01)
        cls.colab = build_model('mobilenetv2', 224, 0.5, 'adam', 0.001, dense_l2=0.01, profil='colab')

    def test_augmentasi_colab_enam_layer_dan_bisa_dimatikan(self):
        self.assertEqual(len(_augmentation_layers_colab()), 6)
        self.assertEqual(len(_augmentation_layers_colab('zoom,flip')), 4)

    def test_kepala_colab_dropout_kedua_03_dan_output_tanpa_regularizer(self):
        dropouts = lambda m: [l.rate for l in m.layers if l.__class__.__name__ == 'Dropout']
        self.assertEqual(dropouts(self.colab), [0.5, 0.3])
        self.assertEqual(dropouts(self.std), [0.5, 0.25])
        self.assertIsNone(self.colab.layers[-1].kernel_regularizer)
        self.assertIsNotNone(self.std.layers[-1].kernel_regularizer)

    def test_fine_tuning_colab_membuka_6_layer_dengan_lr_dibagi_20(self):
        model = _apply_fine_tuning(self.colab, 'mobilenetv2', 0.001, 'adam', profil='colab')
        base = next(l for l in model.layers if hasattr(l, 'layers') and len(l.layers) > 10)
        self.assertEqual(sum(1 for l in base.layers if l.trainable), 6)
        self.assertAlmostEqual(float(model.optimizer.learning_rate), 0.001 / 20, places=9)


if __name__ == '__main__':
    unittest.main()
