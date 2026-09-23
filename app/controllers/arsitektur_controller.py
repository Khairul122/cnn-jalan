import os
import traceback
import threading
from types import SimpleNamespace
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app.auth_utils import admin_required, require_admin
from app import db
from app.models.arsitektur_config import ArsitekturConfig
from app.models.hasil_training import HasilTraining
from app.models.hasil_evaluasi import HasilEvaluasi
from app.models.prediksi_model import PrediksiModel
from app.models.split_config import SplitConfig
from app.models.dokumentasi_foto import DokumentasiFoto
from app.services.metrics_service import cv_summary
from app.services.split_service import jumlah_label_basi

arsitektur_bp = Blueprint('arsitektur', __name__, url_prefix='/arsitektur')

# Progress store: {config_id: {phase, current, total, pct, ...}}
_progress    = {}
# CV predict progress: {config_id: {fold, total_folds, epoch, total_epochs, pct}}
_cv_progress = {}
# Error store: {config_id: error_message} â€” persists after training ends for UI display
_errors      = {}
# Model final yang sedang dilatih: {config_id: True}
_final_progress = {}


def _save_evaluasi(config_id, result):
    HasilEvaluasi.query.filter_by(arsitektur_id=config_id).delete(synchronize_session=False)
    ev = HasilEvaluasi(
        arsitektur_id    = config_id,
        total_data_val   = result['total_data_val'],
        akurasi          = result['akurasi'],
        confusion_matrix = result['confusion_matrix'],
        precision_berat  = result['per_class']['berat']['precision'],
        recall_berat     = result['per_class']['berat']['recall'],
        f1_berat         = result['per_class']['berat']['f1-score'],
        precision_sedang = result['per_class']['sedang']['precision'],
        recall_sedang    = result['per_class']['sedang']['recall'],
        f1_sedang        = result['per_class']['sedang']['f1-score'],
        precision_ringan = result['per_class']['ringan']['precision'],
        recall_ringan    = result['per_class']['ringan']['recall'],
        f1_ringan        = result['per_class']['ringan']['f1-score'],
        macro_precision  = result['macro']['precision'],
        macro_recall     = result['macro']['recall'],
        macro_f1         = result['macro']['f1'],
    )
    db.session.add(ev)
    db.session.commit()


def _rerun_evaluasi(config_id, cfg):
    from app.services import cnn_service

    if cfg.status != 'selesai' or not cfg.model_path:
        flash('Model belum selesai dilatih.', 'warning')
        return

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        result = cnn_service.evaluate(cfg, base_dir)
        _save_evaluasi(config_id, result)
        flash('Evaluasi berhasil diperbarui.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Evaluasi gagal: {e}', 'danger')


