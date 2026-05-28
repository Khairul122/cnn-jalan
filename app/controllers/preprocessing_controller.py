import os
from datetime import datetime
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app import db
from app.models.preprocessing_config import PreprocessingConfig
from app.models.hasil_preprocessing import HasilPreprocessing
from app.models.dokumentasi_foto import DokumentasiFoto
from app.services.preprocessing_service import PreprocessingService

preprocessing_bp = Blueprint('preprocessing', __name__, url_prefix='/preprocessing')

PREPROCESSED_SUBDIR = os.path.join('uploads', 'preprocessed')


def _preprocessed_folder():
    base = os.path.join(current_app.root_path, 'static', 'uploads', 'preprocessed')
    os.makedirs(base, exist_ok=True)
    return base


# ── Index ─────────────────────────────────────────────────────────────────────

@preprocessing_bp.route('/')
@login_required
def index():
    config_list  = PreprocessingConfig.query.order_by(PreprocessingConfig.id).all()
    total_foto   = DokumentasiFoto.query.count()
    total_hasil  = HasilPreprocessing.query.count()
    total_config = len(config_list)
    return render_template('preprocessing/index.html',
                           config_list=config_list,
                           total_foto=total_foto,
                           total_hasil=total_hasil,
                           total_config=total_config)


# ── Config baru ───────────────────────────────────────────────────────────────

@preprocessing_bp.route('/config/new', methods=['GET', 'POST'])
@login_required
def config_new():
    if request.method == 'POST':
        cfg = _config_from_form(request.form)
        cfg.pengguna_id = current_user.id
        db.session.add(cfg)
        db.session.commit()
        flash(f'Konfigurasi "{cfg.nama_config}" berhasil disimpan.', 'success')
        return redirect(url_for('preprocessing.index'))
    return render_template('preprocessing/config_form.html', config=None, action='new')


# ── Edit config ───────────────────────────────────────────────────────────────

@preprocessing_bp.route('/config/<int:config_id>/edit', methods=['GET', 'POST'])
@login_required
def config_edit(config_id):
    cfg = PreprocessingConfig.query.get_or_404(config_id)
    if request.method == 'POST':
        _update_config_from_form(cfg, request.form)
        db.session.commit()
        flash(f'Konfigurasi "{cfg.nama_config}" diperbarui.', 'success')
        return redirect(url_for('preprocessing.index'))
    return render_template('preprocessing/config_form.html', config=cfg, action='edit')


# ── Hapus config ──────────────────────────────────────────────────────────────

@preprocessing_bp.route('/config/<int:config_id>/delete', methods=['POST'])
@login_required
def config_delete(config_id):
    cfg = PreprocessingConfig.query.get_or_404(config_id)
    nama = cfg.nama_config
    db.session.delete(cfg)
    db.session.commit()
    flash(f'Konfigurasi "{nama}" dihapus.', 'info')
    return redirect(url_for('preprocessing.index'))


# ── Jalankan pipeline ─────────────────────────────────────────────────────────

@preprocessing_bp.route('/run/<int:config_id>', methods=['POST'])
@login_required
def run(config_id):
    cfg       = PreprocessingConfig.query.get_or_404(config_id)
    foto_list = DokumentasiFoto.query.all()
    out_folder = _preprocessed_folder()
    upload_folder = current_app.config['UPLOAD_FOLDER']

    berhasil = 0
    gagal    = 0
    BATCH    = 20

    for i, foto in enumerate(foto_list):
        img_path = os.path.join(upload_folder, foto.nama_file)
        if not os.path.isfile(img_path):
            img_path = os.path.join(current_app.root_path, 'static', foto.path_file.lstrip('/\\'))

        kb_asal = PreprocessingService.get_file_kb(img_path)

        try:
            steps = PreprocessingService.run_pipeline_steps(img_path, cfg)
            for step_key, step_img, durasi_ms in steps:
                ts       = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
                out_name = f'{ts}_{step_key}_{foto.nama_file}'
                out_path = os.path.join(out_folder, out_name)
                rel_path = f'uploads/preprocessed/{out_name}'

                PreprocessingService.save_result(step_img, out_path)
                kb_hasil = PreprocessingService.get_file_kb(out_path)

                hasil = HasilPreprocessing(
                    dokumentasi_id  = foto.id,
                    config_id       = cfg.id,
                    step_name       = step_key,
                    path_output     = rel_path,
                    ukuran_kb_asal  = kb_asal,
                    ukuran_kb_hasil = kb_hasil,
                    durasi_ms       = durasi_ms,
                    status          = 'selesai',
                )
                db.session.add(hasil)
            berhasil += 1
        except Exception as e:
            hasil = HasilPreprocessing(
                dokumentasi_id  = foto.id,
                config_id       = cfg.id,
                step_name       = 'resize',
                path_output     = '',
                ukuran_kb_asal  = kb_asal,
                status          = 'gagal',
                catatan         = str(e)[:250],
            )
            db.session.add(hasil)
            gagal += 1

        if (i + 1) % BATCH == 0:
            db.session.commit()

    db.session.commit()
    total_gambar = berhasil * 5
    flash(f'Preprocessing selesai — {berhasil} foto berhasil ({total_gambar} gambar dari 5 tahap), {gagal} gagal.',
          'success' if gagal == 0 else 'warning')
    return redirect(url_for('preprocessing.hasil'))


