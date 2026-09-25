import json

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app import db
from app.auth_utils import admin_required
from app.models.hasil_labeling import HasilLabeling
from app.models.label_kerusakan import LabelKerusakan
from app.models.labeling_config import LabelingConfig
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.tingkat_kerusakan import TingkatKerusakan
from app.services import labeling_service

label_bp = Blueprint('label', __name__, url_prefix='/label')


def _config_from_form(config=None):
    values = {
        'nama_config': request.form.get('nama_config', '').strip(),
        'n_cluster': request.form.get('n_cluster', type=int),
        'pca_komponen': request.form.get('pca_komponen', type=int),
        'random_state': request.form.get('random_state', type=int),
        'canny_low': request.form.get('canny_low', type=int),
        'canny_high': request.form.get('canny_high', type=int),
        'is_default': request.form.get('is_default') == 'on',
    }
    if not values['nama_config']:
        raise ValueError('Nama konfigurasi wajib diisi.')
    if not 2 <= (values['n_cluster'] or 0) <= 20:
        raise ValueError('Jumlah klaster harus antara 2 dan 20.')
    if not 1 <= (values['pca_komponen'] or 0) <= 512:
        raise ValueError('Komponen PCA harus antara 1 dan 512.')
    if not 0 <= (values['canny_low'] or -1) <= 255:
        raise ValueError('Canny low harus antara 0 dan 255.')
    if not 0 <= (values['canny_high'] or -1) <= 255:
        raise ValueError('Canny high harus antara 0 dan 255.')
    if values['canny_low'] >= values['canny_high']:
        raise ValueError('Canny low harus lebih kecil dari Canny high.')

    if config is None:
        config = LabelingConfig(pengguna_id=current_user.id)
        db.session.add(config)
    for key, value in values.items():
        setattr(config, key, value)
    return config


@label_bp.route('/')
@login_required
def index():
    lokasi_list = LokasiKerusakan.query.order_by(LokasiKerusakan.id).all()
    config_list = LabelingConfig.query.order_by(LabelingConfig.id.desc()).all()
    run_list = HasilLabeling.query.order_by(HasilLabeling.id.desc()).limit(10).all()
    return render_template(
        'label/index.html', lokasi_list=lokasi_list,
        config_list=config_list, run_list=run_list,
    )


@label_bp.route('/<int:lokasi_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit(lokasi_id):
    lokasi = LokasiKerusakan.query.get_or_404(lokasi_id)
    label = LabelKerusakan.query.filter_by(lokasi_id=lokasi_id).first()
    tingkat_list = TingkatKerusakan.query.order_by(TingkatKerusakan.skor_prioritas.desc()).all()

    if request.method == 'POST':
        tingkat_id = request.form.get('tingkat_kerusakan_id', type=int)
        catatan = request.form.get('catatan', '').strip() or None
        if not tingkat_id or db.session.get(TingkatKerusakan, tingkat_id) is None:
            flash('Tingkat kerusakan wajib dipilih.', 'danger')
        else:
            if label is None:
                label = LabelKerusakan(lokasi_id=lokasi_id, pengguna_id=current_user.id)
                db.session.add(label)
            label.tingkat_kerusakan_id = tingkat_id
            label.metode = 'manual'
            label.catatan = catatan
            label.pengguna_id = current_user.id
            db.session.commit()
            flash('Label berhasil disimpan.', 'success')
            return redirect(url_for('label.index'))

    return render_template('label/edit.html', lokasi=lokasi, label=label, tingkat_list=tingkat_list)


@label_bp.route('/<int:lokasi_id>/delete', methods=['POST'])
@admin_required
def delete(lokasi_id):
    label = LabelKerusakan.query.filter_by(lokasi_id=lokasi_id).first_or_404()
    db.session.delete(label)
    db.session.commit()
    flash('Label dihapus.', 'info')
    return redirect(url_for('label.index'))


@label_bp.route('/hapus-semua', methods=['POST'])
@admin_required
def hapus_semua():
    jumlah = LabelKerusakan.query.delete()
    db.session.commit()
    flash(f'Semua label dihapus ({jumlah} record).', 'info')
    return redirect(url_for('label.index'))


@label_bp.route('/config/new', methods=['GET', 'POST'])
@admin_required
def config_new():
    config = LabelingConfig(
        nama_config='Konfigurasi K-Means Baru',
        n_cluster=4, pca_komponen=50, random_state=42,
        canny_low=50, canny_high=150, pengguna_id=current_user.id,
    )
    if request.method == 'POST':
        try:
            config = _config_from_form()
            db.session.commit()
            flash('Konfigurasi labeling disimpan.', 'success')
            return redirect(url_for('label.index'))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), 'danger')
    return render_template('label/config_form.html', config=config, action='new')


