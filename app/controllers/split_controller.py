import io
import csv
from flask import Blueprint, render_template, redirect, url_for, request, flash, Response
from flask_login import login_required, current_user
from app import db
from app.models.split_config import SplitConfig
from app.models.split_item import SplitItem
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.label_kerusakan import LabelKerusakan
from app.models.arsitektur_config import ArsitekturConfig
from app.models.tingkat_kerusakan import TingkatKerusakan
from app.models.hasil_preprocessing import HasilPreprocessing
from app.services.split_service import SplitService

split_bp = Blueprint('split', __name__, url_prefix='/split')


def _prep_coverage(doc_ids):
    """Return set of dokumentasi_id yang sudah punya hasil step 'denoise'."""
    if not doc_ids:
        return set()
    rows = (
        HasilPreprocessing.query
        .filter(
            HasilPreprocessing.dokumentasi_id.in_(list(doc_ids)),
            HasilPreprocessing.step_name == 'denoise',
            HasilPreprocessing.status == 'selesai',
            HasilPreprocessing.path_output != '',
        )
        .with_entities(HasilPreprocessing.dokumentasi_id)
        .distinct()
        .all()
    )
    return {r.dokumentasi_id for r in rows}


def _get_labeled_items():
    """
    Ambil semua DokumentasiFoto yang lokasinya sudah punya LabelKerusakan.
    Return list of dict {dokumentasi_id, label_id, nama_file, latitude, longitude}.
    """
    rows = (
        db.session.query(
            DokumentasiFoto.id,
            DokumentasiFoto.nama_file,
            LokasiKerusakan.latitude,
            LokasiKerusakan.longitude,
            LabelKerusakan.tingkat_kerusakan_id,
        )
        .join(LokasiKerusakan, DokumentasiFoto.lokasi_id == LokasiKerusakan.id)
        .join(LabelKerusakan, LabelKerusakan.lokasi_id == LokasiKerusakan.id)
        .order_by(DokumentasiFoto.id)
        .all()
    )
    return [
        {
            'dokumentasi_id': r.id,
            'nama_file':      r.nama_file,
            'latitude':       float(r.latitude),
            'longitude':      float(r.longitude),
            'label_id':       r.tingkat_kerusakan_id,
        }
        for r in rows
    ]


@split_bp.route('/')
@login_required
def index():
    configs        = SplitConfig.query.order_by(SplitConfig.created_at.desc()).all()
    items          = _get_labeled_items()
    total_berlabel = len(items)
    doc_ids        = {i['dokumentasi_id'] for i in items}
    total_prep     = len(_prep_coverage(doc_ids))
    tingkat_list   = TingkatKerusakan.query.order_by(TingkatKerusakan.id).all()
    return render_template(
        'split/index.html',
        configs=configs,
        total_berlabel=total_berlabel,
        total_prep=total_prep,
        tingkat_list=tingkat_list,
    )


@split_bp.route('/new', methods=['GET', 'POST'])
@login_required
def new():
    tingkat_list = TingkatKerusakan.query.order_by(TingkatKerusakan.id).all()
    items        = _get_labeled_items()

    from collections import Counter
    kelas_count  = Counter(i['label_id'] for i in items)
    doc_ids      = {i['dokumentasi_id'] for i in items}
    total_prep   = len(_prep_coverage(doc_ids))

    if request.method == 'POST':
        nama         = request.form.get('nama', '').strip()
        random_state = int(request.form.get('random_state', 42))

        if not nama:
            flash('Nama split wajib diisi.', 'warning')
            return redirect(url_for('split.new'))

        if not items:
            flash('Tidak ada data berlabel. Tambah label SDI terlebih dahulu.', 'warning')
            return redirect(url_for('split.new'))

        result = SplitService.run(0.2, random_state, items)

        config = SplitConfig(
            nama=nama,
            split_type='holdout',
            n_splits=2,
            random_state=random_state,
            label_sumber='tingkat',
            total_data=len(result),
            pengguna_id=current_user.id,
        )
        db.session.add(config)
        db.session.flush()

        db.session.bulk_insert_mappings(SplitItem, [
            {
                'config_id':            config.id,
                'dokumentasi_id':       r['dokumentasi_id'],
                'tingkat_kerusakan_id': r['label_id'],
                'fold_index':           r['fold_index'],
            }
            for r in result
        ])
        db.session.commit()

        flash(f'Split "{nama}" berhasil dibuat dengan {len(result)} data.', 'success')
        return redirect(url_for('split.detail', config_id=config.id))

    return render_template(
        'split/form.html',
        tingkat_list=tingkat_list,
        total_berlabel=len(items),
        total_prep=total_prep,
        kelas_count=kelas_count,
    )


