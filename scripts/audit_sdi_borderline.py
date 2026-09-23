"""
audit_sdi_borderline.py — Tandai label yang skor SDI-nya dekat ambang batas (50 dan 150).

Baris ini paling rawan salah klasifikasi (Ringan/Sedang atau Sedang/Berat) karena SDI-nya
cuma sedikit di bawah/atas garis batas Bina Marga. Dipakai untuk analisis kesalahan terpisah
(lihat TODO.md P1) — bukan untuk mengubah label apa pun, cuma laporan read-only + CSV.

Pemakaian (dari root project, pakai venv):
  .\\.venv\\Scripts\\python.exe scripts\\audit_sdi_borderline.py
  .\\.venv\\Scripts\\python.exe scripts\\audit_sdi_borderline.py --margin 15 --csv borderline.csv
"""
import argparse
import csv
import os
import sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)

THRESHOLDS = (50, 150)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--margin', type=float, default=10, help='jarak dari ambang batas yang dianggap "dekat" (default 10)')
    ap.add_argument('--csv', help='path file CSV untuk simpan hasil (opsional)')
    args = ap.parse_args()

    from app import create_app
    from app.models.label_kerusakan import LabelKerusakan
    from app.models.lokasi_kerusakan import LokasiKerusakan

    with create_app().app_context():
        rows = (
            LabelKerusakan.query
            .join(LokasiKerusakan, LabelKerusakan.lokasi_id == LokasiKerusakan.id)
            .order_by(LabelKerusakan.sdi_score)
            .all()
        )

        hasil = []
        for lbl in rows:
            sdi = float(lbl.sdi_score)
            jarak = min(abs(sdi - t) for t in THRESHOLDS)
            if jarak <= args.margin:
                ambang = min(THRESHOLDS, key=lambda t: abs(sdi - t))
                hasil.append({
                    'lokasi_id': lbl.lokasi_id,
                    'nama_citra': lbl.lokasi.nama_citra,
                    'sdi_score': sdi,
                    'tingkat': lbl.tingkat.nama_tingkat if lbl.tingkat else lbl.tingkat_kerusakan_id,
                    'ambang_terdekat': ambang,
                    'jarak': round(jarak, 2),
                    'keterangan': lbl.lokasi.keterangan,
                })

        print(f'Total label: {len(rows)}')
        print(f'Dekat ambang batas (margin ±{args.margin}): {len(hasil)}\n')
        print(f'{"lokasi_id":>9}  {"nama_citra":<20} {"sdi":>7} {"tingkat":<8} {"ambang":>7} {"jarak":>6}  keterangan')
        for h in hasil:
            print(f'{h["lokasi_id"]:>9}  {h["nama_citra"]:<20} {h["sdi_score"]:>7.2f} {h["tingkat"]:<8} '
                  f'{h["ambang_terdekat"]:>7} {h["jarak"]:>6.2f}  {h["keterangan"] or "-"}')

        if args.csv:
            with open(args.csv, 'w', newline='', encoding='utf-8') as f:
                w = csv.DictWriter(f, fieldnames=list(hasil[0].keys()) if hasil else
                                    ['lokasi_id', 'nama_citra', 'sdi_score', 'tingkat', 'ambang_terdekat', 'jarak', 'keterangan'])
                w.writeheader()
                w.writerows(hasil)
            print(f'\nDisimpan ke {args.csv}')


if __name__ == '__main__':
    main()
