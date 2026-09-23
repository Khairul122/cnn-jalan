from flask import Blueprint, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from app.auth_utils import admin_required
from app import db
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.label_kerusakan import LabelKerusakan
from app.models.tingkat_kerusakan import TingkatKerusakan

label_bp = Blueprint('label', __name__, url_prefix='/label')


@label_bp.route('/')
@login_required
def index():
    # Ambil semua lokasi, join ke label (left join via Python)
    lokasi_list = LokasiKerusakan.query.order_by(LokasiKerusakan.id).all()
    return render_template('label/index.html', lokasi_list=lokasi_list)


@label_bp.route('/<int:lokasi_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit(lokasi_id):
    lokasi = LokasiKerusakan.query.get_or_404(lokasi_id)
    label  = LabelKerusakan.query.filter_by(lokasi_id=lokasi_id).first()
    tingkat_list = TingkatKerusakan.query.order_by(TingkatKerusakan.skor_prioritas.desc()).all()

    if request.method == 'POST':
        try:
            persen_retak      = float(request.form.get('persen_retak', 0))
            jenis_retak       = request.form.get('jenis_retak', 'halus')
            jumlah_lubang     = int(request.form.get('jumlah_lubang', 0))
            kedalaman_rutting = float(request.form.get('kedalaman_rutting', 0))
            catatan           = request.form.get('catatan', '').strip() or None

            sdi = LabelKerusakan.hitung_sdi(persen_retak, jenis_retak, jumlah_lubang, kedalaman_rutting)
            tingkat_id = LabelKerusakan.tingkat_dari_sdi(sdi)

            if label:
                label.persen_retak      = persen_retak
                label.jenis_retak       = jenis_retak
                label.jumlah_lubang     = jumlah_lubang
                label.kedalaman_rutting = kedalaman_rutting
                label.sdi_score         = sdi
                label.tingkat_kerusakan_id = tingkat_id
                label.catatan           = catatan
                label.pengguna_id       = current_user.id
            else:
                label = LabelKerusakan(
                    lokasi_id=lokasi_id,
                    persen_retak=persen_retak,
                    jenis_retak=jenis_retak,
                    jumlah_lubang=jumlah_lubang,
                    kedalaman_rutting=kedalaman_rutting,
                    sdi_score=sdi,
                    tingkat_kerusakan_id=tingkat_id,
                    catatan=catatan,
                    pengguna_id=current_user.id,
                )
                db.session.add(label)

            db.session.commit()
            flash(f'Label berhasil disimpan — SDI: {sdi}', 'success')
            return redirect(url_for('label.index'))

        except (ValueError, TypeError) as e:
            flash(f'Input tidak valid: {e}', 'danger')

    return render_template('label/edit.html', lokasi=lokasi, label=label,
                           tingkat_list=tingkat_list)


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
    flash(f'Semua label SDI dihapus ({jumlah} record).', 'info')
    return redirect(url_for('label.index'))


@label_bp.route('/auto', methods=['POST'])
@admin_required
def auto_label():
    """Labeling otomatis semua lokasi: estimasi SDI dari dimensi (P × L) → tingkat."""
    mode = request.form.get('mode', 'pending')   # 'pending' | 'semua'

    lokasi_list = LokasiKerusakan.query.all()
    berhasil = 0
    dilewati = 0

    for lok in lokasi_list:
        label = LabelKerusakan.query.filter_by(lokasi_id=lok.id).first()
        if label and mode == 'pending':
            dilewati += 1
            continue

        params, sdi, area = LabelKerusakan.estimasi_dari_dimensi(lok.panjang, lok.lebar)

        if label is None:
            label = LabelKerusakan(lokasi_id=lok.id)
            db.session.add(label)
        label.persen_retak         = params['persen_retak']
        label.jenis_retak          = params['jenis_retak']
        label.jumlah_lubang        = params['jumlah_lubang']
        label.kedalaman_rutting    = params['kedalaman_rutting']
        label.sdi_score            = sdi
        label.tingkat_kerusakan_id = LabelKerusakan.tingkat_dari_sdi(sdi)
        label.pengguna_id          = current_user.id
        label.catatan              = f'Auto-label (area {round(area, 2)} m²)'
        berhasil += 1

    db.session.commit()

    kata = 'dilabel ulang' if mode == 'semua' else 'dilabel'
    flash(f'Auto-label selesai — {berhasil} lokasi {kata}, {dilewati} dilewati.', 'success')
    return redirect(url_for('label.index'))


@label_bp.route('/hitung-sdi', methods=['POST'])
@login_required
def hitung_sdi():
    """Endpoint AJAX untuk kalkulasi SDI real-time."""
    data = request.get_json()
    sdi  = LabelKerusakan.hitung_sdi(
        data.get('persen_retak', 0),
        data.get('jenis_retak', 'halus'),
        data.get('jumlah_lubang', 0),
        data.get('kedalaman_rutting', 0),
    )
    tingkat_id = LabelKerusakan.tingkat_dari_sdi(sdi)
    tingkat    = db.session.get(TingkatKerusakan, tingkat_id)
    return jsonify({
        'sdi': sdi,
        'tingkat_id': tingkat_id,
        'nama_tingkat': tingkat.nama_tingkat,
        'warna': tingkat.warna_peta,
    })
