from collections import defaultdict
from sklearn.model_selection import train_test_split


class SplitService:

    @staticmethod
    def run(test_size, random_state, items):
        """
        Stratified holdout split.
        fold_index=0 → train (80%), fold_index=1 → test (20%).
        items: list of dict {dokumentasi_id, label_id, nama_file, latitude, longitude}
        """
        X = list(range(len(items)))
        y = [i['label_id'] for i in items]
        train_idx, test_idx = train_test_split(
            X, test_size=test_size, random_state=random_state, stratify=y
        )
        result = [dict(it) for it in items]
        for i in train_idx:
            result[i]['fold_index'] = 0
        for i in test_idx:
            result[i]['fold_index'] = 1
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
