"""
seed_data.py — Ganti seluruh data model dengan isi Excel + foto asli.

Langkah:
  1. (--reset) Kosongkan tabel data model + hapus file upload, preprocessed, dan model .keras
  2. Baca Excel (kolom: Citra, x, y, P, L, Ket) -> lokasi_kerusakan
  3. Salin foto dari data/jalan/ ke app/static/uploads/foto/ -> dokumentasi_foto

Pemakaian (dari root project, pakai venv):
  .\\.venv\\Scripts\\python.exe scripts\\seed_data.py --reset
  .\\.venv\\Scripts\\python.exe scripts\\seed_data.py --excel "data\\DATA JALAN REVISI.xlsx" --reset

Tabel master (pengguna, jenis/tingkat kerusakan, preprocessing_config, evaluasi_model manual)
tidak disentuh.
"""

import argparse
import glob
import os
import shutil
import sys
from datetime import datetime

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)

DEFAULT_EXCEL = os.path.join(BASE_DIR, 'data', 'DATA JALAN REVISI.xlsx')
IMG_DIR       = os.path.join(BASE_DIR, 'data', 'jalan')
STATIC_DIR    = os.path.join(BASE_DIR, 'app', 'static')
UPLOAD_DIR    = os.path.join(STATIC_DIR, 'uploads', 'foto')
PREPROC_DIR   = os.path.join(STATIC_DIR, 'uploads', 'preprocessed')
MODEL_DIR     = os.path.join(STATIC_DIR, 'models')

PENGGUNA_ID = 1
SUMBER_DATA = 'primer'
HEADER      = ('Citra', 'x', 'y', 'P', 'L', 'Ket')
IMG_EXT     = ('jpg', 'jpeg', 'png', 'webp')

# Urutan aman terhadap FK (anak dulu, induk belakangan)
TABEL_DATA_MODEL = (
    'hasil_training', 'hasil_evaluasi', 'prediksi_model', 'arsitektur_config',
    'split_item', 'split_config', 'hasil_preprocessing', 'label_kerusakan',
    'peta_kerusakan', 'hasil_klasifikasi_cnn', 'dokumentasi_foto', 'lokasi_kerusakan',
)


def read_excel(path):
    """Baca Excel -> list of dict. Berhenti dengan ValueError jika ada baris tidak valid."""
    import openpyxl

    workbook = openpyxl.load_workbook(path, read_only=True, data_only=True)
    ws = workbook.active
    rows = ws.iter_rows(values_only=True)
    header = tuple(str(c).strip() if c is not None else '' for c in next(rows)[:len(HEADER)])
    if header != HEADER:
        workbook.close()
        raise ValueError(f'Header Excel harus {HEADER}, ditemukan {header}')

    data, errors, seen = [], [], set()
    for no, (citra, x, y, p, l, ket, *_) in enumerate(rows, start=2):
        if not citra:
            continue
        citra = str(citra).strip()
        try:
            item = dict(nama_citra=citra, latitude=float(x), longitude=float(y),
                        panjang=float(p), lebar=float(l),
                        keterangan=str(ket).strip() if ket else None)
        except (TypeError, ValueError):
            errors.append(f'baris {no} ({citra}): x/y/P/L bukan angka')
            continue
        if citra in seen:
            errors.append(f'baris {no}: nama citra "{citra}" duplikat')
        seen.add(citra)
        data.append(item)

    if errors:
        workbook.close()
        raise ValueError('Excel tidak valid:\n  ' + '\n  '.join(errors))
    workbook.close()
    return data


def find_image(nama_citra):
    for ext in IMG_EXT:
        path = os.path.join(IMG_DIR, f'{nama_citra.lower()}.{ext}')
        if os.path.isfile(path):
            return path
    return None


def copy_image(src):
    """Salin ke uploads/foto dengan prefix timestamp -> (nama_file, path_file, ukuran_kb)."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    fname = f'{datetime.now():%Y%m%d%H%M%S%f}_{os.path.basename(src)}'
    dst = os.path.join(UPLOAD_DIR, fname)
    shutil.copy2(src, dst)
    return fname, f'uploads/foto/{fname}', os.path.getsize(dst) // 1024


def clear_dir(folder, pattern='*'):
    files = [f for f in glob.glob(os.path.join(folder, pattern)) if os.path.isfile(f)
             and os.path.basename(f) != '.gitkeep']
    for f in files:
        os.remove(f)
    return len(files)


def reset_data(db):
    from sqlalchemy import text

    db.session.execute(text('SET FOREIGN_KEY_CHECKS = 0'))
    for tabel in TABEL_DATA_MODEL:
        db.session.execute(text(f'TRUNCATE TABLE `{tabel}`'))
    db.session.execute(text('SET FOREIGN_KEY_CHECKS = 1'))
    db.session.commit()

    print(f'  tabel dikosongkan : {len(TABEL_DATA_MODEL)}')
    print(f'  foto dihapus      : {clear_dir(UPLOAD_DIR)}')
    print(f'  preprocessed      : {clear_dir(PREPROC_DIR)}')
    print(f'  model .keras      : {clear_dir(MODEL_DIR, "*.keras")}')


def import_rows(db, rows):
    from app.models.lokasi_kerusakan import LokasiKerusakan
    from app.models.dokumentasi_foto import DokumentasiFoto

    tanpa_foto = []
    for row in rows:
        lokasi = LokasiKerusakan(sumber_data=SUMBER_DATA, pengguna_id=PENGGUNA_ID, **row)
        db.session.add(lokasi)
        db.session.flush()

        src = find_image(row['nama_citra'])
        if src is None:
            tanpa_foto.append(row['nama_citra'])
            continue
        nama_file, path_file, ukuran_kb = copy_image(src)
        db.session.add(DokumentasiFoto(lokasi_id=lokasi.id, nama_file=nama_file,
                                       path_file=path_file, ukuran_kb=ukuran_kb))
    db.session.commit()
    return tanpa_foto


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--excel', default=DEFAULT_EXCEL, help='path file Excel')
    ap.add_argument('--reset', action='store_true', help='kosongkan data model + file sebelum import')
    args = ap.parse_args()

    rows = read_excel(args.excel)          # validasi dulu, sebelum ada yang dihapus
    print(f'Excel valid: {len(rows)} baris ({args.excel})')

    from app import create_app, db
    with create_app().app_context():
        if args.reset:
            print('Reset data model:')
            reset_data(db)
        tanpa_foto = import_rows(db, rows)

    print(f'Import selesai: {len(rows)} lokasi, {len(rows) - len(tanpa_foto)} foto')
    if tanpa_foto:
        print('Tanpa foto:', ', '.join(tanpa_foto))


if __name__ == '__main__':
    main()
