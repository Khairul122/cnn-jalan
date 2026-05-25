import openpyxl, os

TANGGAL_SURVEI = '2024-01-01'
PENGGUNA_ID = 1
SUMBER_DATA = 'primer'

def normalize_coord(val):
    if val is None:
        return None
    s = str(val).strip().replace(',', '.')
    # Jika sudah ada titik desimal → sudah format benar
    if '.' in s:
        try:
            return round(float(s), 7)
        except Exception:
            return None
    # Tidak ada titik desimal → integer dari Excel (misal 5202934 → 5.202934)
    try:
        i = int(s)
    except Exception:
        return None
    if abs(i) > 1000:
        return round(i / 1_000_000, 7)
    return round(float(i), 7)

def esc(v):
    if v is None:
        return 'NULL'
    s = str(v).strip().replace("'", "''")
    return "'" + s + "'"

BASE_DIR = os.path.abspath(os.path.dirname(__file__))
wb = openpyxl.load_workbook(os.path.join(BASE_DIR, 'data', 'Data_jalan_rusak_FINAL (1).xlsx'))
ws = wb.active

lines = []
skipped = []
for i, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
    citra, x_raw, y_raw, p_raw, l_raw = (row + (None,)*5)[:5]
    if not citra:
        break
    lat = normalize_coord(x_raw)
    lon = normalize_coord(y_raw)
    if lat is None or lon is None:
        skipped.append(f'-- SKIP baris {i}: koordinat tidak valid ({x_raw}, {y_raw})')
        continue
    panjang = esc(str(p_raw).strip() if p_raw is not None else None)
    lebar   = esc(str(l_raw).strip() if l_raw is not None else None)
    lines.append(
        f"  ({esc(str(citra).strip())}, {lat}, {lon}, {panjang}, {lebar}, '{SUMBER_DATA}', '{TANGGAL_SURVEI}', {PENGGUNA_ID})"
    )

out = os.path.join(BASE_DIR, 'insert_lokasi.sql')
with open(out, 'w', encoding='utf-8') as f:
    f.write("-- ============================================================\n")
    f.write("--  INSERT lokasi_kerusakan dari Excel (280 baris)\n")
    f.write(f"--  Total valid: {len(lines)} | Dilewati: {len(skipped)}\n")
    f.write("-- ============================================================\n\n")
    f.write("USE db_cnn_jalan;\n\n")
    for s in skipped:
        f.write(s + "\n")
    if skipped:
        f.write("\n")
    f.write("INSERT INTO lokasi_kerusakan\n")
    f.write("  (nama_citra, latitude, longitude, panjang, lebar, sumber_data, tanggal_survei, pengguna_id)\n")
    f.write("VALUES\n")
    for j, r in enumerate(lines):
        comma = "," if j < len(lines) - 1 else ";"
        f.write(r + comma + "\n")

print(f"SQL ditulis ke: {out}")
print(f"Total INSERT: {len(lines)} | Dilewati: {len(skipped)}")
