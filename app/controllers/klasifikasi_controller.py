import os
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app import db
from app.auth_utils import admin_required
from app.uploads import UploadError, save_photo
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.hasil_klasifikasi_cnn import HasilKlasifikasiCnn
from app.models.peta_kerusakan import PetaKerusakan
from app.models.tingkat_kerusakan import TingkatKerusakan
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.preprocessing_config import PreprocessingConfig
from app.services import cnn_service
from app.progress_store import ProgressStore

# Akurasi CV resmi sistem sekitar 45%, jadi prediksi di bawah ambang ini ditandai perlu verifikasi manual.
AMBANG_CONFIDENCE = 0.5

klasifikasi_bp = Blueprint('klasifikasi', __name__, url_prefix='/klasifikasi')

# Progres klasifikasi satu foto, dikunci per user (hanya admin yang menjalankan).
_progress = ProgressStore()


def _render_upload(lokasi_list):
    return render_template('klasifikasi/upload.html', lokasi_list=lokasi_list)


@klasifikasi_bp.route('/progress')
@login_required
def progress():
    """Progres klasifikasi foto untuk user yang sedang login (dipoll saat POST berjalan)."""
    prog = _progress.get(current_user.id)
    if prog is None:
        return jsonify({'status': 'selesai', 'pct': 100})
    return jsonify(prog)


@klasifikasi_bp.route('/upload', methods=['GET', 'POST'])
@admin_required
def upload():
    lokasi_list = LokasiKerusakan.query.order_by(LokasiKerusakan.nama_citra).all()
    if request.method == 'GET':
        return _render_upload(lokasi_list)

    lokasi = db.session.get(LokasiKerusakan, request.form.get('lokasi_id', type=int) or 0)
    if lokasi is None:
        flash('Pilih lokasi yang valid.', 'danger')
        return _render_upload(lokasi_list)

    model_cfg = cnn_service.best_model()
    if model_cfg is None:
        flash('Belum ada model terlatih. Latih model di menu Arsitektur CNN terlebih dahulu.', 'warning')
        return _render_upload(lokasi_list)

    foto_file = request.files.get('foto')
    if not foto_file or not foto_file.filename:
        flash('Pilih file foto terlebih dahulu.', 'danger')
        return _render_upload(lokasi_list)
    _progress.set(current_user.id, {'status': 'running', 'pct': 15, 'step': 'Menyimpan foto upload'})
    try:
        nama_file, path_file, ukuran_kb = save_photo(foto_file)
    except UploadError as e:
        _progress.pop(current_user.id)
        flash(str(e), 'danger')
        return _render_upload(lokasi_list)

    base_dir = os.path.dirname(current_app.root_path)
    saved_path = os.path.join(current_app.config['UPLOAD_FOLDER'], nama_file)
    # Config aktif = satu-satunya config yang menghasilkan data training (lihat PreprocessingConfig.aktif).
    prep_cfg = PreprocessingConfig.aktif()
    _progress.sederhanakan(current_user.id, pct=45, step='Preprocessing (config aktif) + inferensi CNN')
    try:
        kelas, confidence = cnn_service.predict_image(model_cfg, saved_path, base_dir, prep_cfg)
    except Exception as e:
        os.remove(saved_path)
        _progress.pop(current_user.id)
        flash(f'Prediksi gagal: {e}', 'danger')
        return _render_upload(lokasi_list)

    _progress.sederhanakan(current_user.id, pct=85, step='Menyimpan hasil klasifikasi')

    tingkat = db.session.get(TingkatKerusakan, kelas + 1)   # indeks kelas = id - 1, lihat app/kelas.py
    foto = DokumentasiFoto(lokasi_id=lokasi.id, nama_file=nama_file,
                           path_file=path_file, ukuran_kb=ukuran_kb)
    db.session.add(foto)
    db.session.flush()

    hasil = HasilKlasifikasiCnn(
        dokumentasi_id=foto.id,
        jenis_kerusakan_id=None,   # model hanya memprediksi tingkat, bukan jenis
        tingkat_kerusakan_id=tingkat.id,
        confidence_score=confidence,
        is_valid=confidence >= AMBANG_CONFIDENCE,
        catatan=(f'Model #{model_cfg.id} "{model_cfg.nama}" ' +
                 ('(model final, semua data)' if model_cfg.final_model_path else f'(model fold uji {model_cfg.fold_val})')),
    )
    db.session.add(hasil)
    db.session.flush()

    if not lokasi.peta:
        db.session.add(PetaKerusakan(
            lokasi_id=lokasi.id,
            hasil_klasifikasi_id=hasil.id,
            status_pemetaan='draft',
            prioritas_perbaikan=tingkat.skor_prioritas,
            tanggal_pemetaan=date.today(),
            pengguna_id=current_user.id,
        ))

    db.session.commit()
    _progress.pop(current_user.id)
    if confidence < AMBANG_CONFIDENCE:
        flash(f'Klasifikasi selesai, tetapi confidence hanya {confidence * 100:.0f}% (di bawah {AMBANG_CONFIDENCE * 100:.0f}%). '
              'Verifikasi manual sebelum dipakai untuk prioritas perbaikan.', 'warning')
    else:
        flash('Klasifikasi CNN berhasil.', 'success')
    return redirect(url_for('klasifikasi.hasil', hasil_id=hasil.id))


