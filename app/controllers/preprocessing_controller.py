import os
from app import utcnow
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app
from flask_login import login_required, current_user
from app.auth_utils import admin_required
from app import db
from app.models.preprocessing_config import PreprocessingConfig
from app.models.hasil_preprocessing import HasilPreprocessing
from app.models.dokumentasi_foto import DokumentasiFoto
from app.services.preprocessing_service import PreprocessingService

preprocessing_bp = Blueprint('preprocessing', __name__, url_prefix='/preprocessing')

PREPROCESSED_SUBDIR = os.path.join('uploads', 'preprocessed')


def _hapus_hasil(query):
    """Hapus file fisik lalu record HasilPreprocessing dari `query`. Return (jumlah_record, jumlah_file)."""
    root = os.path.join(current_app.root_path, 'static')
    n_file = 0
    for h in query.filter(HasilPreprocessing.path_output != '', HasilPreprocessing.path_output.isnot(None)).all():
        path = os.path.join(root, h.path_output)
        if os.path.isfile(path):
            try:
                os.remove(path)
                n_file += 1
            except OSError:
                pass
    return query.delete(synchronize_session=False), n_file


def _hapus_hasil_turunan():
    """Augmentasi dibuat dari hasil denoise; kalau hasil preprocessing berubah, hasil augmentasi ikut basi."""
    from app.services import augmentation_service
    augmentation_service.hapus_semua_hasil(os.path.join(current_app.root_path, 'static'))


def _preprocessed_folder():
    base = os.path.join(current_app.root_path, 'static', 'uploads', 'preprocessed')
    os.makedirs(base, exist_ok=True)
    return base


# â”€â”€ Index â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@preprocessing_bp.route('/')
@login_required
def index():
    config_list  = PreprocessingConfig.query.order_by(PreprocessingConfig.id).all()
    total_foto   = DokumentasiFoto.query.count()
    total_hasil  = HasilPreprocessing.query.count()
    total_config = len(config_list)
    aktif = PreprocessingConfig.aktif() if total_hasil else None
    return render_template('preprocessing/index.html',
                           config_list=config_list,
                           aktif_id=aktif.id if aktif else None,
                           total_foto=total_foto,
                           total_hasil=total_hasil,
                           total_config=total_config)


# â”€â”€ Config baru â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@preprocessing_bp.route('/config/new', methods=['GET', 'POST'])
@admin_required
def config_new():
    if request.method == 'POST':
        cfg = _config_from_form(request.form)
        cfg.pengguna_id = current_user.id
        db.session.add(cfg)
        db.session.commit()
        flash(f'Konfigurasi "{cfg.nama_config}" berhasil disimpan.', 'success')
        return redirect(url_for('preprocessing.index'))
    return render_template('preprocessing/config_form.html', config=None, action='new')


# â”€â”€ Edit config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@preprocessing_bp.route('/config/<int:config_id>/edit', methods=['GET', 'POST'])
@admin_required
def config_edit(config_id):
    cfg = PreprocessingConfig.query.get_or_404(config_id)
    if request.method == 'POST':
        if HasilPreprocessing.query.filter_by(config_id=cfg.id).count():
            flash('Config ini sedang aktif (sudah punya hasil preprocessing). Reset hasil dulu sebelum mengubah '
                  'parameternya, supaya data training tidak berbeda dari config yang tersimpan.', 'warning')
            return redirect(url_for('preprocessing.index'))
        _update_config_from_form(cfg, request.form)
        db.session.commit()
        flash(f'Konfigurasi "{cfg.nama_config}" diperbarui.', 'success')
        return redirect(url_for('preprocessing.index'))
    return render_template('preprocessing/config_form.html', config=cfg, action='edit')


# â”€â”€ Hapus config â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@preprocessing_bp.route('/config/<int:config_id>/delete', methods=['POST'])
@admin_required
def config_delete(config_id):
    cfg = PreprocessingConfig.query.get_or_404(config_id)
    nama = cfg.nama_config
    _hapus_hasil(HasilPreprocessing.query.filter_by(config_id=cfg.id))
    _hapus_hasil_turunan()
    db.session.delete(cfg)
    db.session.commit()
    flash(f'Konfigurasi "{nama}" dihapus.', 'info')
    return redirect(url_for('preprocessing.index'))


