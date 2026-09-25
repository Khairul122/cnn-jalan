import os
from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
load_dotenv(os.path.join(BASE_DIR, '.env'))


def _required(name):
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(
            f'Environment variable {name} belum diset. '
            'Salin .env.example menjadi .env lalu isi SECRET_KEY dan '
            'DATABASE_URL (format mysql+pymysql://user:password@host:3306/nama_db), '
            'lalu jalankan ulang dengan .venv aktif.'
        )
    return value


class Config:
    SECRET_KEY = _required('SECRET_KEY')
    SQLALCHEMY_DATABASE_URI = _required('DATABASE_URL')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    # Tanpa pool_pre_ping, koneksi yang sudah diputus wait_timeout MySQL
    # menimbulkan error 2006 "server has gone away" pada request berikutnya.
    # 280 detik menutupi wait_timeout 240 detik atau kurang.
    SQLALCHEMY_ENGINE_OPTIONS = {
        'pool_pre_ping': True,
        'pool_recycle': 280,
    }
    UPLOAD_FOLDER = os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'foto')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = 'Lax'
