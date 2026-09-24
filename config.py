import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f'Environment variable {name} belum diset. '
            'Salin .env.example menjadi .env lalu isi nilainya.'
        )
    return value


class Config:
    SECRET_KEY = _required('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = _required('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Supabase Postgres lewat connection pooler: koneksi bisa diputus server saat idle.
    SQLALCHEMY_ENGINE_OPTIONS = {'pool_pre_ping': True, 'pool_recycle': 280}
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'foto')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16 MB
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
