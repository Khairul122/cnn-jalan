import os
import traceback
import threading
from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app import db
from app.models.arsitektur_config import ArsitekturConfig
from app.models.hasil_training import HasilTraining
from app.models.hasil_evaluasi import HasilEvaluasi
from app.models.prediksi_model import PrediksiModel
from app.models.split_config import SplitConfig
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.lokasi_kerusakan import LokasiKerusakan

arsitektur_bp = Blueprint('arsitektur', __name__, url_prefix='/arsitektur')

# Progress store: {config_id: {phase, current, total, pct, ...}}
_progress    = {}
# CV predict progress: {config_id: {fold, total_folds, epoch, total_epochs, pct}}
_cv_progress = {}
# Error store: {config_id: error_message} — persists after training ends for UI display
_errors      = {}


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


def _run_training(app, config_id, base_dir):
    """Background thread: training → auto evaluasi → DB write."""
    with app.app_context():
        from app.services import cnn_service

        cfg = ArsitekturConfig.query.get(config_id)
        if not cfg:
            return

        _progress[config_id] = {'phase': 'training', 'current': 0, 'total': cfg.epochs, 'pct': 0}

        _cfg_snapshot = {
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
            class _Cfg:
                pass
            cfg_obj = _Cfg()
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

            # ── Auto evaluasi ──────────────────────────────────────
            _progress[config_id] = {'phase': 'evaluating', 'pct': 100}

            cfg_obj.model_path = model_path
            eval_result = cnn_service.evaluate(cfg_obj, base_dir)
            _save_evaluasi(config_id, eval_result)
            db.session.remove()

            # ── Auto prediksi GIS ───────────────────────────────────
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
            # Semua proses selesai — baru set status 'selesai'
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


@arsitektur_bp.route('/')
@login_required
def index():
    configs       = ArsitekturConfig.query.order_by(ArsitekturConfig.created_at.desc()).all()
    total_selesai = sum(1 for c in configs if c.status == 'selesai')
    total_draft   = sum(1 for c in configs if c.status in ('draft', 'gagal', 'training'))

    # Map config_id → HasilEvaluasi (untuk tampil akurasi di tabel)
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
@login_required
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

        split_cfg = SplitConfig.query.get(split_config_id)
        if fold_val >= split_cfg.n_splits:
            flash(f'Fold val harus 0–{split_cfg.n_splits - 1}.', 'warning')
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
    best           = max(hasil, key=lambda h: h.val_accuracy) if hasil else None
    evaluasi       = HasilEvaluasi.query.filter_by(arsitektur_id=config_id).first()
    total_prediksi = PrediksiModel.query.filter_by(arsitektur_id=config_id).count()
    return render_template('arsitektur/detail.html',
                           cfg=cfg, hasil=hasil, best=best,
                           evaluasi=evaluasi, total_prediksi=total_prediksi)


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


@arsitektur_bp.route('/<int:config_id>/train', methods=['POST'])
@login_required
def train(config_id):
    from flask import current_app

    cfg = ArsitekturConfig.query.get_or_404(config_id)

    HasilTraining.query.filter_by(arsitektur_id=config_id).delete(synchronize_session=False)
    HasilEvaluasi.query.filter_by(arsitektur_id=config_id).delete(synchronize_session=False)
    PrediksiModel.query.filter_by(arsitektur_id=config_id).delete(synchronize_session=False)
    ArsitekturConfig.query.filter_by(id=config_id).update({'status': 'training', 'model_path': None, 'pred_type': 'none'})
    db.session.commit()

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    app      = current_app._get_current_object()

    t = threading.Thread(target=_run_training, args=(app, config_id, base_dir), daemon=True)
    t.start()

    return redirect(url_for('arsitektur.detail', config_id=config_id))


@arsitektur_bp.route('/<int:config_id>/re-evaluate', methods=['POST'])
@login_required
def re_evaluate(config_id):
    """Re-run evaluasi manual jika diperlukan."""
    from app.services import cnn_service

    cfg = ArsitekturConfig.query.get_or_404(config_id)
    if cfg.status != 'selesai' or not cfg.model_path:
        flash('Model belum selesai dilatih.', 'warning')
        return redirect(url_for('arsitektur.detail', config_id=config_id))

    base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        result = cnn_service.evaluate(cfg, base_dir)
        _save_evaluasi(config_id, result)
        flash('Evaluasi berhasil diperbarui.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Evaluasi gagal: {e}', 'danger')

    return redirect(url_for('arsitektur.detail', config_id=config_id))


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
        cv_running=cv_running, split_cfg=split_cfg,
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
@login_required
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
        flash(f'Prediksi selesai — {len(results)} foto diproses.', 'success')
    except Exception as e:
        db.session.rollback()
        flash(f'Prediksi gagal: {e}', 'danger')

    return redirect(url_for('arsitektur.gis', config_id=config_id))


def _run_cv_predict(app, config_id, base_dir):
    """Background thread: K-Fold CV prediction."""
    with app.app_context():
        from app.services import cnn_service

        cfg = ArsitekturConfig.query.get(config_id)
        if not cfg:
            return

        split_cfg = SplitConfig.query.get(cfg.split_config_id)
        n_splits  = split_cfg.n_splits

        _cfg_snapshot = dict(
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
            class _Cfg:
                pass
            cfg_obj = _Cfg()
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

        except Exception as e:
            db.session.rollback()
            _cv_progress[config_id] = {'error': str(e)}
        finally:
            _cv_progress.pop(config_id, None)
            db.session.remove()


@arsitektur_bp.route('/<int:config_id>/predict-cv', methods=['POST'])
@login_required
def predict_cv_route(config_id):
    from flask import current_app

    cfg = ArsitekturConfig.query.get_or_404(config_id)
    if cfg.status != 'selesai' or not cfg.model_path:
        flash('Model belum selesai dilatih.', 'warning')
        return redirect(url_for('arsitektur.gis', config_id=config_id))

    if config_id in _cv_progress:
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


@arsitektur_bp.route('/<int:config_id>/delete', methods=['POST'])
@login_required
def delete(config_id):
    cfg  = ArsitekturConfig.query.get_or_404(config_id)
    nama = cfg.nama

    if cfg.model_path:
        base_dir   = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        model_file = os.path.join(base_dir, 'app', 'static', cfg.model_path)
        if os.path.isfile(model_file):
            os.remove(model_file)

    db.session.delete(cfg)
    db.session.commit()
    flash(f'Konfigurasi "{nama}" dihapus.', 'success')
    return redirect(url_for('arsitektur.index'))