def _run_training(app, config_id, base_dir):
    """Background thread: training â†’ auto evaluasi â†’ DB write."""
    with app.app_context():
        from app.services import cnn_service

        cfg = db.session.get(ArsitekturConfig, config_id)
        if not cfg:
            return

        _progress[config_id] = {'phase': 'training', 'current': 0, 'total': cfg.epochs, 'pct': 0}

        _cfg_snapshot = {
            'id':              cfg.id,
            'split_config_id': cfg.split_config_id,
            'fold_val':        cfg.fold_val,
            'input_size':      cfg.input_size,
            'model_type':      cfg.model_type,
            'dropout_rate':    cfg.dropout_rate,
            'optimizer':       cfg.optimizer,
            'learning_rate':   cfg.learning_rate,
            'batch_size':      cfg.batch_size,
            'epochs':          cfg.epochs,
            'patience':        cfg.patience,
        }
        db.session.remove()

        def on_epoch_end(epoch, total, logs):
            _progress[config_id] = {
                'phase':        'fine_tuning' if logs.get('fine_tuning') else 'training',
                'current':      epoch,
                'total':        total,
                'pct':          round(epoch / total * 100),
                'loss':         round(logs.get('loss', 0), 4),
                'accuracy':     round(logs.get('accuracy', 0) * 100, 2),
                'val_loss':     round(logs.get('val_loss', 0), 4),
                'val_accuracy': round(logs.get('val_accuracy', 0) * 100, 2),
            }

        try:
            cfg_obj = SimpleNamespace()
            for k, v in _cfg_snapshot.items():
                setattr(cfg_obj, k, v)

            model, history = cnn_service.train(cfg_obj, base_dir, on_epoch_end=on_epoch_end)

            rows = [
                HasilTraining(
                    arsitektur_id=config_id,
                    epoch=i + 1,
                    loss=history['loss'][i],
                    accuracy=history['accuracy'][i],
                    val_loss=history['val_loss'][i],
                    val_accuracy=history['val_accuracy'][i],
                )
                for i in range(len(history['loss']))
            ]
            db.session.bulk_save_objects(rows)

            model_path = cnn_service.save_model(model, config_id, base_dir)

            # Simpan model_path saja, status tetap 'training' sampai semua selesai
            ArsitekturConfig.query.filter_by(id=config_id).update({'model_path': model_path})
            db.session.commit()
            db.session.remove()

            # â”€â”€ Auto evaluasi â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            _progress[config_id] = {'phase': 'evaluating', 'pct': 100}

            cfg_obj.model_path = model_path
            eval_result = cnn_service.evaluate(cfg_obj, base_dir)
            _save_evaluasi(config_id, eval_result)
            db.session.remove()

            # â”€â”€ Auto prediksi GIS â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
            _progress[config_id] = {'phase': 'predicting', 'pct': 100}

            predict_results = cnn_service.predict_all(cfg_obj, base_dir)
            PrediksiModel.query.filter_by(arsitektur_id=config_id).delete(synchronize_session=False)
            for r in predict_results:
                db.session.add(PrediksiModel(
                    arsitektur_id  = config_id,
                    dokumentasi_id = r['dokumentasi_id'],
                    prediksi       = r['prediksi'],
                    aktual         = r['aktual'],
                    confidence     = r['confidence'],
                ))
            # Semua proses selesai â€” baru set status 'selesai'
            ArsitekturConfig.query.filter_by(id=config_id).update({
                'status':    'selesai',
                'pred_type': 'single',
            })
            db.session.commit()
            db.session.remove()

        except Exception as e:
            traceback.print_exc()  # log full traceback ke terminal Flask
            db.session.rollback()
            try:
                ArsitekturConfig.query.filter_by(id=config_id).update({'status': 'gagal'})
                db.session.commit()
            except Exception:
                db.session.rollback()
            _errors[config_id] = str(e)
            _progress[config_id] = {'phase': 'error', 'error': str(e)}

        finally:
            _progress.pop(config_id, None)
            db.session.remove()


def tandai_training_terputus():
    """Dipanggil saat server start: thread training tidak selamat dari restart, jadi tandai 'gagal'."""
    n = ArsitekturConfig.query.filter_by(status='training').update({'status': 'gagal'}, synchronize_session=False)
    db.session.commit()
    return n


def _remove_fold_models(config_id, base_dir):
    """
    Hapus semua model_{config_id}_fold*.keras (disimpan cnn_service.predict_cv untuk
    ensemble). Wajib dipanggil saat re-train atau hapus config — kalau tidak, model fold
    lama yang sudah tidak sesuai split/data terbaru bisa ikut kepakai sebagai ensemble.
    """
    folder = os.path.join(base_dir, 'app', 'static', 'models')
    k = 0
    while True:
        path = os.path.join(folder, f'model_{config_id}_fold{k}.keras')
        if not os.path.isfile(path):
            break
        try:
            os.remove(path)
        except OSError:
            pass
        k += 1


@arsitektur_bp.route('/')
@login_required
def index():
    configs       = ArsitekturConfig.query.order_by(ArsitekturConfig.created_at.desc()).all()
    total_selesai = sum(1 for c in configs if c.status == 'selesai')
    total_draft   = sum(1 for c in configs if c.status in ('draft', 'gagal', 'training'))

    # Map config_id â†’ HasilEvaluasi (untuk tampil akurasi di tabel)
    evaluasi_map = {
        ev.arsitektur_id: ev
        for ev in HasilEvaluasi.query.all()
    }

    # Config dengan akurasi evaluasi tertinggi
    best_id = None
    if evaluasi_map:
        best_id = max(evaluasi_map, key=lambda cid: evaluasi_map[cid].akurasi)

    return render_template('arsitektur/index.html',
                           configs=configs,
                           total_selesai=total_selesai,
                           total_draft=total_draft,
                           evaluasi_map=evaluasi_map,
                           best_id=best_id)


