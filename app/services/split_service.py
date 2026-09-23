from collections import defaultdict
from sklearn.model_selection import StratifiedKFold, StratifiedGroupKFold


class SplitService:

    @staticmethod
    def run(n_splits, random_state, items, groups=None):
        """
        Stratified K-Fold split.
        fold_index = 0..n_splits-1
        items: list of dict {dokumentasi_id, label_id, nama_file, latitude, longitude}
        groups: opsional, list sejajar items — id grup (mis. dari dedup_service.find_duplicate_groups).
                Foto dengan group id sama SELALU jatuh di fold yang sama (cegah leakage
                foto near-duplicate). Kalau None atau semua grup singleton, sama seperti
                StratifiedKFold biasa.
        """
        X = list(range(len(items)))
        y = [i['label_id'] for i in items]
        result = [dict(it) for it in items]

        if groups is not None and len(set(groups)) < len(items):
            skf = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
            splits = skf.split(X, y, groups=groups)
        else:
            skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
            splits = skf.split(X, y)

        for fold_idx, (_, val_idx) in enumerate(splits):
            for i in val_idx:
                result[i]['fold_index'] = fold_idx
        return result

    @staticmethod
    def distribusi(items, label_map):
        """
        items: list of dict with 'fold_index' and 'label_id'
        Returns {fold_index: {label_id: count}}
        """
        dist = defaultdict(lambda: defaultdict(int))
        for it in items:
            dist[it['fold_index']][it['label_id']] += 1
        return dist


def jumlah_label_basi(config_id):
    """Jumlah item split yang kelas tersimpannya beda dengan label sekarang (atau labelnya sudah dihapus)."""
    from sqlalchemy import func, or_
    from app import db
    from app.models.dokumentasi_foto import DokumentasiFoto
    from app.models.label_kerusakan import LabelKerusakan
    from app.models.split_item import SplitItem

    return (
        db.session.query(func.count(SplitItem.id))
        .join(DokumentasiFoto, SplitItem.dokumentasi_id == DokumentasiFoto.id)
        .outerjoin(LabelKerusakan, LabelKerusakan.lokasi_id == DokumentasiFoto.lokasi_id)
        .filter(SplitItem.config_id == config_id,
                or_(LabelKerusakan.id.is_(None),
                    LabelKerusakan.tingkat_kerusakan_id != SplitItem.tingkat_kerusakan_id))
        .scalar()
    )
