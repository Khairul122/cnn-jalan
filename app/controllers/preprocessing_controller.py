import os
import threading
from types import SimpleNamespace

from app import utcnow
from flask import Blueprint, render_template, redirect, url_for, flash, request, current_app, jsonify
from flask_login import login_required, current_user
from app.auth_utils import admin_required
from app import db
from app.models.preprocessing_config import PreprocessingConfig
from app.models.hasil_preprocessing import HasilPreprocessing
from app.models.dokumentasi_foto import DokumentasiFoto
from app.progress_store import ProgressStore
from app.services.preprocessing_service import PreprocessingService

preprocessing_bp = Blueprint('preprocessing', __name__, url_prefix='/preprocessing')

PREPROCESSED_SUBDIR = os.path.join('uploads', 'preprocessed')

# Progres run pipeline di background, per config_id.
_progress = ProgressStore()
# (berhasil, gagal) terakhir per config_id, untuk flash setelah redirect.
_progress_err = {}


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
    # Hasil run background ditulis di sini, karena thread tidak punya request untuk flash().
    if request.args.get('proses') == 'selesai' and _progress_err:
        berhasil, gagal = _progress_err.pop(next(iter(_progress_err)))
        flash(f'Preprocessing selesai — {berhasil} foto berhasil ({berhasil * 4} gambar dari 4 tahap), {gagal} gagal.',
              'success' if gagal == 0 else 'warning')
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

def _simpan_progress(config_id, data):
    _progress.set(config_id, data)


def _progress_aktif(config_id):
    return _progress.get(config_id)


def _selesaikan(config_id):
    """Tandai run selesai supaya UI polling ikut pindah. Flash ditampilkan oleh
    index() lewat data sekali-pakai, bukan dari thread (thread tidak punya request)."""
    _progress.set(config_id, {'status': 'selesai', 'pct': 100, 'reload': '/preprocessing/?proses=selesai'})


def _jalankan_pipeline(app, config_id, cfg_snapshot):
    """Background thread: pipeline 4 tahap untuk semua foto + tulis progres tiap foto."""
    with app.app_context():
        upload_folder = app.config['UPLOAD_FOLDER']
        root = app.root_path
        out_folder = os.path.join(root, 'static', 'uploads', 'preprocessed')
        os.makedirs(out_folder, exist_ok=True)

        # Salinan lepas: objek config dari request tidak terikat ke session thread ini.
        cfg = SimpleNamespace(**cfg_snapshot)

        foto_list = DokumentasiFoto.query.all()
        total = len(foto_list)
        berhasil = gagal = 0
        BATCH = 20

        for i, foto in enumerate(foto_list):
            img_path = os.path.join(upload_folder, foto.nama_file)
            if not os.path.isfile(img_path):
                img_path = os.path.join(root, 'static', foto.path_file.lstrip('/\\'))

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
                        config_id       = config_id,
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
                    config_id       = config_id,
                    step_name       = 'resize',
                    path_output     = '',
                    ukuran_kb_asal  = kb_asal,
                    status          = 'gagal',
                    catatan         = str(e)[:250],
                ))
                gagal += 1

            if (i + 1) % BATCH == 0:
                db.session.commit()

            _simpan_progress(config_id, {
                'status': 'running',
                'pct': round((i + 1) / total * 100) if total else 100,
                'current': i + 1,
                'total': total,
                'step': f'Memproses {foto.nama_file}',
                'berhasil': berhasil,
                'gagal': gagal,
            })

        db.session.commit()
        _progress_err[config_id] = (berhasil, gagal)
        _selesaikan(config_id)
        db.session.remove()


@preprocessing_bp.route('/run/<int:config_id>', methods=['POST'])
@admin_required
def run(config_id):
    cfg = PreprocessingConfig.query.get_or_404(config_id)
    if _progress_aktif(config_id) and _progress_aktif(config_id).get('status') == 'running':
        flash('Preprocessing untuk konfigurasi ini sedang berjalan.', 'warning')
        return redirect(url_for('preprocessing.index'))

    try:
        _hapus_hasil(HasilPreprocessing.query)
        _hapus_hasil_turunan()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        flash(f'Gagal menyiapkan folder hasil: {e}', 'danger')
        return redirect(url_for('preprocessing.index'))

    # Nilai skalar saja: objek ORM dari request tidak boleh dipakai di thread lain.
    snapshot = {c.name: getattr(cfg, c.name)
                for c in PreprocessingConfig.__table__.columns}
    _simpan_progress(config_id, {'status': 'running', 'pct': 0, 'current': 0,
                                 'total': DokumentasiFoto.query.count(), 'step': 'Menyiapkan…'})
    app = current_app._get_current_object()
    threading.Thread(target=_jalankan_pipeline, args=(app, config_id, snapshot), daemon=True).start()
    return redirect(url_for('preprocessing.index'))


@preprocessing_bp.route('/progress/<int:config_id>')
@login_required
def progress(config_id):
    prog = _progress_aktif(config_id)
    if prog is None:
        return jsonify({'status': 'idle'})
    return jsonify(prog)


# â”€â”€ Reset semua hasil â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€

@preprocessing_bp.route('/hasil/reset', methods=['POST'])
@admin_required
def hasil_reset():
    jumlah, hapus_file = _hapus_hasil(HasilPreprocessing.query)
    _hapus_hasil_turunan()
    db.session.commit()
    flash(f'Reset selesai â€” {jumlah} record dan {hapus_file} file dihapus.', 'info')
    return redirect(url_for('preprocessing.hasil'))


@preprocessing_bp.route('/config/<int:config_id>/reset-hasil', methods=['POST'])
@admin_required
def config_reset_hasil(config_id):
    """Hapus hasil preprocessing milik satu konfigurasi saja."""
    cfg = PreprocessingConfig.query.get_or_404(config_id)
    jumlah, hapus_file = _hapus_hasil(HasilPreprocessing.query.filter_by(config_id=config_id))
    _hapus_hasil_turunan()
    db.session.commit()
    flash(f'Hasil preprocessing "{cfg.nama_config}" direset â€” {jumlah} record dan {hapus_file} file dihapus.', 'info')
    return redirect(url_for('preprocessing.index'))


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

