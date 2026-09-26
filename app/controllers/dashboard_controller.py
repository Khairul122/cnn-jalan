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


# Notebook Colab melatih Fase 1 (backbone beku) 27 epoch, lalu Fase 2 (fine-tuning).
# Batas fase tidak tersimpan di DB, jadi dicatat di sini untuk grafik landing.
FASE_1_EPOCH = 27


def _landing_data():
    """Semua angka landing page dibaca dari DB, tidak ada yang diketik di template."""
    from flask import url_for
    from app.kelas import KELAS
    from app.models.hasil_training import HasilTraining
    from app.services import cnn_service

    cfg = cnn_service.best_model()
    ev = HasilEvaluasi.query.filter_by(arsitektur_id=cfg.id).first() if cfg else None
    total = PrediksiModel.query.count()
    if not (cfg and ev and total):
        return None

    per_class = ev.get_per_class()
    benar = PrediksiModel.query.filter(PrediksiModel.prediksi == PrediksiModel.aktual).count()
    kelas = []
    for i, k in enumerate(KELAS):
        pc = per_class.get(k['key'], {})
        kelas.append({
            'key': k['key'], 'nama': k['nama'], 'warna': k['warna'], 'sdi': k['sdi'],
            'prediksi': PrediksiModel.query.filter_by(prediksi=i).count(),
            'label': LabelKerusakan.query.filter_by(tingkat_kerusakan_id=i + 1).count(),
            'precision': pc.get('precision'), 'recall': pc.get('recall'), 'f1': pc.get('f1-score'),
        })

    # Tiap kelas: contoh foto yang diprediksi benar, dari confidence terendah, tengah, tertinggi.
    contoh = {}
    for i, k in enumerate(KELAS):
        rows = (db.session.query(PrediksiModel.confidence, LokasiKerusakan.nama_citra, DokumentasiFoto.path_file)
                .join(DokumentasiFoto, PrediksiModel.dokumentasi_id == DokumentasiFoto.id)
                .join(LokasiKerusakan, DokumentasiFoto.lokasi_id == LokasiKerusakan.id)
                .filter(PrediksiModel.prediksi == i, PrediksiModel.aktual == i)
                .order_by(PrediksiModel.confidence).all())
        pilih = [rows[0], rows[len(rows) // 2], rows[-1]] if len(rows) >= 3 else rows
        contoh[k['key']] = [{'citra': r.nama_citra, 'confidence': round(float(r.confidence) * 100, 1),
                             'src': url_for('static', filename=r.path_file)} for r in pilih]

    riwayat = [{'e': h.epoch, 'acc': h.accuracy, 'val': h.val_accuracy, 'loss': h.loss, 'vloss': h.val_loss}
               for h in HasilTraining.query.filter_by(arsitektur_id=cfg.id).order_by(HasilTraining.epoch)]

    return {
        'total': total,
        'benar_semua': benar,
        'akurasi_semua': round(benar / total * 100, 1),
        'akurasi_val': round(ev.akurasi, 2),
        'n_val': ev.total_data_val,
        'benar_val': sum(ev.get_cm()[i][i] for i in range(len(KELAS))),
        'macro_f1': round(ev.macro_f1, 1),
        'cm': ev.get_cm(),
        'kelas': kelas,
        'contoh': contoh,
        'riwayat': riwayat,
        'fase1': FASE_1_EPOCH,
        'model': {'nama': cfg.nama, 'lr': cfg.learning_rate, 'batch': cfg.batch_size,
                  'patience': cfg.patience, 'input': cfg.input_size},
    }


@dashboard_bp.route('/')
def root():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))
    from datetime import date
    return render_template('landing/index.html', data=_landing_data(), tahun=date.today().year)


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
