from collections import defaultdict
from sklearn.model_selection import StratifiedKFold


class SplitService:

    @staticmethod
    def run(n_splits, random_state, items):
        """
        Stratified K-Fold split.
        fold_index = 0..n_splits-1
        items: list of dict {dokumentasi_id, label_id, nama_file, latitude, longitude}
        """
        X = list(range(len(items)))
        y = [i['label_id'] for i in items]
        skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
        result = [dict(it) for it in items]
        for fold_idx, (_, val_idx) in enumerate(skf.split(X, y)):
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