@split_bp.route('/<int:config_id>')
@login_required
def detail(config_id):
    config       = SplitConfig.query.get_or_404(config_id)
    tingkat_list = TingkatKerusakan.query.order_by(TingkatKerusakan.id).all()
    label_map    = {t.id: t.nama_tingkat for t in tingkat_list}

    items = (
        db.session.query(
            SplitItem.dokumentasi_id,
            SplitItem.fold_index,
            SplitItem.tingkat_kerusakan_id,
            DokumentasiFoto.nama_file,
            LokasiKerusakan.latitude,
            LokasiKerusakan.longitude,
        )
        .join(DokumentasiFoto, SplitItem.dokumentasi_id == DokumentasiFoto.id)
        .join(LokasiKerusakan, DokumentasiFoto.lokasi_id == LokasiKerusakan.id)
        .filter(SplitItem.config_id == config_id)
        .order_by(SplitItem.fold_index, SplitItem.tingkat_kerusakan_id)
        .all()
    )

    item_dicts = [
        {
            'fold_index': r.fold_index,
            'label_id':   r.tingkat_kerusakan_id,
            'nama_file':  r.nama_file,
            'latitude':   float(r.latitude),
            'longitude':  float(r.longitude),
        }
        for r in items
    ]

    dist = SplitService.distribusi(item_dicts, label_map)

    # Coverage preprocessing per fold
    all_doc_ids   = {r.dokumentasi_id for r in items}
    train_doc_ids = {r.dokumentasi_id for r in items if r.fold_index == 0}
    test_doc_ids  = {r.dokumentasi_id for r in items if r.fold_index == 1}
    prep_ids      = _prep_coverage(all_doc_ids)
    prep_coverage = {
        'train': len(prep_ids & train_doc_ids),
        'test':  len(prep_ids & test_doc_ids),
        'total': len(prep_ids),
        'train_total': len(train_doc_ids),
        'test_total':  len(test_doc_ids),
    }

    return render_template(
        'split/detail.html',
        config=config,
        tingkat_list=tingkat_list,
        label_map=label_map,
        dist=dist,
        prep_coverage=prep_coverage,
    )


@split_bp.route('/<int:config_id>/delete', methods=['POST'])
@login_required
def delete(config_id):
    config = SplitConfig.query.get_or_404(config_id)
    nama   = config.nama

    arsitektur_count = ArsitekturConfig.query.filter_by(split_config_id=config_id).count()
    if arsitektur_count > 0:
        flash(
            f'Split "{nama}" tidak bisa dihapus karena digunakan oleh '
            f'{arsitektur_count} konfigurasi arsitektur CNN. Hapus arsitektur tersebut terlebih dahulu.',
            'danger',
        )
        return redirect(url_for('split.index'))

    db.session.delete(config)
    db.session.commit()
    flash(f'Split "{nama}" telah dihapus.', 'success')
    return redirect(url_for('split.index'))


@split_bp.route('/<int:config_id>/reset', methods=['POST'])
@login_required
def reset_items(config_id):
    config = SplitConfig.query.get_or_404(config_id)

    arsitektur_count = ArsitekturConfig.query.filter_by(split_config_id=config_id).count()
    if arsitektur_count > 0:
        flash(
            f'Split tidak bisa direset karena digunakan oleh {arsitektur_count} '
            f'konfigurasi arsitektur CNN. Hapus arsitektur tersebut terlebih dahulu.',
            'danger',
        )
        return redirect(url_for('split.detail', config_id=config_id))

    jumlah = SplitItem.query.filter_by(config_id=config_id).delete()
    config.total_data = 0
    db.session.commit()
    flash(f'Split items direset — {jumlah} item dihapus. Konfigurasi split tetap ada.', 'info')
    return redirect(url_for('split.detail', config_id=config_id))


@split_bp.route('/<int:config_id>/export')
@login_required
def export(config_id):
    config = SplitConfig.query.get_or_404(config_id)
    tingkat_map = {t.id: t.nama_tingkat for t in TingkatKerusakan.query.all()}

    rows = (
        db.session.query(
            SplitItem.fold_index,
            SplitItem.tingkat_kerusakan_id,
            DokumentasiFoto.nama_file,
            LokasiKerusakan.latitude,
            LokasiKerusakan.longitude,
        )
        .join(DokumentasiFoto, SplitItem.dokumentasi_id == DokumentasiFoto.id)
        .join(LokasiKerusakan, DokumentasiFoto.lokasi_id == LokasiKerusakan.id)
        .filter(SplitItem.config_id == config_id)
        .order_by(SplitItem.fold_index, SplitItem.tingkat_kerusakan_id)
        .all()
    )

    holdout_label = {0: 'Train', 1: 'Test'}
    is_holdout = (config.split_type == 'holdout')

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['nama_file', 'split', 'tingkat', 'latitude', 'longitude'])
    for r in rows:
        split_label = holdout_label.get(r.fold_index, str(r.fold_index)) if is_holdout else f'Fold {r.fold_index + 1}'
        writer.writerow([
            r.nama_file,
            split_label,
            tingkat_map.get(r.tingkat_kerusakan_id, ''),
            r.latitude,
            r.longitude,
        ])

    filename = f"split_{config.nama.replace(' ', '_')}_K{config.n_splits}.csv"
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
