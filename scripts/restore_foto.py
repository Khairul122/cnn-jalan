"""
restore_foto.py — Pulihkan foto yang terhapus dari uploads/foto/
Baca nama file dari database lalu copy dari data/jalan/ ke uploads/foto/.
Database TIDAK diubah sama sekali.

Cara pakai:
    python restore_foto.py
"""

import os
import shutil

BASE_DIR   = os.path.abspath(os.path.dirname(__file__))
SRC_DIR    = os.path.join(BASE_DIR, 'data', 'jalan')
DEST_DIR   = os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'foto')

# Timestamp prefix di nama_file = 20 karakter + underscore (21 total)
# Format: %Y%m%d%H%M%S%f → 4+2+2+2+2+2+6 = 20 karakter
TIMESTAMP_LEN = 21  # 20 digit + 1 underscore


def build_src_index():
    """Buat index {lowercase_name: full_path} untuk semua file di data/jalan/."""
    idx = {}
    for f in os.listdir(SRC_DIR):
        idx[f.lower()] = os.path.join(SRC_DIR, f)
    return idx


def main():
    from app import create_app, db
    from app.models.dokumentasi_foto import DokumentasiFoto

    app = create_app()
    with app.app_context():
        foto_list = DokumentasiFoto.query.all()
        print(f'Total record di database: {len(foto_list)}')

    os.makedirs(DEST_DIR, exist_ok=True)
    src_index = build_src_index()

    berhasil = 0
    tidak_ditemukan = []

    for foto in foto_list:
        dest_path = os.path.join(DEST_DIR, foto.nama_file)

        # Sudah ada → skip
        if os.path.isfile(dest_path):
            berhasil += 1
            continue

        # Ekstrak nama asli: strip timestamp prefix
        if len(foto.nama_file) > TIMESTAMP_LEN:
            original_name = foto.nama_file[TIMESTAMP_LEN:]
        else:
            original_name = foto.nama_file

        # Cari di data/jalan/ (case-insensitive)
        src_path = src_index.get(original_name.lower())

        if src_path:
            shutil.copy2(src_path, dest_path)
            berhasil += 1
            print(f'  OK  {foto.nama_file}')
        else:
            tidak_ditemukan.append(foto.nama_file)
            print(f'  ??  {foto.nama_file}  (sumber: "{original_name}" tidak ditemukan)')

    print()
    print('=' * 55)
    print(f'Selesai — {berhasil} foto dipulihkan')
    if tidak_ditemukan:
        print(f'Tidak ditemukan: {len(tidak_ditemukan)} file')
        for f in tidak_ditemukan:
            print(f'  - {f}')
    print('=' * 55)


if __name__ == '__main__':
    main()