@arsitektur_bp.route('/new', methods=['GET', 'POST'])
@admin_required
def new():
    split_list = SplitConfig.query.order_by(SplitConfig.created_at.desc()).all()

    if request.method == 'POST':
        nama            = request.form.get('nama', '').strip()
        model_type      = request.form.get('model_type', 'mobilenetv2')
        learning_rate   = float(request.form.get('learning_rate') or 0.0001)
        batch_size      = int(request.form.get('batch_size') or 16)
        epochs          = int(request.form.get('epochs') or 30)
        patience        = int(request.form.get('patience') or 5)
        dropout_rate    = float(request.form.get('dropout_rate') or 0.3)
        optimizer       = request.form.get('optimizer') or 'adam'
        split_config_id = int(request.form.get('split_config_id') or 0)
        fold_val        = int(request.form.get('fold_val') or 0)

        if not nama:
            flash('Nama konfigurasi wajib diisi.', 'warning')
            return redirect(url_for('arsitektur.new'))
        if not split_config_id:
            flash('Pilih split config terlebih dahulu.', 'warning')
            return redirect(url_for('arsitektur.new'))

        split_cfg = db.session.get(SplitConfig, split_config_id)
        if fold_val >= split_cfg.n_splits:
            flash(f'Fold val harus 0â€“{split_cfg.n_splits - 1}.', 'warning')
            return redirect(url_for('arsitektur.new'))

        cfg = ArsitekturConfig(
            nama=nama, model_type=model_type, input_size=224,
            learning_rate=learning_rate, batch_size=batch_size,
            epochs=epochs, patience=patience, dropout_rate=dropout_rate,
            optimizer=optimizer, split_config_id=split_config_id,
            fold_val=fold_val, status='draft',
            pengguna_id=current_user.id,
        )
        db.session.add(cfg)
        db.session.commit()
        flash(f'Konfigurasi "{nama}" berhasil disimpan.', 'success')
        return redirect(url_for('arsitektur.detail', config_id=cfg.id))

    return render_template('arsitektur/form.html', split_list=split_list)


@arsitektur_bp.route('/<int:config_id>')
@login_required
def detail(config_id):
    cfg            = ArsitekturConfig.query.get_or_404(config_id)
    hasil          = HasilTraining.query.filter_by(arsitektur_id=config_id).order_by(HasilTraining.epoch).all()
    best_acc       = max(hasil, key=lambda h: h.val_accuracy) if hasil else None
    best_loss      = min(hasil, key=lambda h: h.val_loss)     if hasil else None
    evaluasi       = HasilEvaluasi.query.filter_by(arsitektur_id=config_id).first()
    total_prediksi = PrediksiModel.query.filter_by(arsitektur_id=config_id).count()
    return render_template('arsitektur/detail.html',
                           cfg=cfg, hasil=hasil,
                           best_acc=best_acc, best_loss=best_loss,
                           evaluasi=evaluasi, total_prediksi=total_prediksi,
                           cv=cv_summary(cfg), label_basi=jumlah_label_basi(cfg.split_config_id),
                           final_running=config_id in _final_progress)


@arsitektur_bp.route('/<int:config_id>/progress')
@login_required
def progress(config_id):
    cfg = ArsitekturConfig.query.get_or_404(config_id)
    if cfg.status not in ('training',):
        resp = {'status': cfg.status}
        if cfg.status == 'gagal' and config_id in _errors:
            resp['error'] = _errors[config_id]
        return jsonify(resp)
    if config_id not in _progress:
        return jsonify({'status': 'training', 'interrupted': True})
    prog = dict(_progress[config_id])
    prog['status'] = 'training'
    return jsonify(prog)