@klasifikasi_bp.route('/hasil/<int:hasil_id>')
@login_required
def hasil(hasil_id):
    hasil = HasilKlasifikasiCnn.query.get_or_404(hasil_id)
    return render_template('klasifikasi/hasil.html', hasil=hasil)


def _hapus_hasil(hasil):
    """Hapus satu hasil klasifikasi + peta turunannya + file foto (data augmentasi/dokumentasi).

    PetaKerusakan tidak cascade di DB, jadi dihapus eksplisit agar tidak jadi orphan.
    Foto asli yang diupload lewat klasifikasi memang tidak dipakai pipeline lain,
    jadi filenya ikut dibersihkan; kegagalan hapus file tidak menggagalkan DB.
    """
    root_upload = current_app.config['UPLOAD_FOLDER']
    foto = db.session.get(DokumentasiFoto, hasil.dokumentasi_id)
    if hasil.peta:
        db.session.delete(hasil.peta)
    db.session.delete(hasil)
    db.session.flush()
    if foto:
        path = os.path.join(root_upload, foto.nama_file)
        db.session.delete(foto)
        try:
            if os.path.isfile(path):
                os.remove(path)
        except OSError:
            pass


@klasifikasi_bp.route('/riwayat')
@login_required
def index():
    """Daftar semua hasil klasifikasi, terbaru dahulu, dengan aksi hapus."""
    riwayat = (HasilKlasifikasiCnn.query
               .order_by(HasilKlasifikasiCnn.created_at.desc())
               .all())
    total_perlu_verifikasi = sum(1 for h in riwayat if not h.is_valid)
    return render_template('klasifikasi/index.html', riwayat=riwayat,
                           total=len(riwayat), total_perlu_verifikasi=total_perlu_verifikasi)


@klasifikasi_bp.route('/hasil/<int:hasil_id>/delete', methods=['POST'])
@admin_required
def hasil_delete(hasil_id):
    hasil = HasilKlasifikasiCnn.query.get_or_404(hasil_id)
    _hapus_hasil(hasil)
    db.session.commit()
    flash('Hasil klasifikasi beserta foto dan peta turunannya dihapus.', 'info')
    return redirect(request.referrer or url_for('klasifikasi.index'))


@klasifikasi_bp.route('/riwayat/hapus-semua', methods=['POST'])
@admin_required
def hapus_semua():
    jumlah = 0
    for hasil in HasilKlasifikasiCnn.query.all():
        _hapus_hasil(hasil)
        jumlah += 1
    db.session.commit()
    flash(f'Semua hasil klasifikasi dihapus ({jumlah} record).', 'info')
    return redirect(url_for('klasifikasi.index'))
