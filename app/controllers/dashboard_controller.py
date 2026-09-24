from flask import Blueprint, render_template, redirect, url_for, jsonify
from flask_login import login_required, current_user
from app import db
from app.kelas import KEYS
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.pengguna import Pengguna
from app.models.label_kerusakan import LabelKerusakan
from app.models.prediksi_model import PrediksiModel
from app.models.hasil_evaluasi import HasilEvaluasi
from app.models.dokumentasi_foto import DokumentasiFoto

dashboard_bp = Blueprint('dashboard', __name__)


def _headline_accuracy():
    """
    Angka akurasi CNN untuk ditampilkan sebagai headline (dashboard & landing page).
    Utamakan cv_summary().macro_f1 tertinggi (metrik resmi, rata-rata K-Fold) — SAMA
    seperti cnn_service.best_model() dan arsitektur_controller.index() — fallback ke
    HasilEvaluasi (1 fold, ditandai 'sumber': '1fold') hanya kalau belum ada config yang
    di-CV sama sekali. Cegah headline publik diam-diam pakai metrik 1-fold tanpa label.
    """
    from app.services import cnn_service
    from app.services.metrics_service import cv_summary

    best_cfg = cnn_service.best_model()
    if not best_cfg:
        return None

    cv = cv_summary(best_cfg) if best_cfg.pred_type == 'cv' else None
    if cv:
        return {
            'akurasi'       : cv['akurasi'],
            'recall'        : cv['recall'],
            'model_nama'    : best_cfg.nama,
            'sumber'        : 'cv',
        }

    ev = HasilEvaluasi.query.filter_by(arsitektur_id=best_cfg.id).first()
    if not ev:
        return None
    return {
        'akurasi'       : round(ev.akurasi or 0, 1),
        'recall'        : {k: round(v['recall'], 1) for k, v in ev.get_per_class().items()},
        'model_nama'    : best_cfg.nama,
        'sumber'        : '1fold',
    }


@dashboard_bp.route('/')
def root():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    headline = _headline_accuracy()

    total_pred = PrediksiModel.query.count()
    pred_ct    = {k: PrediksiModel.query.filter_by(prediksi=i).count() for i, k in enumerate(KEYS)}

    ctx = {
        'total_pred'    : total_pred,
        'pred_ct'       : pred_ct,
        'akurasi'       : headline['akurasi'] if headline else None,
        'recall'        : headline['recall'] if headline else {},
        'model_nama'    : headline['model_nama'] if headline else None,
        'akurasi_sumber': headline['sumber'] if headline else None,
    }
    return render_template('landing/index.html', **ctx)


@dashboard_bp.route('/api/landing/gis')
def landing_gis():
    """Public GeoJSON for landing page map — no image paths or sensitive data."""
    from app.models.prediksi_model import PrediksiModel
    from app.models.dokumentasi_foto import DokumentasiFoto

    from app.kelas import LABEL, WARNA

    rows = (db.session.query(
                PrediksiModel.prediksi,
                PrediksiModel.aktual,
                PrediksiModel.confidence,
                LokasiKerusakan.latitude,
                LokasiKerusakan.longitude,
                LokasiKerusakan.nama_citra,
                DokumentasiFoto.path_file,
            )
            .join(DokumentasiFoto, PrediksiModel.dokumentasi_id == DokumentasiFoto.id)
            .join(LokasiKerusakan, DokumentasiFoto.lokasi_id == LokasiKerusakan.id)
            .filter(LokasiKerusakan.latitude.isnot(None))
            .all())

    features = [{
        'type': 'Feature',
        'geometry': {'type': 'Point', 'coordinates': [float(r.longitude), float(r.latitude)]},
        'properties': {
            'nama_citra': r.nama_citra,
            'prediksi': LABEL.get(r.prediksi, '?'),
            'aktual'  : LABEL.get(r.aktual, '?') if r.aktual is not None else '?',
            'confidence': float(r.confidence) if r.confidence is not None else 0.0,
            'warna'   : WARNA.get(r.prediksi, '#999'),
            'benar'   : r.aktual is not None and r.prediksi == r.aktual,
            'path_file': r.path_file,
        },
    } for r in rows]

    return jsonify({'type': 'FeatureCollection', 'features': features})


@dashboard_bp.route('/dashboard')
@login_required
def index():
    total_lokasi   = LokasiKerusakan.query.count()
    total_pengguna = Pengguna.query.count()
    total_foto     = DokumentasiFoto.query.count()
    total_label    = LabelKerusakan.query.count()
    total_prediksi = PrediksiModel.query.count()

    label_ct = {k: LabelKerusakan.query.filter_by(tingkat_kerusakan_id=i + 1).count() for i, k in enumerate(KEYS)}

    headline     = _headline_accuracy()
    akurasi_cnn  = headline['akurasi'] if headline else None
    model_nama   = headline['model_nama'] if headline else None
    model_status = 'selesai' if headline else 'mock'

    stats = {
        'total_lokasi'   : total_lokasi,
        'total_pengguna' : total_pengguna,
        'total_foto'     : total_foto,
        'total_label'    : total_label,
        'total_prediksi' : total_prediksi,
        'label_ct'       : label_ct,
        'akurasi_cnn'    : akurasi_cnn,
        'model_nama'     : model_nama,
        'model_status'   : model_status,
        'akurasi_sumber' : headline['sumber'] if headline else None,
    }
    return render_template('dashboard/index.html', stats=stats)
