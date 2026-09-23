"""
run_pipeline.py — Jalankan ulang pipeline: Auto-label -> Preprocessing -> Split -> Training -> CV -> Model final.

Dipakai setelah data atau label berubah, supaya tidak perlu klik tiap menu satu per satu.
Memanggil route aplikasi yang sama dengan UI (bukan logika terpisah).

Pemakaian (dari root project, pakai venv):
  .\\.venv\\Scripts\\python.exe scripts\\run_pipeline.py
  .\\.venv\\Scripts\\python.exe scripts\\run_pipeline.py --skip-preprocessing --epochs 60 --fold 2
  .\\.venv\\Scripts\\python.exe scripts\\run_pipeline.py --no-cv

Prasyarat: data lokasi + foto sudah ada (scripts/seed_data.py) dan minimal satu konfigurasi
preprocessing (menu Preprocessing -> Konfigurasi Baru).
"""

import argparse
import os
import sys
import time

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, BASE_DIR)


def log(*args):
    print(time.strftime('%H:%M:%S'), *args, flush=True)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--preprocessing-config', type=int, help='id config preprocessing (default: config default/pertama)')
    ap.add_argument('--skip-preprocessing', action='store_true', help='pakai hasil preprocessing yang sudah ada')
    ap.add_argument('--k', type=int, default=5, help='jumlah fold split')
    ap.add_argument('--random-state', type=int, default=42)
    ap.add_argument('--model', choices=('mobilenetv2', 'efficientnetb0'), default='mobilenetv2')
    ap.add_argument('--epochs', type=int, default=80)
    ap.add_argument('--lr', type=float, default=0.001)
    ap.add_argument('--batch', type=int, default=32)
    ap.add_argument('--patience', type=int, default=20)
    ap.add_argument('--dropout', type=float, default=0.3)
    ap.add_argument('--optimizer', choices=('adam', 'sgd', 'rmsprop'), default='adam')
    ap.add_argument('--fold', type=int, default=0, help='fold uji untuk training tunggal')
    ap.add_argument('--no-cv', action='store_true', help='lewati prediksi CV K-Fold (yang paling lama)')
    ap.add_argument('--no-final', action='store_true', help='lewati pelatihan model final (semua data)')
    args = ap.parse_args()

    from app import create_app, db
    from app.controllers.arsitektur_controller import _run_cv_predict, _run_final_training, _run_training, _errors
    from app.models.arsitektur_config import ArsitekturConfig
    from app.models.label_kerusakan import LabelKerusakan
    from app.models.pengguna import Pengguna
    from app.models.preprocessing_config import PreprocessingConfig
    from app.models.split_config import SplitConfig
    from app.services.metrics_service import cv_summary
    from sqlalchemy import func

    app = create_app()
    app.config['WTF_CSRF_ENABLED'] = False   # skrip lokal memanggil route tanpa form
    client = app.test_client()

    with app.app_context():
        admin = Pengguna.query.filter_by(role='admin').first()
        if admin is None:
            sys.exit('Belum ada akun admin. Jalankan scripts/create_admin.py dulu.')
        admin_id = admin.id
        prep = (db.session.get(PreprocessingConfig, args.preprocessing_config) if args.preprocessing_config
                else PreprocessingConfig.query.filter_by(is_default=True).first() or PreprocessingConfig.query.first())
        if prep is None and not args.skip_preprocessing:
            sys.exit('Belum ada konfigurasi preprocessing. Buat lewat menu Preprocessing.')
        prep_id = prep.id if prep else None
    with client.session_transaction() as sess:
        sess['_user_id'] = str(admin_id)
        sess['_fresh'] = True

    def post(path, **data):
        r = client.post(path, data=data)
        if r.status_code != 302:
            sys.exit(f'POST {path} gagal: HTTP {r.status_code}')

    # 1. Label
    post('/label/auto', mode='semua')
    with app.app_context():
        dist = dict(db.session.query(LabelKerusakan.tingkat_kerusakan_id, func.count())
                    .group_by(LabelKerusakan.tingkat_kerusakan_id).all())
    log('Label (1=Berat, 2=Sedang, 3=Ringan):', dist)

    # 2. Preprocessing
    if not args.skip_preprocessing:
        t = time.time()
        post(f'/preprocessing/run/{prep_id}')
        log(f'Preprocessing selesai ({time.time() - t:.0f} dtk)')

    # 3. Split baru (yang lama dihapus dari perhatian: nama unik per waktu)
    nama_split = f'KFold{args.k}-{time.strftime("%m%d-%H%M")}'
    post('/split/new', nama=nama_split, n_splits=args.k, random_state=args.random_state)
    with app.app_context():
        split_id = SplitConfig.query.order_by(SplitConfig.id.desc()).first().id
    log('Split', split_id, nama_split)

    # 4. Konfigurasi arsitektur + training fold tunggal
    post('/arsitektur/new', nama=f'{args.model}-{nama_split}', model_type=args.model,
         learning_rate=args.lr, batch_size=args.batch, epochs=args.epochs, patience=args.patience,
         dropout_rate=args.dropout, optimizer=args.optimizer, split_config_id=split_id, fold_val=args.fold)
    with app.app_context():
        aid = ArsitekturConfig.query.order_by(ArsitekturConfig.id.desc()).first().id
        ArsitekturConfig.query.filter_by(id=aid).update({'status': 'training'})
        db.session.commit()
    log('Training fold', args.fold, '(arsitektur', aid, ')')
    t = time.time()
    _run_training(app, aid, BASE_DIR)
    with app.app_context():
        cfg = db.session.get(ArsitekturConfig, aid)
        log(f'Training selesai ({(time.time() - t) / 60:.1f} menit), status = {cfg.status}',
            f'| error = {_errors.get(aid)}' if cfg.status != 'selesai' else '')
        if cfg.status != 'selesai':
            sys.exit(1)

    # 5. CV K-Fold: angka utama yang boleh dilaporkan
    if args.no_cv:
        log('Prediksi CV dilewati (--no-cv). Jalankan dari halaman GIS untuk metrik CV.')
        return
    t = time.time()
    _run_cv_predict(app, aid, BASE_DIR)
    with app.app_context():
        cv = cv_summary(db.session.get(ArsitekturConfig, aid))
    if cv is None:
        sys.exit('CV gagal: tidak ada prediksi yang tersimpan.')
    log(f'CV selesai ({(time.time() - t) / 60:.1f} menit), n = {cv["n"]}')
    log(f'  Akurasi {cv["akurasi"]}% ± {cv["std"]} | Macro-F1 {cv["macro_f1"]}% | '
        f'baseline {cv["baseline"]}% (selisih {cv["selisih_baseline"]:+} poin)')
    log('  Recall', cv['recall'], '| per fold', [f['akurasi'] for f in cv['per_fold']])

    # 6. Model final pada semua data (untuk klasifikasi foto baru)
    if args.no_final:
        return
    t = time.time()
    _run_final_training(app, aid, BASE_DIR)
    with app.app_context():
        final_path = db.session.get(ArsitekturConfig, aid).final_model_path
    if not final_path:
        sys.exit(f'Model final gagal: {_errors.get(("final", aid))}')
    log(f'Model final selesai ({(time.time() - t) / 60:.1f} menit): {final_path}')


if __name__ == '__main__':
    main()