@label_bp.route('/config/<int:config_id>/edit', methods=['GET', 'POST'])
@admin_required
def config_edit(config_id):
    config = LabelingConfig.query.get_or_404(config_id)
    if request.method == 'POST':
        try:
            _config_from_form(config)
            db.session.commit()
            flash('Konfigurasi labeling diperbarui.', 'success')
            return redirect(url_for('label.index'))
        except ValueError as exc:
            db.session.rollback()
            flash(str(exc), 'danger')
    return render_template('label/config_form.html', config=config, action='edit')


@label_bp.route('/config/<int:config_id>/delete', methods=['POST'])
@admin_required
def config_delete(config_id):
    config = LabelingConfig.query.get_or_404(config_id)
    db.session.delete(config)
    db.session.commit()
    flash('Konfigurasi labeling dihapus.', 'info')
    return redirect(url_for('label.index'))


@label_bp.route('/config/<int:config_id>/run', methods=['POST'])
@admin_required
def run(config_id):
    config = LabelingConfig.query.get_or_404(config_id)
    hasil = labeling_service.jalankan_klasterisasi(
        config, current_app.config['UPLOAD_FOLDER'], current_user.id
    )
    if hasil.status == 'gagal':
        flash(f'Klasterisasi gagal: {hasil.catatan}', 'danger')
        return redirect(url_for('label.index'))
    flash(
        f'Klasterisasi selesai — {hasil.jumlah_lokasi} lokasi diproses, '
        f'{hasil.jumlah_dilewati} dilewati. Review sebelum menerapkan.', 'info'
    )
    return redirect(url_for('label.review', run_id=hasil.id))


@label_bp.route('/review/<int:run_id>')
@admin_required
def review(run_id):
    run = HasilLabeling.query.get_or_404(run_id)
    items_per_kelas = {}
    for item in run.item_list:
        name = item.tingkat.nama_tingkat
        items_per_kelas.setdefault(name, []).append(item)
    items_per_kelas = {name: items[:5] for name, items in items_per_kelas.items()}
    distribution = json.loads(run.distribusi_kelas or '{}')
    return render_template(
        'label/review.html', run=run, items_per_kelas=items_per_kelas,
        distribution=distribution,
    )


@label_bp.route('/review/<int:run_id>/terapkan', methods=['POST'])
@admin_required
def review_terapkan(run_id):
    run = HasilLabeling.query.get_or_404(run_id)
    if run.is_diterapkan:
        flash('Hasil ini sudah pernah diterapkan.', 'warning')
    else:
        jumlah = labeling_service.terapkan_hasil(run)
        flash(f'{jumlah} label berhasil diterapkan.', 'success')
    return redirect(url_for('label.index'))


@label_bp.route('/review/<int:run_id>/buang', methods=['POST'])
@admin_required
def review_buang(run_id):
    run = HasilLabeling.query.get_or_404(run_id)
    labeling_service.buang_hasil(run)
    flash('Hasil klasterisasi dibuang.', 'info')
    return redirect(url_for('label.index'))
