from flask import Blueprint, render_template, jsonify, request
from flask_login import login_required
from app.models.peta_kerusakan import PetaKerusakan
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.arsitektur_config import ArsitekturConfig
from app.models.prediksi_model import PrediksiModel
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.hasil_evaluasi import HasilEvaluasi

peta_bp = Blueprint('peta', __name__, url_prefix='/peta')


@peta_bp.route('/')
@login_required
def index():
    # Configs that have predictions stored
    prediksi_configs = (
        ArsitekturConfig.query
        .join(ArsitekturConfig.prediksi_list)
        .filter(ArsitekturConfig.status == 'selesai')
        .distinct()
        .all()
    )

    evaluasi_map = {
        ev.arsitektur_id: ev
        for ev in HasilEvaluasi.query.all()
    }

    best_id = None
    if evaluasi_map:
        best_id = max(evaluasi_map, key=lambda cid: evaluasi_map[cid].akurasi)

    return render_template(
        'peta/index.html',
        prediksi_configs=prediksi_configs,
        evaluasi_map=evaluasi_map,
        best_id=best_id,
    )


@peta_bp.route('/geojson')
@login_required
def geojson():
    status = request.args.get('status')

    query = PetaKerusakan.query.join(PetaKerusakan.lokasi)

    if status:
        query = query.filter(PetaKerusakan.status_pemetaan == status)

    peta_list = query.all()

    features = []
    for p in peta_list:
        lok = p.lokasi
        hk  = p.hasil_klasifikasi
        warna = '#999999'
        jenis = '-'
        tingkat = '-'

        if hk:
            if hk.tingkat_kerusakan:
                warna   = hk.tingkat_kerusakan.warna_peta
                tingkat = hk.tingkat_kerusakan.nama_tingkat
            if hk.jenis_kerusakan:
                jenis = hk.jenis_kerusakan.nama_jenis

        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [float(lok.longitude), float(lok.latitude)]
            },
            'properties': {
                'id'         : p.id,
                'nama_citra' : lok.nama_citra,
                'jenis'      : jenis,
                'tingkat'    : tingkat,
                'warna'      : warna,
                'status'     : p.status_pemetaan,
                'prioritas'  : p.prioritas_perbaikan,
            }
        })

    return jsonify({'type': 'FeatureCollection', 'features': features})


@peta_bp.route('/prediksi-geojson')
@login_required
def prediksi_geojson():
    arsitektur_id = request.args.get('arsitektur_id', type=int)
    filter_val    = request.args.get('filter', 'all')

    if not arsitektur_id:
        return jsonify({'type': 'FeatureCollection', 'features': []})

    LABEL = {0: 'Berat', 1: 'Sedang', 2: 'Ringan'}
    WARNA = {0: '#E53E3E', 1: '#F59E0B', 2: '#10B981'}

    prediksi_list = (
        PrediksiModel.query
        .filter_by(arsitektur_id=arsitektur_id)
        .join(PrediksiModel.dokumentasi)
        .join(DokumentasiFoto.lokasi)
        .all()
    )

    features = []
    for p in prediksi_list:
        lok = p.dokumentasi.lokasi
        if not lok or lok.latitude is None:
            continue

        benar = p.prediksi == p.aktual

        if filter_val == 'salah' and benar:
            continue
        if filter_val not in ('all', 'salah') and p.prediksi != int(filter_val):
            continue

        features.append({
            'type': 'Feature',
            'geometry': {
                'type': 'Point',
                'coordinates': [float(lok.longitude), float(lok.latitude)],
            },
            'properties': {
                'nama_citra':   lok.nama_citra,
                'path_file':    p.dokumentasi.path_file,
                'prediksi':     p.prediksi,
                'label_pred':   LABEL.get(p.prediksi, '?'),
                'aktual':       p.aktual,
                'label_aktual': LABEL.get(p.aktual, '?') if p.aktual is not None else '?',
                'confidence':   p.confidence,
                'warna':        WARNA.get(p.prediksi, '#999'),
                'benar':        benar,
            }
        })

    return jsonify({'type': 'FeatureCollection', 'features': features})