@arsitektur_bp.route('/<int:config_id>/train', methods=['GET', 'POST'])
@admin_required
def train(config_id):
    from flask import current_app

    cfg = ArsitekturConfig.query.get_or_404(config_id)

    if request.method == 'GET':
        return redirect(url_for('arsitektur.detail', config_id=config_id))

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    if jumlah_label_basi(cfg.split_config_id):
        flash('Label berubah sejak split dibuat. Buat split baru sebelum training agar kelas '
              'tiap fold sesuai label terbaru.', 'danger')
        return redirect(url_for('arsitektur.detail', config_id=config_id))

    # Klaim atomik: hanya satu permintaan yang bisa mengubah status menjadi 'training'
    model_lama = [m for m in (cfg.model_path, cfg.final_model_path) if m]
    diklaim = (ArsitekturConfig.query
               .filter(ArsitekturConfig.id == config_id, ArsitekturConfig.status != 'training')
               .update({'status': 'training', 'model_path': None, 'final_model_path': None, 'pred_type': 'none'},
                       synchronize_session=False))
    if not diklaim:
        db.session.rollback()
        flash('Training untuk konfigurasi ini sedang berjalan.', 'warning')
        return redirect(url_for('arsitektur.detail', config_id=config_id))

    HasilTraining.query.filter_by(arsitektur_id=config_id).delete(synchronize_session=False)
    HasilEvaluasi.query.filter_by(arsitektur_id=config_id).delete(synchronize_session=False)
    PrediksiModel.query.filter_by(arsitektur_id=config_id).delete(synchronize_session=False)
    db.session.commit()
    for rel in model_lama:
        try:
            os.remove(os.path.join(base_dir, 'app', 'static', rel))
        except OSError:
            pass
    _remove_fold_models(config_id, base_dir)
    app      = current_app._get_current_object()

    t = threading.Thread(target=_run_training, args=(app, config_id, base_dir), daemon=True)
    t.start()

    return redirect(url_for('arsitektur.detail', config_id=config_id))


@arsitektur_bp.route('/<int:config_id>/re-evaluate', methods=['POST'])
@admin_required
def re_evaluate(config_id):
    """Re-run evaluasi manual jika diperlukan."""
    cfg = ArsitekturConfig.query.get_or_404(config_id)
    _rerun_evaluasi(config_id, cfg)

    return redirect(url_for('arsitektur.detail', config_id=config_id))


@arsitektur_bp.route('/<int:config_id>/evaluate', methods=['GET', 'POST'])
@login_required
def evaluate(config_id):
    """Alias route for evaluasi.html â€” GET shows detail, POST re-runs evaluation."""
    if request.method == 'POST':
        require_admin()
    cfg = ArsitekturConfig.query.get_or_404(config_id)

    if request.method == 'GET':
        evaluasi = HasilEvaluasi.query.filter_by(arsitektur_id=config_id).first()
        return render_template('arsitektur/evaluasi.html', cfg=cfg, evaluasi=evaluasi)

    _rerun_evaluasi(config_id, cfg)

    return redirect(url_for('arsitektur.evaluate', config_id=config_id))


@arsitektur_bp.route('/<int:config_id>/evaluasi-delete', methods=['POST'])
@admin_required
def evaluasi_delete(config_id):
    """Hapus data HasilEvaluasi untuk config tertentu."""
    ArsitekturConfig.query.get_or_404(config_id)
    deleted = HasilEvaluasi.query.filter_by(arsitektur_id=config_id).delete(synchronize_session=False)
    db.session.commit()
    if deleted:
        flash('Data evaluasi dihapus.', 'success')
    else:
        flash('Tidak ada data evaluasi untuk dihapus.', 'info')
    return redirect(url_for('arsitektur.evaluate', config_id=config_id))


@arsitektur_bp.route('/<int:config_id>/gis')
@login_required
def gis(config_id):
    cfg      = ArsitekturConfig.query.get_or_404(config_id)
    evaluasi = HasilEvaluasi.query.filter_by(arsitektur_id=config_id).first()
    total    = PrediksiModel.query.filter_by(arsitektur_id=config_id).count()
    cv_running = config_id in _cv_progress
    split_cfg  = cfg.split_config
    return render_template(
        'arsitektur/gis.html',
        cfg=cfg, evaluasi=evaluasi, total_prediksi=total,
        cv_running=cv_running, split_cfg=split_cfg, cv=cv_summary(cfg),
    )


