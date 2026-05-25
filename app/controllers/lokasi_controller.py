import os
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app import db
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.dokumentasi_foto import DokumentasiFoto

lokasi_bp = Blueprint('lokasi', __name__, url_prefix='/lokasi')

ALLOWED = {'png', 'jpg', 'jpeg', 'webp'}


def _allowed(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED


@lokasi_bp.route('/')
@login_required
def index():
    lokasi_list = LokasiKerusakan.query.order_by(LokasiKerusakan.created_at.desc()).all()
    return render_template('lokasi/index.html', lokasi_list=lokasi_list)


@lokasi_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        nama_citra     = request.form.get('nama_citra', '').strip()
        latitude       = request.form.get('latitude')
        longitude      = request.form.get('longitude')
        panjang        = request.form.get('panjang') or None
        lebar          = request.form.get('lebar') or None
        sumber_data    = request.form.get('sumber_data', 'primer')

        lokasi = LokasiKerusakan(
            nama_citra=nama_citra,
            latitude=latitude,
            longitude=longitude,
            panjang=panjang,
            lebar=lebar,
            sumber_data=sumber_data,
            pengguna_id=current_user.id
        )
        db.session.add(lokasi)
        db.session.flush()

        foto_files = request.files.getlist('foto')
        for f in foto_files:
            if f and _allowed(f.filename):
                fname = secure_filename(f.filename)
                timestamp = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                fname = f"{timestamp}_{fname}"
                save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], fname)
                f.save(save_path)
                ukuran_kb = os.path.getsize(save_path) // 1024
                foto = DokumentasiFoto(
                    lokasi_id=lokasi.id,
                    nama_file=fname,
                    path_file=f'uploads/foto/{fname}',
                    ukuran_kb=ukuran_kb
                )
                db.session.add(foto)

        db.session.commit()
        flash('Data lokasi berhasil disimpan.', 'success')
        return redirect(url_for('lokasi.index'))

    return render_template('lokasi/create.html')


@lokasi_bp.route('/<int:lokasi_id>')
@login_required
def detail(lokasi_id):
    lokasi = LokasiKerusakan.query.get_or_404(lokasi_id)
    return render_template('lokasi/detail.html', lokasi=lokasi)


@lokasi_bp.route('/<int:lokasi_id>/delete', methods=['POST'])
@login_required
def delete(lokasi_id):
    lokasi = LokasiKerusakan.query.get_or_404(lokasi_id)
    db.session.delete(lokasi)
    db.session.commit()
    flash('Data lokasi dihapus.', 'info')
    return redirect(url_for('lokasi.index'))
