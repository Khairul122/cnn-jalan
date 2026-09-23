import os
from datetime import date

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
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

klasifikasi_bp = Blueprint('klasifikasi', __name__, url_prefix='/klasifikasi')


def _render_upload(lokasi_list):
    return render_template('klasifikasi/upload.html', lokasi_list=lokasi_list)


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
    try:
        nama_file, path_file, ukuran_kb = save_photo(foto_file)
    except UploadError as e:
        flash(str(e), 'danger')
        return _render_upload(lokasi_list)

    base_dir = os.path.dirname(current_app.root_path)
    saved_path = os.path.join(current_app.config['UPLOAD_FOLDER'], nama_file)
    prep_cfg = (PreprocessingConfig.query.filter_by(is_default=True).first()
                or PreprocessingConfig.query.first())
    try:
        kelas, confidence = cnn_service.predict_image(model_cfg, saved_path, base_dir, prep_cfg)
    except Exception as e:
        os.remove(saved_path)
        flash(f'Prediksi gagal: {e}', 'danger')
        return _render_upload(lokasi_list)

    tingkat = db.session.get(TingkatKerusakan, kelas + 1)   # 0=Berat (id 1), 1=Sedang, 2=Ringan
    foto = DokumentasiFoto(lokasi_id=lokasi.id, nama_file=nama_file,
                           path_file=path_file, ukuran_kb=ukuran_kb)
    db.session.add(foto)
    db.session.flush()

    hasil = HasilKlasifikasiCnn(
        dokumentasi_id=foto.id,
        jenis_kerusakan_id=None,   # model hanya memprediksi tingkat, bukan jenis
        tingkat_kerusakan_id=tingkat.id,
        confidence_score=confidence,
        is_valid=True,
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
    flash('Klasifikasi CNN berhasil.', 'success')
    return redirect(url_for('klasifikasi.hasil', hasil_id=hasil.id))


@klasifikasi_bp.route('/hasil/<int:hasil_id>')
@login_required
def hasil(hasil_id):
    hasil = HasilKlasifikasiCnn.query.get_or_404(hasil_id)
    return render_template('klasifikasi/hasil.html', hasil=hasil)
