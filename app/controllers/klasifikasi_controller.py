import os
import random
from datetime import date, datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.hasil_klasifikasi_cnn import HasilKlasifikasiCnn
from app.models.peta_kerusakan import PetaKerusakan
from app.models.jenis_kerusakan import JenisKerusakan
from app.models.tingkat_kerusakan import TingkatKerusakan
from app.models.lokasi_kerusakan import LokasiKerusakan

klasifikasi_bp = Blueprint('klasifikasi', __name__, url_prefix='/klasifikasi')

ALLOWED = {'png', 'jpg', 'jpeg', 'webp'}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


def _mock_predict():
    """Simulasi prediksi CNN — ganti dengan model nyata saat tersedia."""
    jenis_list   = JenisKerusakan.query.all()
    tingkat_list = TingkatKerusakan.query.all()
    jenis   = random.choice(jenis_list)
    tingkat = random.choice(tingkat_list)
    score   = round(random.uniform(0.70, 0.99), 4)
    return jenis, tingkat, score


@klasifikasi_bp.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    lokasi_list = LokasiKerusakan.query.order_by(LokasiKerusakan.nama_citra).all()

    if request.method == 'POST':
        lokasi_id = request.form.get('lokasi_id', type=int)
        foto_file = request.files.get('foto')

        if not foto_file or not _allowed(foto_file.filename):
            flash('File foto tidak valid (png/jpg/jpeg/webp).', 'danger')
            return render_template('klasifikasi/upload.html', lokasi_list=lokasi_list)

        fname     = secure_filename(foto_file.filename)
        timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
        fname     = f"{timestamp}_{fname}"
        save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], fname)
        foto_file.save(save_path)
        ukuran_kb = os.path.getsize(save_path) // 1024

        foto = DokumentasiFoto(
            lokasi_id=lokasi_id,
            nama_file=fname,
            path_file=f'uploads/foto/{fname}',
            ukuran_kb=ukuran_kb
        )
        db.session.add(foto)
        db.session.flush()

        jenis, tingkat, score = _mock_predict()

        hasil = HasilKlasifikasiCnn(
            dokumentasi_id=foto.id,
            jenis_kerusakan_id=jenis.id,
            tingkat_kerusakan_id=tingkat.id,
            confidence_score=score,
            is_valid=True
        )
        db.session.add(hasil)
        db.session.flush()

        lokasi = LokasiKerusakan.query.get(lokasi_id)
        if lokasi and not lokasi.peta:
            peta = PetaKerusakan(
                lokasi_id=lokasi_id,
                hasil_klasifikasi_id=hasil.id,
                status_pemetaan='draft',
                prioritas_perbaikan=tingkat.skor_prioritas,
                tanggal_pemetaan=date.today(),
                pengguna_id=current_user.id
            )
            db.session.add(peta)

        db.session.commit()
        flash('Klasifikasi CNN berhasil.', 'success')
        return redirect(url_for('klasifikasi.hasil', hasil_id=hasil.id))

    return render_template('klasifikasi/upload.html', lokasi_list=lokasi_list)


@klasifikasi_bp.route('/hasil/<int:hasil_id>')
@login_required
def hasil(hasil_id):
    hasil = HasilKlasifikasiCnn.query.get_or_404(hasil_id)
    return render_template('klasifikasi/hasil.html', hasil=hasil)
