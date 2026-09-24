"""
migrate_mysql_to_supabase.py — Salin semua data dari database MySQL lama ke Postgres (Supabase). Sekali jalan.

Prasyarat: skema tujuan sudah dibuat dengan `flask db upgrade` (migrasi Alembic membuat tabel, data master, dan RLS).

Pemakaian (dari root project, pakai venv):
  .\\.venv\\Scripts\\python.exe scripts\\migrate_mysql_to_supabase.py --sumber "mysql+pymysql://root:PWD@localhost/db_cnn_jalan" --ganti
  # tujuan diambil dari DATABASE_URL (.env) kecuali --tujuan diberikan

  --ganti   kosongkan semua tabel tujuan (TRUNCATE ... RESTART IDENTITY CASCADE) sebelum menyalin. Wajib bila
            tabel tujuan sudah berisi data (termasuk data master hasil migrasi Alembic).

Yang dilakukan: menyalin tiap tabel model sesuai urutan FK (hanya kolom yang ada di sumber DAN di model), mereset
sequence id, lalu membandingkan jumlah baris sumber vs tujuan. Exit code 1 bila ada yang tidak sama.
"""
import argparse
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)

CHUNK = 500


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--sumber', default=os.environ.get('MYSQL_URL'), help='URL SQLAlchemy MySQL lama (atau env MYSQL_URL)')
    ap.add_argument('--tujuan', default=None, help='URL Postgres tujuan (default: DATABASE_URL)')
    ap.add_argument('--ganti', action='store_true', help='kosongkan tabel tujuan sebelum menyalin')
    args = ap.parse_args()
    if not args.sumber:
        sys.exit('Sumber MySQL belum diberikan (--sumber atau env MYSQL_URL).')
    if args.tujuan:
        os.environ['DATABASE_URL'] = args.tujuan

    from sqlalchemy import create_engine, func, inspect, select, text
    from app import db
    import app.models  # noqa: F401  (mendaftarkan semua tabel ke db.metadata)

    tujuan_url = os.environ.get('DATABASE_URL')
    if not tujuan_url or not tujuan_url.startswith('postgresql'):
        sys.exit('Tujuan bukan Postgres. Set DATABASE_URL (atau --tujuan) ke database Supabase.')

    src = create_engine(args.sumber)
    dst = create_engine(tujuan_url)
    tables = list(db.metadata.sorted_tables)
    src_insp = inspect(src)
    src_tables = set(src_insp.get_table_names())

    with dst.begin() as conn:
        tak_kosong = [t.name for t in tables if conn.execute(select(func.count()).select_from(t)).scalar()]
        if tak_kosong and not args.ganti:
            sys.exit(f'Tabel tujuan sudah berisi data: {", ".join(tak_kosong)}. Jalankan dengan --ganti untuk menimpa.')
        if args.ganti:
            nama = ', '.join(f'"{t.name}"' for t in tables)
            conn.execute(text(f'TRUNCATE TABLE {nama} RESTART IDENTITY CASCADE'))

        for t in tables:
            if t.name not in src_tables:
                print(f'  {t.name:24s} (tidak ada di sumber, dilewati)')
                continue
            kolom_sumber = {c['name'] for c in src_insp.get_columns(t.name)}
            kolom = [c for c in t.columns if c.name in kolom_sumber]
            with src.connect() as sc:
                rows = [dict(r) for r in sc.execute(select(*kolom)).mappings()]
            for i in range(0, len(rows), CHUNK):
                conn.execute(t.insert(), rows[i:i + CHUNK])
            print(f'  {t.name:24s} {len(rows):6d} baris disalin')

        # Insert dengan id eksplisit tidak memajukan sequence: samakan dengan MAX(id).
        for t in tables:
            if 'id' in t.c and t.c.id.primary_key:
                conn.execute(text(
                    f'SELECT setval(pg_get_serial_sequence(\'"{t.name}"\', \'id\'), '
                    f'COALESCE((SELECT MAX(id) FROM "{t.name}"), 1), (SELECT MAX(id) FROM "{t.name}") IS NOT NULL)'))

    beda = []
    with src.connect() as sc, dst.connect() as dc:
        for t in tables:
            if t.name not in src_tables:
                continue
            a = sc.execute(select(func.count()).select_from(t)).scalar()
            b = dc.execute(select(func.count()).select_from(t)).scalar()
            if a != b:
                beda.append((t.name, a, b))
    if beda:
        print('JUMLAH BARIS TIDAK SAMA:', beda)
        sys.exit(1)
    print('Selesai: jumlah baris semua tabel sama antara sumber dan tujuan.')


if __name__ == '__main__':
    main()
