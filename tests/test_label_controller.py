import unittest
from unittest import mock

from flask import request

from app import create_app, db
from app.controllers.label_controller import _config_from_form
from app.models.pengguna import Pengguna
from tests.isolated_app import make_isolated_app, release_isolated_app


class LabelControllerContractTest(unittest.TestCase):
    def setUp(self):
        self.app, self.database_path = make_isolated_app('label-controller-secret')

    def tearDown(self):
        release_isolated_app(self.app, self.database_path)

    def test_new_configuration_rejects_invalid_canny_order(self):
        with self.app.test_request_context(
            '/label/config/new',
            method='POST',
            data={
                'nama_config': 'invalid', 'n_cluster': '4', 'pca_komponen': '50',
                'random_state': '42', 'canny_low': '150', 'canny_high': '50',
            },
        ):
            with mock.patch('app.controllers.label_controller.current_user', id=7):
                with self.assertRaisesRegex(ValueError, 'Canny low'):
                    _config_from_form()

    def test_label_routes_expose_review_workflow_without_sdi_routes(self):
        routes = {rule.rule for rule in self.app.url_map.iter_rules()}
        self.assertIn('/label/config/new', routes)
        self.assertIn('/label/config/<int:config_id>/run', routes)
        self.assertIn('/label/review/<int:run_id>', routes)
        self.assertIn('/label/review/<int:run_id>/terapkan', routes)
        self.assertIn('/label/review/<int:run_id>/buang', routes)
        self.assertNotIn('/label/auto', routes)
        self.assertNotIn('/label/hitung-sdi', routes)


if __name__ == '__main__':
    unittest.main()
