from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required, current_user
from app.auth_utils import admin_required
from app.uploads import UploadError, save_photo
from app import db
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.dokumentasi_foto import DokumentasiFoto

lokasi_bp = Blueprint('lokasi', __name__, url_prefix='/lokasi')

KETERANGAN = ('Ukur', 'Estimasi (Ringan)', 'Estimasi (Sedang)', 'Estimasi (Berat)')


def _meter(value):
    """Nilai form (meter) → float, atau None jika kosong/tidak valid."""
    try:
        return float(str(value).replace(',', '.'))
    except (TypeError, ValueError):
        return None


@lokasi_bp.route('/')
@login_required
def index():
    lokasi_list = LokasiKerusakan.query.order_by(LokasiKerusakan.created_at.desc()).all()
    return render_template('lokasi/index.html', lokasi_list=lokasi_list)


@lokasi_bp.route('/create', methods=['GET', 'POST'])
@admin_required
def create():
    if request.method == 'POST':
        nama_citra     = request.form.get('nama_citra', '').strip()
        latitude       = request.form.get('latitude')
        longitude      = request.form.get('longitude')
        panjang        = _meter(request.form.get('panjang'))
        lebar          = _meter(request.form.get('lebar'))
        keterangan     = request.form.get('keterangan')
        if keterangan not in KETERANGAN:
            keterangan = None
        sumber_data    = request.form.get('sumber_data', 'primer')

        lokasi = LokasiKerusakan(
            nama_citra=nama_citra,
            latitude=latitude,
            longitude=longitude,
            panjang=panjang,
            lebar=lebar,
            keterangan=keterangan,
            sumber_data=sumber_data,
            pengguna_id=current_user.id
        )
        db.session.add(lokasi)
        db.session.flush()

        for f in request.files.getlist('foto'):
            if not f or not f.filename:
                continue
            try:
                nama_file, path_file, ukuran_kb = save_photo(f)
            except UploadError as e:
                flash(f'{f.filename}: {e}', 'warning')
                continue
            db.session.add(DokumentasiFoto(lokasi_id=lokasi.id, nama_file=nama_file,
                                           path_file=path_file, ukuran_kb=ukuran_kb))

        db.session.commit()
        flash('Data lokasi berhasil disimpan.', 'success')
        return redirect(url_for('lokasi.index'))

    return render_template('lokasi/create.html', keterangan_list=KETERANGAN)


@lokasi_bp.route('/<int:lokasi_id>')
@login_required
def detail(lokasi_id):
    lokasi = LokasiKerusakan.query.get_or_404(lokasi_id)
    return render_template('lokasi/detail.html', lokasi=lokasi)


@lokasi_bp.route('/<int:lokasi_id>/delete', methods=['POST'])
@admin_required
def delete(lokasi_id):
    lokasi = LokasiKerusakan.query.get_or_404(lokasi_id)
    db.session.delete(lokasi)
    db.session.commit()
    flash('Data lokasi dihapus.', 'info')
    return redirect(url_for('lokasi.index'))