# â”€â”€ Jalankan pipeline â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@preprocessing_bp.route('/run/<int:config_id>', methods=['POST'])
@admin_required
def run(config_id):
    cfg = PreprocessingConfig.query.get_or_404(config_id)
    # Hanya satu config yang boleh punya hasil (config aktif): hasil lama dari config manapun diganti.
    _hapus_hasil(HasilPreprocessing.query)
    _hapus_hasil_turunan()
    db.session.commit()

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
                ts       = utcnow().strftime('%Y%m%d%H%M%S%f')
                out_name = f'{ts}_{step_key}_{foto.nama_file}'
                out_path = os.path.join(out_folder, out_name)
                rel_path = f'uploads/preprocessed/{out_name}'

                PreprocessingService.save_result(step_img, out_path)
                kb_hasil = PreprocessingService.get_file_kb(out_path)

                db.session.add(HasilPreprocessing(
                    dokumentasi_id  = foto.id,
                    config_id       = cfg.id,
                    step_name       = step_key,
                    path_output     = rel_path,
                    ukuran_kb_asal  = kb_asal,
                    ukuran_kb_hasil = kb_hasil,
                    durasi_ms       = durasi_ms,
                    status          = 'selesai',
                ))
            berhasil += 1
        except Exception as e:
            db.session.add(HasilPreprocessing(
                dokumentasi_id  = foto.id,
                config_id       = cfg.id,
                step_name       = 'resize',
                path_output     = '',
                ukuran_kb_asal  = kb_asal,
                status          = 'gagal',
                catatan         = str(e)[:250],
            ))
            gagal += 1

        if (i + 1) % BATCH == 0:
            db.session.commit()

    db.session.commit()
    total_gambar = berhasil * 4   # 4 tahap per foto
    flash(f'Preprocessing selesai â€” {berhasil} foto berhasil ({total_gambar} gambar dari 4 tahap), {gagal} gagal.',
          'success' if gagal == 0 else 'warning')
    return redirect(url_for('preprocessing.hasil'))


# â”€â”€ Reset semua hasil â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@preprocessing_bp.route('/hasil/reset', methods=['POST'])
@admin_required
def hasil_reset():
    jumlah, hapus_file = _hapus_hasil(HasilPreprocessing.query)
    _hapus_hasil_turunan()
    db.session.commit()
    flash(f'Reset selesai â€” {jumlah} record dan {hapus_file} file dihapus.', 'info')
    return redirect(url_for('preprocessing.hasil'))


# â”€â”€ Hasil â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

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
                   for s in ('semua', 'resize', 'crop', 'normalisasi', 'denoise')}

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


# â”€â”€ Helper â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

def _config_from_form(form):
    cfg = PreprocessingConfig()
    _update_config_from_form(cfg, form)
    return cfg


def _update_config_from_form(cfg, form):
    cfg.nama_config    = form.get('nama_config', '').strip() or 'Konfigurasi Baru'
    cfg.target_width   = int(form.get('target_width', 256))
    cfg.target_height  = int(form.get('target_height', 256))
    cfg.resize_method  = form.get('resize_method', 'LANCZOS')
    cfg.resize_mode    = form.get('resize_mode', 'stretch')
    cfg.illum_correction = bool(form.get('illum_correction'))
    cfg.crop_enabled   = bool(form.get('crop_enabled'))
    cfg.crop_width     = int(form.get('crop_width', 224))
    cfg.crop_height    = int(form.get('crop_height', 224))
    cfg.norm_method    = form.get('norm_method', 'none')
    cfg.denoise_method = form.get('denoise_method', 'bilateral')
    cfg.denoise_ksize  = int(form.get('denoise_ksize', 3))
    cfg.is_default     = bool(form.get('is_default'))