@arsitektur_bp.route('/<int:config_id>/gis.json')
@login_required
def gis_json(config_id):
    prediksi_list = (
        PrediksiModel.query
        .filter_by(arsitektur_id=config_id)
        .join(PrediksiModel.dokumentasi)
        .join(DokumentasiFoto.lokasi)
        .all()
    )

    LABEL = {0: 'Berat', 1: 'Sedang', 2: 'Ringan'}
    WARNA = {0: '#E53E3E', 1: '#F59E0B', 2: '#10B981'}

    features = []
    for p in prediksi_list:
        lok = p.dokumentasi.lokasi
        if not lok or lok.latitude is None:
            continue
        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [float(lok.longitude), float(lok.latitude)],
            },
            'properties': {
                'id':           p.id,
                'nama_citra':   lok.nama_citra,
                'path_file':    p.dokumentasi.path_file,
                'prediksi':     p.prediksi,
                'label_pred':   LABEL.get(p.prediksi, '?'),
                'aktual':       p.aktual,
                'label_aktual': LABEL.get(p.aktual, '?') if p.aktual is not None else '?',
                'confidence':   p.confidence,
                'warna':        WARNA.get(p.prediksi, '#999'),
                'benar':        p.prediksi == p.aktual,
            }
        })

    return jsonify({'type': 'FeatureCollection', 'features': features})


@arsitektur_bp.route('/<int:config_id>/predict', methods=['POST'])
@admin_required
def predict(config_id):
    from app.services import cnn_service

    cfg = ArsitekturConfig.query.get_or_404(config_id)
    if cfg.status != 'selesai' or not cfg.model_path:
        flash('Model belum selesai dilatih.', 'warning')
        return redirect(url_for('arsitektur.detail', config_id=config_id))

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        results = cnn_service.predict_all(cfg, base_dir)

        PrediksiModel.query.filter_by(arsitektur_id=config_id).delete()
        for r in results:
            db.session.add(PrediksiModel(
                arsitektur_id  = config_id,
                dokumentasi_id = r['dokumentasi_id'],
                prediksi       = r['prediksi'],
                aktual         = r['aktual'],
                confidence     = r['confidence'],
            ))
        cfg.pred_type = 'single'
        db.session.commit()
        flash(f'Prediksi selesai â€” {len(results)} foto diproses.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Prediksi gagal: {e}', 'danger')

    return redirect(url_for('arsitektur.gis', config_id=config_id))


def _run_cv_predict(app, config_id, base_dir):
    """Background thread: K-Fold CV prediction."""
    with app.app_context():
        from app.services import cnn_service

        cfg = db.session.get(ArsitekturConfig, config_id)
        if not cfg:
            return

        split_cfg = db.session.get(SplitConfig, cfg.split_config_id)
        n_splits  = split_cfg.n_splits

        _cfg_snapshot = dict(
            id              = cfg.id,
            split_config_id = cfg.split_config_id,
            input_size      = cfg.input_size,
            model_type      = cfg.model_type,
            dropout_rate    = cfg.dropout_rate,
            optimizer       = cfg.optimizer,
            learning_rate   = cfg.learning_rate,
            batch_size      = cfg.batch_size,
            epochs          = cfg.epochs,
            patience        = cfg.patience,
        )
        db.session.remove()

        _cv_progress[config_id] = {
            'fold': 0, 'total_folds': n_splits,
            'epoch': 0, 'total_epochs': cfg.epochs,
            'pct': 0,
        }

        def on_progress(fold_done, total_folds, epoch, total_epochs):
            fold_pct  = fold_done / total_folds * 100
            epoch_pct = (epoch / total_epochs * 100 / total_folds) if total_epochs else 0
            _cv_progress[config_id] = {
                'fold':         fold_done,
                'total_folds':  total_folds,
                'epoch':        epoch,
                'total_epochs': total_epochs,
                'pct':          round(fold_pct + epoch_pct),
            }

        try:
            cfg_obj = SimpleNamespace()
            for k, v in _cfg_snapshot.items():
                setattr(cfg_obj, k, v)

            results = cnn_service.predict_cv(cfg_obj, base_dir, on_progress=on_progress)

            PrediksiModel.query.filter_by(arsitektur_id=config_id).delete(synchronize_session=False)
            for r in results:
                db.session.add(PrediksiModel(
                    arsitektur_id  = config_id,
                    dokumentasi_id = r['dokumentasi_id'],
                    prediksi       = r['prediksi'],
                    aktual         = r['aktual'],
                    confidence     = r['confidence'],
                ))
            ArsitekturConfig.query.filter_by(id=config_id).update({'pred_type': 'cv'})
            db.session.commit()
            _cv_progress.pop(config_id, None)

        except Exception as e:
            db.session.rollback()
            # JANGAN langsung pop — biarkan cv_progress_route menampilkan error ini
            # ke frontend dulu (sebelumnya error di sini langsung hilang sebelum
            # sempat dibaca, jadi kegagalan selalu senyap).
            _cv_progress[config_id] = {'error': str(e)}
        finally:
            db.session.remove()


