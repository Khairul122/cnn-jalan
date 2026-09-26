import io
import os
import csv
from flask import Blueprint, render_template, redirect, url_for, request, flash, Response, jsonify
from flask_login import login_required, current_user
from sqlalchemy import func
from werkzeug.utils import secure_filename
from app.auth_utils import admin_required
from app import db
from app.models.split_config import SplitConfig
from app.models.split_item import SplitItem
from app.models.dokumentasi_foto import DokumentasiFoto
from app.models.lokasi_kerusakan import LokasiKerusakan
from app.models.label_kerusakan import LabelKerusakan
from app.models.arsitektur_config import ArsitekturConfig
from app.models.tingkat_kerusakan import TingkatKerusakan
from app.models.hasil_preprocessing import HasilPreprocessing
from app.services import cnn_service
from app.services.cnn_service import TRAIN_EXPAND_STEPS
from app.services.split_service import SplitService, jumlah_label_basi
from collections import Counter
from app.services.dedup_service import find_duplicate_groups, find_spatial_groups, merge_group_maps
from app.progress_store import ProgressStore

split_bp = Blueprint('split', __name__, url_prefix='/split')

# Progres pembuatan split, dikunci per user (hanya admin yang menjalankan, satu run sekaligus).
_progress = ProgressStore()


def _lapor(user_id, pct, step):
    _progress.set(user_id, {'status': 'running', 'pct': pct, 'step': step})

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MAKS_ULANGAN = 5   # jumlah split berseed berurutan yang boleh dibuat sekaligus (repeated K-Fold)


def _prep_coverage(doc_ids):
    """
    Return set of dokumentasi_id yang SEMUA tahap non-acaknya (TRAIN_EXPAND_STEPS = resize,
    crop, normalisasi, denoise) sudah selesai — ini yang dipakai cnn_service.load_dataset
    untuk ekspansi train & val (bukan cuma tahap 'denoise' lagi).
    """
    if not doc_ids:
        return set()
    rows = (
        db.session.query(HasilPreprocessing.dokumentasi_id)
        .filter(
            HasilPreprocessing.dokumentasi_id.in_(list(doc_ids)),
            HasilPreprocessing.step_name.in_(TRAIN_EXPAND_STEPS),
            HasilPreprocessing.status == 'selesai',
            HasilPreprocessing.path_output != '',
        )
        .group_by(HasilPreprocessing.dokumentasi_id)
        .having(func.count(func.distinct(HasilPreprocessing.step_name)) == len(TRAIN_EXPAND_STEPS))
        .all()
    )
    return {r[0] for r in rows}


def _expanded_sample_count(doc_ids):
    """
    Estimasi total sampel training+validasi setelah ekspansi cnn_service.load_dataset,
    termasuk dedup tahap yang kontennya identik (mis. crop_enabled=False membuat 'crop'
    sama persis dengan 'resize') — selalu konsisten dengan apa yang benar-benar dimuat
    load_dataset. Nilai ini sama untuk setiap fold, karena train dan val diperlakukan
    seragam (lihat load_dataset).
    """
    return cnn_service.effective_sample_count(doc_ids, BASE_DIR)