# ── Reset semua hasil ────────────────────────────────────────────────────────

@preprocessing_bp.route('/hasil/reset', methods=['POST'])
@login_required
def hasil_reset():
    # Hapus file fisik terlebih dahulu sebelum delete record DB
    hasil_list = HasilPreprocessing.query.filter(
        HasilPreprocessing.path_output != '',
        HasilPreprocessing.path_output.isnot(None),
    ).all()

    hapus_file = 0
    for h in hasil_list:
        file_path = os.path.join(current_app.root_path, 'static', h.path_output)
        if os.path.isfile(file_path):
            try:
                os.remove(file_path)
                hapus_file += 1
            except OSError:
                pass

    jumlah = HasilPreprocessing.query.delete()
    db.session.commit()
    flash(f'Reset selesai — {jumlah} record dan {hapus_file} file dihapus.', 'info')
    return redirect(url_for('preprocessing.hasil'))


# ── Hasil ─────────────────────────────────────────────────────────────────────

@preprocessing_bp.route('/hasil')
@login_required
def hasil():
    config_id   = request.args.get('config_id', type=int)
    step        = request.args.get('step', 'semua')
    page        = request.args.get('page', 1, type=int)
    per_page    = 24
    config_list = PreprocessingConfig.query.order_by(PreprocessingConfig.id).all()

    def build_q(s='semua'):
        q = HasilPreprocessing.query
        if config_id:
            q = q.filter(HasilPreprocessing.config_id == config_id)
        if s != 'semua':
            q = q.filter(HasilPreprocessing.step_name == s)
        return q

    total       = build_q(step).count()
    hasil_list  = build_q(step).order_by(HasilPreprocessing.created_at.desc()) \
                               .offset((page - 1) * per_page).limit(per_page).all()
    total_pages = max(1, (total + per_page - 1) // per_page)

    step_counts = {s: build_q(s).count()
                   for s in ('semua', 'resize', 'crop', 'normalisasi', 'augmentasi', 'denoise')}

    return render_template('preprocessing/hasil.html',
                           hasil_list=hasil_list,
                           config_list=config_list,
                           config_id=config_id,
                           step=step,
                           step_counts=step_counts,
                           page=page,
                           total=total,
                           total_pages=total_pages,
                           per_page=per_page)


# ── Helper ────────────────────────────────────────────────────────────────────

def _config_from_form(form):
    cfg = PreprocessingConfig()
    _update_config_from_form(cfg, form)
    return cfg


def _update_config_from_form(cfg, form):
    cfg.nama_config    = form.get('nama_config', '').strip() or 'Konfigurasi Baru'
    cfg.target_width   = int(form.get('target_width', 224))
    cfg.target_height  = int(form.get('target_height', 224))
    cfg.resize_method  = form.get('resize_method', 'LANCZOS')
    cfg.crop_enabled   = bool(form.get('crop_enabled'))
    cfg.crop_width     = int(form.get('crop_width', 224))
    cfg.crop_height    = int(form.get('crop_height', 224))
    cfg.norm_method    = form.get('norm_method', 'minmax')
    cfg.aug_flip_h     = bool(form.get('aug_flip_h'))
    cfg.aug_flip_v     = bool(form.get('aug_flip_v'))
    cfg.aug_rotate_deg = float(form.get('aug_rotate_deg', 0))
    cfg.aug_brightness = float(form.get('aug_brightness', 1.0))
    cfg.aug_contrast   = float(form.get('aug_contrast', 1.0))
    cfg.denoise_method = form.get('denoise_method', 'none')
    cfg.denoise_ksize  = int(form.get('denoise_ksize', 3))
    cfg.is_default     = bool(form.get('is_default'))
