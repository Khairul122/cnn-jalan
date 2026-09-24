"""
Tes regresi keamanan P0. Jalankan dari root project:
  .\\.venv\\Scripts\\python.exe -m unittest discover -s tests -v

Memakai database dev (DATABASE_URL, atau TEST_DATABASE_URL bila diset). Akun uji dibuat dengan email acak dan
dihapus di akhir. Target aksi destruktif memakai id yang tidak ada (999999) agar tidak
ada data nyata yang bisa terhapus seandainya proteksi gagal.
"""
import re
import unittest
import uuid

from app import create_app, db
from app.models.pengguna import Pengguna

PASSWORD = 'uji-password-123'


def _token(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, 'token CSRF tidak ditemukan di halaman'
    return m.group(1)


class SecurityTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app()
        cls.tag = uuid.uuid4().hex[:8]
        cls.emails = {}
        with cls.app.app_context():
            for role in ('admin', 'viewer'):
                email = f'uji-{role}-{cls.tag}@example.test'
                u = Pengguna(nama=f'Uji {role}', email=email, role=role)
                u.set_password(PASSWORD)
                db.session.add(u)
                cls.emails[role] = email
            db.session.commit()

    @classmethod
    def tearDownClass(cls):
        with cls.app.app_context():
            Pengguna.query.filter(Pengguna.email.like(f'%-{cls.tag}@example.test')).delete(synchronize_session=False)
            db.session.commit()

    def login(self, role):
        c = self.app.test_client()
        tok = _token(c.get('/auth/login').get_data(as_text=True))
        r = c.post('/auth/login', data={'email': self.emails[role], 'password': PASSWORD, 'csrf_token': tok})
        self.assertEqual(r.status_code, 302)
        return c

    def token(self, client, path='/lokasi/'):
        return _token(client.get(path).get_data(as_text=True))

    # ── register ────────────────────────────────────────────────
    def test_register_ignores_role_admin(self):
        c = self.app.test_client()
        email = f'daftar-{self.tag}@example.test'
        tok = _token(c.get('/auth/register').get_data(as_text=True))
        r = c.post('/auth/register', data={'nama': 'Pendaftar', 'email': email, 'password': PASSWORD,
                                           'role': 'admin', 'csrf_token': tok})
        self.assertEqual(r.status_code, 302)
        with self.app.app_context():
            u = Pengguna.query.filter_by(email=email).first()
            self.assertIsNotNone(u)
            self.assertEqual(u.role, 'viewer')

    def test_register_rejects_short_password(self):
        c = self.app.test_client()
        email = f'pendek-{self.tag}@example.test'
        tok = _token(c.get('/auth/register').get_data(as_text=True))
        c.post('/auth/register', data={'nama': 'X', 'email': email, 'password': '1234567', 'csrf_token': tok})
        with self.app.app_context():
            self.assertIsNone(Pengguna.query.filter_by(email=email).first())

    # ── CSRF ────────────────────────────────────────────────────
    def test_post_without_csrf_token_is_rejected(self):
        c = self.login('admin')
        r = c.post('/split/999999/delete')          # tanpa token
        self.assertEqual(r.status_code, 302)        # CSRFError → redirect, bukan 404 dari route
        r = c.post('/split/999999/delete', data={'csrf_token': self.token(c)})
        self.assertEqual(r.status_code, 404)        # dengan token: lolos ke route

    # ── role ────────────────────────────────────────────────────
    def test_viewer_cannot_mutate(self):
        c = self.login('viewer')
        tok = self.token(c)
        for path in ('/split/999999/delete', '/label/999999/delete', '/lokasi/999999/delete',
                     '/arsitektur/999999/delete', '/preprocessing/config/999999/delete',
                     '/evaluasi/999999/delete'):
            r = c.post(path, data={'csrf_token': tok})
            self.assertEqual(r.status_code, 302, path)       # 403 → redirect + flash, bukan 404
        self.assertEqual(c.get('/lokasi/create').status_code, 302)
        self.assertEqual(c.post('/arsitektur/999999/evaluate', data={'csrf_token': tok}).status_code, 302)

    def test_viewer_can_read(self):
        c = self.login('viewer')
        for path in ('/lokasi/', '/label/', '/split/', '/arsitektur/', '/preprocessing/', '/peta/'):
            self.assertEqual(c.get(path).status_code, 200, path)

    def test_admin_passes_role_check(self):
        c = self.login('admin')
        tok = self.token(c)
        self.assertEqual(c.get('/lokasi/create').status_code, 200)
        self.assertEqual(c.post('/split/999999/delete', data={'csrf_token': tok}).status_code, 404)

    # ── login/logout ────────────────────────────────────────────
    def test_login_next_open_redirect(self):
        for nxt, expected in (('//evil.example', '/'), ('https://evil.example', '/'),
                              ('/\\evil.example', '/'), ('/lokasi/', '/lokasi/')):
            c = self.app.test_client()
            tok = _token(c.get('/auth/login').get_data(as_text=True))
            r = c.post('/auth/login', query_string={'next': nxt},
                       data={'email': self.emails['viewer'], 'password': PASSWORD, 'csrf_token': tok})
            self.assertEqual(r.status_code, 302)
            loc = r.headers['Location']
            self.assertFalse('evil' in loc, f'{nxt} → {loc}')
            self.assertTrue(loc.endswith(expected) or loc.endswith('/dashboard'), f'{nxt} → {loc}')

    def test_logout_requires_post(self):
        c = self.login('viewer')
        self.assertEqual(c.get('/auth/logout').status_code, 405)
        r = c.post('/auth/logout', data={'csrf_token': self.token(c)})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(c.get('/lokasi/').status_code, 302)   # sudah logout


if __name__ == '__main__':
    unittest.main()
