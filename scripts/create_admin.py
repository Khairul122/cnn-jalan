"""
create_admin.py — Buat akun admin, atau ubah password/role akun yang sudah ada.

Pemakaian (dari root project, pakai venv):
  .\\.venv\\Scripts\\python.exe scripts\\create_admin.py --email admin@gmail.com
  .\\.venv\\Scripts\\python.exe scripts\\create_admin.py --email baru@kampus.ac.id --nama "Nama Admin"

Password dibaca lewat prompt (tidak tampil di layar dan tidak masuk riwayat shell).
Akun yang sudah ada dijadikan admin dan password-nya diganti.
"""

import argparse
import getpass
import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

MIN_PASSWORD = 8


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--email', required=True)
    ap.add_argument('--nama', help='wajib untuk akun baru')
    args = ap.parse_args()

    password = getpass.getpass('Password baru: ')
    if len(password) < MIN_PASSWORD:
        sys.exit(f'Password minimal {MIN_PASSWORD} karakter.')
    if password != getpass.getpass('Ulangi password: '):
        sys.exit('Password tidak sama.')

    from app import create_app, db
    from app.models.pengguna import Pengguna

    with create_app().app_context():
        pengguna = Pengguna.query.filter_by(email=args.email).first()
        if pengguna is None:
            if not args.nama:
                sys.exit('Akun belum ada: sertakan --nama untuk membuatnya.')
            pengguna = Pengguna(nama=args.nama, email=args.email)
            db.session.add(pengguna)
            aksi = 'dibuat'
        else:
            aksi = 'diperbarui'
        pengguna.role = 'admin'
        pengguna.set_password(password)
        db.session.commit()
        print(f'Akun admin {args.email} {aksi}.')


if __name__ == '__main__':
    main()