def _get_labeled_items():
    """
    Ambil semua DokumentasiFoto yang lokasinya sudah punya LabelKerusakan.
    Return list of dict {dokumentasi_id, label_id, nama_file, latitude, longitude}.
    """
    rows = (
        db.session.query(
            DokumentasiFoto.id,
            DokumentasiFoto.nama_file,
            DokumentasiFoto.path_file,
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
            'path_file':      r.path_file,
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
    total_sampel   = _expanded_sample_count(doc_ids)
    tingkat_list   = TingkatKerusakan.query.order_by(TingkatKerusakan.id).all()
    return render_template(
        'split/index.html',
        configs=configs,
        total_berlabel=total_berlabel,
        total_prep=total_prep,
        total_sampel=total_sampel,
        tingkat_list=tingkat_list,
    )


@split_bp.route('/progress')
@login_required
def progress():
    """Progres pembuatan split untuk user yang sedang login (dipoll saat POST berjalan)."""
    prog = _progress.get(current_user.id)
    if prog is None:
        return jsonify({'status': 'selesai', 'pct': 100})
    return jsonify(prog)


@split_bp.route('/new', methods=['GET', 'POST'])
@admin_required
def new():
    tingkat_list = TingkatKerusakan.query.order_by(TingkatKerusakan.id).all()
    items        = _get_labeled_items()

    kelas_count  = Counter(i['label_id'] for i in items)
    doc_ids      = {i['dokumentasi_id'] for i in items}
    total_prep   = len(_prep_coverage(doc_ids))
    total_sampel = _expanded_sample_count(doc_ids)

    if request.method == 'POST':
        nama         = request.form.get('nama', '').strip()
        try:
            n_splits     = max(3, min(10, int(request.form.get('n_splits') or 5)))
            random_state = int(request.form.get('random_state') or 42)
            radius_m     = max(0, min(500, int(request.form.get('radius_grup_m') or 0)))
            ulangan      = max(1, min(MAKS_ULANGAN, int(request.form.get('ulangan') or 1)))
        except ValueError:
            flash('K, random state, radius, dan jumlah ulangan harus berupa bilangan bulat.', 'warning')
            return redirect(url_for('split.new'))

        if not nama:
            flash('Nama split wajib diisi.', 'warning')
            return redirect(url_for('split.new'))

        if not items:
            flash('Tidak ada data berlabel. Tambah label SDI terlebih dahulu.', 'warning')
            return redirect(url_for('split.new'))

        min_class = min(kelas_count.values()) if kelas_count else 0
        if min_class < n_splits:
            flash(
                f'Kelas terkecil hanya {min_class} sampel — K tidak boleh lebih dari {min_class}.',
                'danger',
            )
            return redirect(url_for('split.new'))

        ids = [i['dokumentasi_id'] for i in items]
        _lapor(current_user.id, 15, 'Mendeteksi foto near-duplicate')
        # Tanpa centang: tiap foto grupnya sendiri, sama dengan StratifiedKFold biasa di notebook Colab.
        if request.form.get('grup_duplikat'):
            dup_groups = find_duplicate_groups(ids, [i['path_file'] for i in items], BASE_DIR)
        else:
            dup_groups = {d: d for d in ids}
        _lapor(current_user.id, 50, 'Mengelompokkan foto radius GPS')
        spatial_groups = find_spatial_groups(ids, [(i['latitude'], i['longitude']) for i in items], radius_m)
        group_map = merge_group_maps(ids, dup_groups, spatial_groups)
        groups = [group_map[d] for d in ids]
        ukuran = Counter(groups)
        terbesar = max(ukuran.values())
        if terbesar > len(items) // n_splits:
            _progress.pop(current_user.id)
            flash(f'Radius {radius_m} m menggabungkan {terbesar} foto ke satu grup, lebih besar dari satu fold '
                  f'(±{len(items) // n_splits} foto), sehingga fold tidak bisa seimbang. Kecilkan radius atau kurangi K.',
                  'danger')
            return redirect(url_for('split.new'))
        n_grup_foto = len(items) - len(ukuran)
        if n_grup_foto > 0:
            flash(f'{n_grup_foto} foto digabung ke grup near-duplicate/spasial (radius {radius_m} m; grup terbesar '
                  f'{terbesar} foto) dan selalu berada di fold yang sama.', 'info')

        dibuat = []
        for r in range(ulangan):
            seed = random_state + r
            _lapor(current_user.id, 50 + round((r + 0.5) / ulangan * 40),
                   f'Membagi fold secara stratified ({r + 1}/{ulangan})')
            result = SplitService.run(n_splits, seed, items, groups=groups)
            config = SplitConfig(
                nama=nama if ulangan == 1 else f'{nama} (ulangan {r + 1}/{ulangan}, seed {seed})',
                n_splits=n_splits,
                random_state=seed,
                radius_grup_m=radius_m,
                label_sumber='tingkat',
                total_data=len(result),
                pengguna_id=current_user.id,
            )
            db.session.add(config)
            db.session.flush()
            db.session.bulk_insert_mappings(SplitItem, [
                {
                    'config_id':            config.id,
                    'dokumentasi_id':       x['dokumentasi_id'],
                    'tingkat_kerusakan_id': x['label_id'],
                    'fold_index':           x['fold_index'],
                }
                for x in result
            ])
            dibuat.append(config)
        db.session.commit()
        _progress.pop(current_user.id)

        if ulangan == 1:
            flash(f'Split "{nama}" berhasil dibuat dengan {len(items)} data.', 'success')
            return redirect(url_for('split.detail', config_id=dibuat[0].id))
        flash(f'{ulangan} split "{nama}" berhasil dibuat (seed {random_state}–{random_state + ulangan - 1}), '
              f'masing-masing {len(items)} data. Latih satu model per split lalu gabungkan hasilnya di '
              'Arsitektur CNN → Ringkasan Repeated CV.', 'success')
        return redirect(url_for('split.index'))

    return render_template(
        'split/form.html',
        tingkat_list=tingkat_list,
        total_berlabel=len(items),
        total_prep=total_prep,
        total_sampel=total_sampel,
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

    # Preprocessing coverage (K-Fold: setiap foto berperan sebagai train & val di fold berbeda)
    all_doc_ids  = {r.dokumentasi_id for r in items}
    prep_ids     = _prep_coverage(all_doc_ids)
    fold_indices = sorted(set(r.fold_index for r in items))
    fold_prep    = {}
    for fi in fold_indices:
        fold_ids      = {r.dokumentasi_id for r in items if r.fold_index == fi}
        fold_prep[fi] = {
            'total':  len(fold_ids),
            'prep':   len(prep_ids & fold_ids),
            'sampel': _expanded_sample_count(fold_ids),
        }

    prep_coverage = {
        'total':       len(prep_ids),
        'grand_total': len(all_doc_ids),
        'per_fold':    fold_prep,
        'sampel':      _expanded_sample_count(all_doc_ids),
    }

    return render_template(
        'split/detail.html',
        config=config,
        tingkat_list=tingkat_list,
        label_map=label_map,
        dist=dist,
        prep_coverage=prep_coverage,
        fold_indices=fold_indices,
        label_basi=jumlah_label_basi(config_id),
    )


@split_bp.route('/<int:config_id>/delete', methods=['POST'])
@admin_required
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
@admin_required
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

    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(['nama_file', 'split', 'tingkat', 'latitude', 'longitude'])
    for r in rows:
        split_label = f'Fold {r.fold_index + 1}'
        writer.writerow([
            r.nama_file,
            split_label,
            tingkat_map.get(r.tingkat_kerusakan_id, ''),
            r.latitude,
            r.longitude,
        ])

    filename = f"split_{secure_filename(config.nama) or config.id}_K{config.n_splits}.csv"
    return Response(
        buf.getvalue(),
        mimetype='text/csv',
        headers={'Content-Disposition': f'attachment; filename="{filename}"'},
    )
