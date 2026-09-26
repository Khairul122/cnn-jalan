import os
import re
from datetime import datetime

from flask import current_app
from PIL import Image, ImageOps, UnidentifiedImageError
from werkzeug.utils import secure_filename

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

MAX_EDGE = 1600          # sisi panjang maksimum setelah kompresi
JPEG_QUALITY = 82        # kualitas JPEG/WebP setelah kompresi


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


def _clean_stem(name):
    """Ambil nama tanpa ekstensi, buang karakter yang menyulitkan URL/laporan.

    secure_filename() aslinya mengganti spasi jadi underscore, tapi ia menelan
    aksen dan tanda hubung gaya unicode menjadi kosong. Normalisasi spasi dulu
    supaya `gambar 182` menjadi `gambar_182`, bukan `gambar182`.
    """
    stem = os.path.splitext(name)[0]
    stem = secure_filename(stem.replace(' ', '_'))
    stem = re.sub(r'_+', '_', stem).strip('_.')
    return stem or 'foto'


def _compress(path, ext):
    """Perkecil gambar di tempat. Gagal → biarkan berkas asli apa adanya."""
    try:
        with Image.open(path) as img:
            img = ImageOps.exif_transpose(img)
            if max(img.size) > MAX_EDGE:
                img.thumbnail((MAX_EDGE, MAX_EDGE), Image.LANCZOS)
            save_kwargs = {'optimize': True}
            if ext in {'jpg', 'jpeg'}:
                img.convert('RGB').save(path, 'JPEG', quality=JPEG_QUALITY, **save_kwargs)
            elif ext == 'webp':
                img.save(path, 'WEBP', quality=JPEG_QUALITY, **save_kwargs)
            else:
                # PNG: palette kalau tidak butuh transparansi, kalau perlu tetap RGBA
                if img.mode not in ('RGBA', 'LA', 'P'):
                    img = img.convert('P', palette=Image.ADAPTIVE)
                img.save(path, 'PNG', **save_kwargs)
    except (UnidentifiedImageError, OSError, ValueError):
        # ponytail: kompresi best-effort. Foto tetap tersimpan utuh kalau gagal,
        # jadi upload tidak pernah hilang gara-gara encoder. Ganti ke antrian
        # latar kalau nanti perlu lapor balik ke pengguna.
        pass


def save_photo(file_storage):
    """Validasi, kompres, lalu simpan ke UPLOAD_FOLDER → (nama_file, path_file relatif static, ukuran_kb)."""
    validate_image(file_storage)
    folder = current_app.config['UPLOAD_FOLDER']
    os.makedirs(folder, exist_ok=True)
    ext = file_storage.filename.rsplit('.', 1)[1].lower()
    fname = f'{datetime.now():%Y%m%d%H%M%S%f}_{_clean_stem(file_storage.filename)}.{ext}'
    full = os.path.join(folder, fname)
    file_storage.save(full)
    _compress(full, ext)
    return fname, f'uploads/foto/{fname}', os.path.getsize(full) // 1024
