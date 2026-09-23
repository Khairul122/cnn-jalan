"""Deteksi foto near-duplicate (average hash) supaya split tidak membocorkan
foto yang nyaris identik antara train dan val fold."""
import os
from PIL import Image

HASH_SIZE = 8          # 64-bit hash
DEFAULT_THRESHOLD = 5  # jarak Hamming maksimal untuk dianggap near-duplicate


def average_hash(img_path, hash_size=HASH_SIZE):
    """Average hash 64-bit dari sebuah gambar. None kalau file tidak bisa dibaca."""
    try:
        img = Image.open(img_path).convert('L').resize((hash_size, hash_size), Image.Resampling.LANCZOS)
    except Exception:
        return None
    pixels = list(img.getdata())
    avg = sum(pixels) / len(pixels)
    bits = 0
    for p in pixels:
        bits = (bits << 1) | (1 if p >= avg else 0)
    return bits


def _hamming(a, b):
    return bin(a ^ b).count('1')


def find_duplicate_groups(doc_ids, path_files, base_dir, threshold=DEFAULT_THRESHOLD):
    """
    doc_ids, path_files: list sejajar (dokumentasi_id, path relatif ke app/static).
    Return dict {dokumentasi_id: group_id} — foto yang near-duplicate (jarak hash <=
    threshold) berbagi group_id yang sama. Foto tanpa duplikat jadi group singleton
    (group_id = dokumentasi_id sendiri).
    """
    hashes = {}
    for doc_id, path_rel in zip(doc_ids, path_files):
        full_path = os.path.join(base_dir, 'app', 'static', path_rel)
        h = average_hash(full_path)
        if h is not None:
            hashes[doc_id] = h

    parent = {doc_id: doc_id for doc_id in doc_ids}

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[max(ra, rb)] = min(ra, rb)

    # ponytail: O(n^2) pairwise compare, fine for ~280 foto; pakai BK-tree/LSH kalau dataset jadi ribuan.
    ids = list(hashes.keys())
    for i in range(len(ids)):
        for j in range(i + 1, len(ids)):
            if _hamming(hashes[ids[i]], hashes[ids[j]]) <= threshold:
                union(ids[i], ids[j])

    return {doc_id: find(doc_id) for doc_id in doc_ids}
