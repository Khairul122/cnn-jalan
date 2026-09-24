"""
run_surveyor_cv.py — Latih & CV model kedua dengan label SURVEYOR (bukan SDI dari P×L).

TODO.md P1: "Latih model kedua dengan label surveyor (kolom keterangan pada baris Estimasi)
sebagai target, untuk subset data yang punya kedua sumber label. Bandingkan macro-F1 dengan
model label SDI." Subset = foto dengan keterangan 'Estimasi (Ringan|Sedang|Berat)' — baris
'Ukur' tidak dihitung (tidak ada penilaian kelas surveyor yang independen dari P×L-nya).

Cara kerja: split & training/CV yang SAMA dengan run_pipeline.py (reuse SplitService,
dedup_service, cnn_service via _run_training/_run_cv_predict), tapi ground-truth kelas per
split_item diambil dari teks `keterangan` surveyor, BUKAN dari LabelKerusakan (SDI). Ini murni
eksperimen pembanding — TIDAK mengubah label_kerusakan atau split manapun yang sudah ada.

Pemakaian (dari root project, pakai venv):
  .\\.venv\\Scripts\\python.exe scripts\\run_surveyor_cv.py
  .\\.venv\\Scripts\\python.exe scripts\\run_surveyor_cv.py --epochs 60 --lr 0.0001
"""
import argparse
import os
import re
import sys
import time

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)

KETERANGAN_KE_TINGKAT = {'Berat': 1, 'Sedang': 2, 'Ringan': 3}


def log(*args):
    print(time.strftime('%H:%M:%S'), *args, flush=True)


def _parse_surveyor_class(keterangan):
    m = re.match(r'Estimasi \((Berat|Sedang|Ringan)\)', keterangan or '')
    return KETERANGAN_KE_TINGKAT[m.group(1)] if m else None


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--k', type=int, default=5)
    ap.add_argument('--random-state', type=int, default=42)
    ap.add_argument('--model', choices=('mobilenetv2', 'efficientnetb0'), default='mobilenetv2')
    ap.add_argument('--epochs', type=int, default=80)
    ap.add_argument('--lr', type=float, default=0.0001)
    ap.add_argument('--batch', type=int, default=32)
    ap.add_argument('--patience', type=int, default=20)
    ap.add_argument('--dropout', type=float, default=0.3)
    ap.add_argument('--optimizer', choices=('adam', 'sgd', 'rmsprop'), default='adam')
    ap.add_argument('--fold', type=int, default=0, help='fold uji untuk training tunggal awal')
    args = ap.parse_args()

    from app import create_app, db
    from app.controllers.arsitektur_controller import _run_cv_predict, _run_training, _errors
    from app.models.arsitektur_config import ArsitekturConfig
    from app.models.dokumentasi_foto import DokumentasiFoto
    from app.models.lokasi_kerusakan import LokasiKerusakan
    from app.models.pengguna import Pengguna
    from app.models.split_config import SplitConfig
    from app.models.split_item import SplitItem
    from app.services.dedup_service import find_duplicate_groups
    from app.services.metrics_service import cv_summary
    from app.services.split_service import SplitService

    app = create_app()

    with app.app_context():
        admin = Pengguna.query.filter_by(role='admin').first()
        if admin is None:
            sys.exit('Belum ada akun admin. Jalankan scripts/create_admin.py dulu.')

        rows = (
            db.session.query(DokumentasiFoto.id, DokumentasiFoto.path_file, LokasiKerusakan.keterangan)
            .join(LokasiKerusakan, DokumentasiFoto.lokasi_id == LokasiKerusakan.id)
            .filter(LokasiKerusakan.keterangan.like('Estimasi (%'))
            .all()
        )
        items = []
        for doc_id, path_file, ket in rows:
            tingkat = _parse_surveyor_class(ket)
            if tingkat is not None:
                items.append({'dokumentasi_id': doc_id, 'path_file': path_file, 'label_id': tingkat})

        from collections import Counter
        kelas_count = Counter(i['label_id'] for i in items)
        log(f'Subset label surveyor: {len(items)} foto | distribusi (1=Berat,2=Sedang,3=Ringan): {dict(kelas_count)}')

        min_class = min(kelas_count.values()) if kelas_count else 0
        if min_class < args.k:
            sys.exit(f'Kelas terkecil cuma {min_class} sampel — K={args.k} terlalu besar untuk stratified split.')

        dup_groups = find_duplicate_groups(
            [i['dokumentasi_id'] for i in items], [i['path_file'] for i in items], BASE_DIR)
        groups = [dup_groups[i['dokumentasi_id']] for i in items]
        n_dup = len(items) - len(set(groups))
        log(f'Near-duplicate terdeteksi & dikelompokkan: {n_dup}')

        result = SplitService.run(args.k, args.random_state, items, groups=groups)

        nama_split = f'Surveyor-KFold{args.k}-{time.strftime("%m%d-%H%M")}'
        # label_sumber cuma bisa 'tingkat'/'jenis' (target klasifikasi, bukan sumber datanya) —
        # split surveyor tetap target 'tingkat', dibedakan lewat nama split.
        split_cfg = SplitConfig(
            nama=nama_split, n_splits=args.k, random_state=args.random_state,
            label_sumber='tingkat', total_data=len(result), pengguna_id=admin.id,
        )
        db.session.add(split_cfg)
        db.session.flush()
        db.session.bulk_insert_mappings(SplitItem, [
            {'config_id': split_cfg.id, 'dokumentasi_id': r['dokumentasi_id'],
             'tingkat_kerusakan_id': r['label_id'], 'fold_index': r['fold_index']}
            for r in result
        ])
        split_id = split_cfg.id
        db.session.commit()
        log('Split surveyor', split_id, nama_split)

        cfg = ArsitekturConfig(
            nama=f'{args.model}-{nama_split}', model_type=args.model, input_size=224,
            learning_rate=args.lr, batch_size=args.batch, epochs=args.epochs, patience=args.patience,
            dropout_rate=args.dropout, optimizer=args.optimizer, split_config_id=split_id,
            fold_val=args.fold, status='training', pengguna_id=admin.id,
        )
        db.session.add(cfg)
        db.session.commit()
        aid = cfg.id

    log('Training fold', args.fold, '(arsitektur', aid, ') — label surveyor')
    t = time.time()
    _run_training(app, aid, BASE_DIR)
    with app.app_context():
        cfg = db.session.get(ArsitekturConfig, aid)
        log(f'Training selesai ({(time.time() - t) / 60:.1f} menit), status = {cfg.status}',
            f'| error = {_errors.get(aid)}' if cfg.status != 'selesai' else '')
        if cfg.status != 'selesai':
            sys.exit(1)

    t = time.time()
    _run_cv_predict(app, aid, BASE_DIR)
    with app.app_context():
        cv = cv_summary(db.session.get(ArsitekturConfig, aid))
    if cv is None:
        sys.exit('CV gagal: tidak ada prediksi yang tersimpan.')
    log(f'CV (label surveyor) selesai ({(time.time() - t) / 60:.1f} menit), n = {cv["n"]}')
    log(f'  Akurasi {cv["akurasi"]}% ± {cv["std"]} | Macro-F1 {cv["macro_f1"]}% | '
        f'baseline {cv["baseline"]}% (selisih {cv["selisih_baseline"]:+} poin)')
    log('  Recall', cv['recall'], '| per fold', [f['akurasi'] for f in cv['per_fold']])
    log(f'  arsitektur_id={aid} split_config_id={split_id} — bandingkan macro_f1 ini dengan CV label SDI')


if __name__ == '__main__':
    main()