@arsitektur_bp.route('/<int:config_id>/predict-cv', methods=['POST'])
@admin_required
def predict_cv_route(config_id):
    from flask import current_app

    cfg = ArsitekturConfig.query.get_or_404(config_id)
    if cfg.status != 'selesai' or not cfg.model_path:
        flash('Model belum selesai dilatih.', 'warning')
        return redirect(url_for('arsitektur.gis', config_id=config_id))

    if config_id in _cv_progress:
        if 'error' in _cv_progress[config_id]:
            _cv_progress.pop(config_id, None)   # percobaan gagal sebelumnya — boleh dicoba ulang
        else:
            flash('Prediksi CV sedang berjalan.', 'warning')
            return redirect(url_for('arsitektur.gis', config_id=config_id))

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app      = current_app._get_current_object()
    t = threading.Thread(target=_run_cv_predict, args=(app, config_id, base_dir), daemon=True)
    t.start()

    return redirect(url_for('arsitektur.gis', config_id=config_id))


@arsitektur_bp.route('/<int:config_id>/cv-progress')
@login_required
def cv_progress_route(config_id):
    if config_id in _cv_progress:
        prog = dict(_cv_progress[config_id])
        prog['running'] = True
        return jsonify(prog)
    return jsonify({'running': False})


def _run_final_training(app, config_id, base_dir):
    """Background thread: latih model final pada semua data lalu simpan path-nya."""
    with app.app_context():
        from app.services import cnn_service

        cfg = db.session.get(ArsitekturConfig, config_id)
        if not cfg:
            _final_progress.pop(config_id, None)
            return
        snapshot = SimpleNamespace(
            id=cfg.id, split_config_id=cfg.split_config_id, input_size=cfg.input_size,
            model_type=cfg.model_type, dropout_rate=cfg.dropout_rate, optimizer=cfg.optimizer,
            learning_rate=cfg.learning_rate, batch_size=cfg.batch_size, epochs=cfg.epochs,
            patience=cfg.patience,
        )
        db.session.remove()
        try:
            model = cnn_service.train_final(snapshot, base_dir)
            path = cnn_service.save_model(model, config_id, base_dir, suffix='_final')
            ArsitekturConfig.query.filter_by(id=config_id).update({'final_model_path': path})
            db.session.commit()
        except Exception as e:
            traceback.print_exc()
            db.session.rollback()
            _errors[('final', config_id)] = str(e)
        finally:
            _final_progress.pop(config_id, None)
            db.session.remove()


@arsitektur_bp.route('/<int:config_id>/train-final', methods=['POST'])
@admin_required
def train_final(config_id):
    from flask import current_app

    cfg = ArsitekturConfig.query.get_or_404(config_id)
    if cfg.status != 'selesai':
        flash('Latih dan evaluasi model dulu sebelum melatih model final.', 'warning')
    elif config_id in _final_progress:
        flash('Model final sedang dilatih.', 'warning')
    elif jumlah_label_basi(cfg.split_config_id):
        flash('Label berubah sejak split dibuat. Buat split baru dan latih ulang terlebih dahulu.', 'danger')
    else:
        _final_progress[config_id] = True
        _errors.pop(('final', config_id), None)
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        app = current_app._get_current_object()
        threading.Thread(target=_run_final_training, args=(app, config_id, base_dir), daemon=True).start()
        flash('Model final dilatih di background (beberapa menit). Muat ulang halaman untuk melihat statusnya.', 'info')
    return redirect(url_for('arsitektur.detail', config_id=config_id))


@arsitektur_bp.route('/<int:config_id>/delete', methods=['POST'])
@admin_required
def delete(config_id):
    cfg  = ArsitekturConfig.query.get_or_404(config_id)
    nama = cfg.nama

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    for rel in (cfg.model_path, cfg.final_model_path):
        if rel:
            model_file = os.path.join(base_dir, 'app', 'static', rel)
            if os.path.isfile(model_file):
                os.remove(model_file)
    _remove_fold_models(config_id, base_dir)

    db.session.delete(cfg)
    db.session.commit()
    flash(f'Konfigurasi "{nama}" dihapus.', 'success')
    return redirect(url_for('arsitektur.index'))

