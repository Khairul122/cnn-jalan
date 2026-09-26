import os
import threading

from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func

from app import db
from app.auth_utils import admin_required
from app.models.augmentasi_config import AugmentasiConfig
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.hasil_augmentasi import HasilAugmentasi
from app.models.hasil_preprocessing import HasilPreprocessing
from app.services import augmentation_service as aug

import json

augmentasi_bp = Blueprint('augmentasi', __name__, url_prefix='/augmentasi')

# Progres run augmentasi di background, per config_id.
_progress = {}
_progress_hasil = {}
_progress_lock = threading.Lock()

LABEL = {
    'flip': 'Flip horizontal', 'rotasi': 'Rotasi', 'zoom': 'Zoom', 'translasi': 'Translasi',
    'brightness': 'Brightness', 'contrast': 'Contrast', 'hue': 'Hue', 'saturasi': 'Saturasi',
    'noise': 'Noise piksel', 'erasing': 'Random erasing',
}
MAKS_SALINAN = 10


def _static_root():
    return os.path.join(current_app.root_path, 'static')


def _foto_berdenoise():
    return (db.session.query(func.count(func.distinct(HasilPreprocessing.dokumentasi_id)))
            .filter(HasilPreprocessing.step_name == 'denoise', HasilPreprocessing.status == 'selesai',
                    HasilPreprocessing.path_output != '').scalar() or 0)


@augmentasi_bp.route('/')
@login_required
def index():
    config_list = AugmentasiConfig.query.order_by(AugmentasiConfig.id).all()
    total_hasil = HasilAugmentasi.query.filter_by(status='selesai').count()
    aktif = AugmentasiConfig.aktif() if total_hasil else None
    galeri = (HasilAugmentasi.query.filter_by(status='selesai').order_by(HasilAugmentasi.id.desc()).limit(24).all())
    if request.args.get('proses') == 'selesai' and _progress_hasil:
        stat = _progress_hasil.pop(next(iter(_progress_hasil)))
        flash(f'Augmentasi selesai: {stat["foto"]} foto × salinan = {stat["salinan"]} gambar, {stat["gagal"]} gagal. '
              'Salinan hanya dipakai training untuk foto fold-train; buat/ulangi Split sesudah ini bila belum.',
              'success' if not stat['gagal'] else 'warning')
    return render_template('augmentasi/index.html', config_list=config_list, aktif_id=aktif.id if aktif else None,
                           total_foto=DokumentasiFoto.query.count(), total_denoise=_foto_berdenoise(),
                           total_hasil=total_hasil, galeri=galeri)


def _params_dari_form(form):
    params = {}
    for kunci, bawaan in aug.DEFAULT_PARAMS.items():
        params[kunci] = {'aktif': bool(form.get(f'{kunci}_aktif'))}
        for k in bawaan:
            if k != 'aktif':
                params[kunci][k] = form.get(f'{kunci}_{k}', bawaan[k])
    return aug.normalisasi_params(params)


def _isi_config(cfg, form):
    cfg.nama_config = form.get('nama_config', '').strip() or 'Konfigurasi Augmentasi'
    cfg.n_salinan = max(1, min(MAKS_SALINAN, int(form.get('n_salinan') or 3)))
    cfg.seed = int(form.get('seed') or 42)
    cfg.parameter = json.dumps(_params_dari_form(form))
    cfg.is_default = bool(form.get('is_default'))
    if cfg.is_default:
        AugmentasiConfig.query.filter(AugmentasiConfig.id != (cfg.id or 0)).update({'is_default': False})


@augmentasi_bp.route('/config/new', methods=['GET', 'POST'])
@admin_required
def config_new():
    if request.method == 'POST':
        cfg = AugmentasiConfig(pengguna_id=current_user.id)
        try:
            _isi_config(cfg, request.form)
        except ValueError as e:
            flash(f'Input tidak valid: {e}', 'warning')
            return redirect(url_for('augmentasi.config_new'))
        db.session.add(cfg)
        db.session.commit()
        flash(f'Konfigurasi "{cfg.nama_config}" disimpan.', 'success')
        return redirect(url_for('augmentasi.index'))
    return render_template('augmentasi/config_form.html', config=None, params=aug.default_params(), label=LABEL,
                           n_salinan=3, seed=42)


