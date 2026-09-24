"""Satu-satunya definisi kelas tingkat kerusakan. Indeks kelas CNN = tingkat_kerusakan_id - 1."""

# Urut dari paling parah; skema 4 kategori SDI Bina Marga (Baik <50 | Sedang 50-100 | Rusak Ringan 100-150 | Rusak Berat >150).
KELAS = (
    {'key': 'rusak_berat',  'nama': 'Rusak Berat',  'warna': '#E53E3E', 'sdi': 'SDI > 150'},
    {'key': 'rusak_ringan', 'nama': 'Rusak Ringan', 'warna': '#F97316', 'sdi': 'SDI 100–150'},
    {'key': 'sedang',       'nama': 'Sedang',       'warna': '#F59E0B', 'sdi': 'SDI 50–100'},
    {'key': 'baik',         'nama': 'Baik',         'warna': '#10B981', 'sdi': 'SDI < 50'},
)
N_KELAS = len(KELAS)
KEYS = tuple(k['key'] for k in KELAS)
LABEL = {i: k['nama'] for i, k in enumerate(KELAS)}
WARNA = {i: k['warna'] for i, k in enumerate(KELAS)}
WARNA_NAMA = {k['nama']: k['warna'] for k in KELAS}
