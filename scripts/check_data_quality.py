"""
check_data_quality.py — Audit kebersihan dataset foto (tahap Cleaning preprocessing).

Cek (read-only, TIDAK menghapus apa pun):
  - File hilang / 0 byte / tidak bisa dibuka (korup)
  - Resolusi di bawah ambang batas (default 64x64)
  - Duplikat persis via MD5 isi file

Pemakaian (dari root project, pakai venv):
  .\\.venv\\Scripts\\python.exe scripts\\check_data_quality.py
  .\\.venv\\Scripts\\python.exe scripts\\check_data_quality.py --min-resolution 64
"""
import argparse
import hashlib
import os
import sys
from collections import defaultdict

from PIL import Image

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)


def _md5(path):
    with open(path, 'rb') as f:
        return hashlib.md5(f.read()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--min-resolution', type=int, default=64)
    args = ap.parse_args()

    from app import create_app
    from app.models.dokumentasi_foto import DokumentasiFoto

    with create_app().app_context():
        foto_list = DokumentasiFoto.query.order_by(DokumentasiFoto.id).all()

        missing, corrupt, zero_byte, too_small = [], [], [], []
        hashes = defaultdict(list)

        for foto in foto_list:
            path = os.path.join(BASE_DIR, 'app', 'static', foto.path_file.lstrip('/\\'))
            if not os.path.isfile(path):
                missing.append(foto)
                continue
            if os.path.getsize(path) == 0:
                zero_byte.append(foto)
                continue
            try:
                with Image.open(path) as img:
                    img.verify()
                with Image.open(path) as img:
                    w, h = img.size
            except Exception:
                corrupt.append(foto)
                continue
            if w < args.min_resolution or h < args.min_resolution:
                too_small.append((foto, w, h))
            hashes[_md5(path)].append(foto)

        exact_dupes = {h: fotos for h, fotos in hashes.items() if len(fotos) > 1}

        print(f'Total foto di DB      : {len(foto_list)}')
        print(f'File hilang            : {len(missing)}')
        for f in missing:
            print(f'  - #{f.id} {f.nama_file}')
        print(f'File 0 byte            : {len(zero_byte)}')
        for f in zero_byte:
            print(f'  - #{f.id} {f.nama_file}')
        print(f'File korup             : {len(corrupt)}')
        for f in corrupt:
            print(f'  - #{f.id} {f.nama_file}')
        print(f'Resolusi < {args.min_resolution}x{args.min_resolution}    : {len(too_small)}')
        for f, w, h in too_small:
            print(f'  - #{f.id} {f.nama_file} ({w}x{h})')
        print(f'Grup duplikat persis (MD5) : {len(exact_dupes)}')
        for h, fotos in exact_dupes.items():
            print(f'  - {", ".join(f"#{f.id} {f.nama_file}" for f in fotos)}')

        print('\nLaporan saja — tidak ada file/data yang dihapus.')


if __name__ == '__main__':
    main()
