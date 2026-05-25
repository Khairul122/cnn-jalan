"""
seed_data.py — Import data lokasi dari Excel + gambar ke database

Cara pakai:
  1. Pastikan MySQL berjalan dan db_cnn_jalan sudah ada (sudah dimigrasi)
  2. Pastikan ada user di tabel pengguna (PENGGUNA_ID di bawah)
  3. Edit TANGGAL_SURVEI sesuai tanggal survei data Anda
  4. Jalankan: python seed_data.py
"""

import os
import shutil
from datetime import datetime, date

# ── Konfigurasi — ubah sesuai kebutuhan ─────────────────────────────────────
PENGGUNA_ID    = 1               # id pengguna di tabel pengguna
SUMBER_DATA    = 'primer'        # 'primer' atau 'sekunder'
BATCH_SIZE     = 50              # commit tiap N baris
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR   = os.path.abspath(os.path.dirname(__file__))
EXCEL_PATH = os.path.join(BASE_DIR, 'data', 'Data_jalan_rusak_FINAL (1).xlsx')
IMG_DIR    = os.path.join(BASE_DIR, 'data', 'jalan')
UPLOAD_DIR = os.path.join(BASE_DIR, 'app', 'static', 'uploads', 'foto')


def normalize_coord(val):
    """Konversi koordinat dari Excel.
    - Nilai string dengan titik ('97.108763') → pakai langsung
    - Nilai integer tanpa titik (97109566) → bagi 1_000_000
    """
    if val is None:
        return None
    s = str(val).strip().replace(',', '.')
    if '.' in s:
        try:
            return round(float(s), 7)
        except (ValueError, TypeError):
            return None
    try:
        i = int(s)
    except (ValueError, TypeError):
        return None
    if abs(i) > 1000:
        return round(i / 1_000_000, 7)
    return round(float(i), 7)


def normalize_str(val):
    """Pastikan nilai P/L tersimpan sebagai string atau None."""
    if val is None:
        return None
    return str(val).strip() or None


def find_image(citra_name):
    """Cari file gambar berdasarkan nama citra dari Excel (case-insensitive)."""
    # Nama di Excel: 'Gambar 1' → cari 'gambar 1.jpg' atau 'gambar 1.jpeg'
    base = citra_name.lower()   # 'gambar 1'
    for ext in ('jpg', 'jpeg', 'png', 'webp'):
        path = os.path.join(IMG_DIR, f'{base}.{ext}')
        if os.path.isfile(path):
            return path
    return None


def copy_image(src_path):
    """Salin gambar ke folder upload dengan prefix timestamp, kembalikan (nama_file, path_file)."""
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    ext       = os.path.splitext(src_path)[1].lower()
    basename  = os.path.basename(src_path)
    timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
    fname     = f'{timestamp}_{basename}'
    dst_path  = os.path.join(UPLOAD_DIR, fname)
    shutil.copy2(src_path, dst_path)
    ukuran_kb = os.path.getsize(dst_path) // 1024
    return fname, f'uploads/foto/{fname}', ukuran_kb


def main():
    try:
        import openpyxl
    except ImportError:
        print('ERROR: openpyxl belum terinstall. Jalankan: pip install openpyxl')
        return

    from app import create_app, db
    from app.models.lokasi_kerusakan import LokasiKerusakan
    from app.models.dokumentasi_foto import DokumentasiFoto

    app = create_app()

    with app.app_context():
        wb = openpyxl.load_workbook(EXCEL_PATH)
        ws = wb.active

        total_ok    = 0
        total_skip  = 0
        errors      = []

        for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
            citra, x_raw, y_raw, p_raw, l_raw, *_ = row

            if not citra:
                break   # baris kosong = akhir data

            lat = normalize_coord(x_raw)
            lon = normalize_coord(y_raw)

            if lat is None or lon is None:
                errors.append(f'  Baris {i} ({citra}): koordinat tidak valid (x={x_raw}, y={y_raw})')
                total_skip += 1
                continue

            # Cari gambar
            img_path = find_image(citra)

            try:
                lokasi = LokasiKerusakan(
                    nama_citra=str(citra).strip(),
                    latitude=lat,
                    longitude=lon,
                    panjang=normalize_str(p_raw),
                    lebar=normalize_str(l_raw),
                    sumber_data=SUMBER_DATA,
                    pengguna_id=PENGGUNA_ID,
                )
                db.session.add(lokasi)
                db.session.flush()   # dapatkan lokasi.id

                if img_path:
                    fname, path_file, ukuran_kb = copy_image(img_path)
                    foto = DokumentasiFoto(
                        lokasi_id=lokasi.id,
                        nama_file=fname,
                        path_file=path_file,
                        ukuran_kb=ukuran_kb,
                    )
                    db.session.add(foto)
                else:
                    errors.append(f'  Baris {i} ({citra}): gambar tidak ditemukan di {IMG_DIR}')

                total_ok += 1

                if total_ok % BATCH_SIZE == 0:
                    db.session.commit()
                    print(f'  [{total_ok} lokasi tersimpan...]')

            except Exception as e:
                db.session.rollback()
                errors.append(f'  Baris {i} ({citra}): {e}')
                total_skip += 1
                continue

        db.session.commit()

    print()
    print('=' * 50)
    print(f'Selesai! Berhasil: {total_ok} lokasi | Dilewati: {total_skip}')
    if errors:
        print('\nPeringatan/error:')
        for e in errors:
            print(e)
    print('=' * 50)


if __name__ == '__main__':
    main()
