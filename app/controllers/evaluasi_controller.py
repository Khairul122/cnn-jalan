from flask import Blueprint, render_template, redirect, url_for, flash, request
from flask_login import login_required
from app import db
from app.models.evaluasi_model import EvaluasiModel

evaluasi_bp = Blueprint('evaluasi', __name__, url_prefix='/evaluasi')


@evaluasi_bp.route('/')
@login_required
def index():
    evaluasi_list = EvaluasiModel.query.order_by(EvaluasiModel.created_at.desc()).all()
    return render_template('evaluasi/index.html', evaluasi_list=evaluasi_list)


@evaluasi_bp.route('/create', methods=['POST'])
@login_required
def create():
    try:
        ev = EvaluasiModel(
            nama_model         = request.form.get('nama_model', '').strip(),
            versi              = request.form.get('versi', '').strip(),
            total_data_uji     = int(request.form.get('total_data_uji', 0)),
            akurasi            = float(request.form.get('akurasi', 0)),
            presisi            = float(request.form.get('presisi', 0)),
            recall             = float(request.form.get('recall', 0)),
            f1_score           = float(request.form.get('f1_score', 0)),
            cross_entropy_loss = float(request.form.get('cross_entropy_loss', 0)),
            tp                 = int(request.form.get('tp', 0)),
            fp                 = int(request.form.get('fp', 0)),
            tn                 = int(request.form.get('tn', 0)),
            fn                 = int(request.form.get('fn', 0)),
            catatan            = request.form.get('catatan') or None,
        )
        db.session.add(ev)
        db.session.commit()
        flash('Data evaluasi berhasil disimpan.', 'success')
    except (ValueError, TypeError) as e:
        flash(f'Input tidak valid: {e}', 'danger')

    return redirect(url_for('evaluasi.index'))


@evaluasi_bp.route('/<int:ev_id>/delete', methods=['POST'])
@login_required
def delete(ev_id):
    ev = EvaluasiModel.query.get_or_404(ev_id)
    db.session.delete(ev)
    db.session.commit()
    flash('Data evaluasi dihapus.', 'info')
    return redirect(url_for('evaluasi.index'))