@augmentasi_bp.route('/config/<int:config_id>/edit', methods=['GET', 'POST'])
@admin_required
def config_edit(config_id):
    cfg = AugmentasiConfig.query.get_or_404(config_id)
    if request.method == 'POST':
        if HasilAugmentasi.query.filter_by(config_id=cfg.id).count():
            flash('Config ini sedang aktif (sudah punya hasil augmentasi). Reset hasil dulu sebelum mengubah parameternya.', 'warning')
            return redirect(url_for('augmentasi.index'))
        try:
            _isi_config(cfg, request.form)
        except ValueError as e:
            flash(f'Input tidak valid: {e}', 'warning')
            return redirect(url_for('augmentasi.config_edit', config_id=cfg.id))
        db.session.commit()
        flash(f'Konfigurasi "{cfg.nama_config}" diperbarui.', 'success')
        return redirect(url_for('augmentasi.index'))
    return render_template('augmentasi/config_form.html', config=cfg, params=aug.normalisasi_params(cfg.get_parameter()),
                           label=LABEL, n_salinan=cfg.n_salinan, seed=cfg.seed)


@augmentasi_bp.route('/config/<int:config_id>/delete', methods=['POST'])
@admin_required
def config_delete(config_id):
    cfg = AugmentasiConfig.query.get_or_404(config_id)
    aug.hapus_semua_hasil(_static_root(), HasilAugmentasi.query.filter_by(config_id=cfg.id))
    db.session.delete(cfg)
    db.session.commit()
    flash(f'Konfigurasi "{cfg.nama_config}" dihapus.', 'info')
    return redirect(url_for('augmentasi.index'))


def _simpan_progress(config_id, data):
    with _progress_lock:
        _progress[config_id] = data


def _sisa_progress(config_id):
    with _progress_lock:
        return _progress.get(config_id)


def _run_augmentasi(app, config_id):
    """Background thread: salinan augmentasi untuk semua foto + tulis progres tiap 20 foto."""
    total_foto = _foto_berdenoise()
    try:
        stat = aug.jalankan(db.session.get(AugmentasiConfig, config_id), _static_root(),
                            on_progress=lambda selesai, total: _simpan_progress(config_id, {
                                'status': 'running',
                                'pct': round(selesai / total * 100) if total else 100,
                                'current': selesai, 'total': total,
                                'step': f'Membuat salinan — foto {selesai} / {total}',
                            }))
        db.session.commit()
        _progress_hasil[config_id] = stat
        _simpan_progress(config_id, {'status': 'selesai', 'pct': 100,
                                     'reload': url_for('augmentasi.index', proses='selesai')})
    except Exception as exc:      # noqa: BLE001 — semua error jadi pesan UI
        db.session.rollback()
        _simpan_progress(config_id, {'status': 'error', 'error': f'Augmentasi gagal: {exc}'})
    finally:
        db.session.remove()


@augmentasi_bp.route('/run/<int:config_id>', methods=['POST'])
@admin_required
def run(config_id):
    cfg = AugmentasiConfig.query.get_or_404(config_id)
    if not _foto_berdenoise():
        flash('Belum ada hasil preprocessing (tahap denoise). Jalankan Preprocessing dulu.', 'warning')
        return redirect(url_for('augmentasi.index'))
    if (_sisa_progress(config_id) or {}).get('status') == 'running':
        flash('Augmentasi untuk konfigurasi ini sedang berjalan.', 'warning')
        return redirect(url_for('augmentasi.index'))

    # Satu config aktif: hasil augmentasi sebelumnya (config manapun) diganti.
    aug.hapus_semua_hasil(_static_root())
    db.session.commit()

    total = _foto_berdenoise()
    _simpan_progress(config_id, {'status': 'running', 'pct': 0, 'current': 0, 'total': total,
                                 'step': f'Membuat {cfg.n_salinan} salinan per foto…'})
    app = current_app._get_current_object()
    threading.Thread(target=_run_augmentasi, args=(app, config_id), daemon=True).start()
    return redirect(url_for('augmentasi.index'))


@augmentasi_bp.route('/progress/<int:config_id>')
@login_required
def progress(config_id):
    prog = _sisa_progress(config_id)
    if prog is None:
        return jsonify({'status': 'idle'})
    return jsonify(prog)


@augmentasi_bp.route('/hasil/reset', methods=['POST'])
@admin_required
def hasil_reset():
    jumlah, n_file = aug.hapus_semua_hasil(_static_root())
    db.session.commit()
    flash(f'Reset selesai — {jumlah} record dan {n_file} file dihapus.', 'info')
    return redirect(url_for('augmentasi.index'))
