import os
from datetime import datetime

from flask import current_app
from PIL import Image, UnidentifiedImageError
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}


class UploadError(ValueError):
    """Berkas upload tidak valid; pesan aman untuk ditampilkan ke pengguna."""


def validate_image(file_storage):
    """Cek ekstensi dan isi berkas (harus benar-benar gambar). Stream dikembalikan ke awal."""
    name = file_storage.filename or ''
    if '.' not in name or name.rsplit('.', 1)[1].lower() not in ALLOWED_EXTENSIONS:
        raise UploadError('File foto tidak valid (png/jpg/jpeg/webp).')
    try:
        Image.open(file_storage.stream).verify()
    except (UnidentifiedImageError, OSError):
        raise UploadError('Isi file bukan gambar yang valid.')
    finally:
        file_storage.stream.seek(0)


def save_photo(file_storage):
    """Validasi lalu simpan ke UPLOAD_FOLDER → (nama_file, path_file relatif static, ukuran_kb)."""
    validate_image(file_storage)
    folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)
    fname = f'{datetime.now():%Y%m%d%H%M%S%f}_{secure_filename(file_storage.filename)}'
    full = os.path.join(folder, fname)
    file_storage.save(full)
    return fname, f'uploads/foto/{fname}', os.path.getsize(full) // 1024
