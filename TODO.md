# TODO: Rewrite Sistem Labeling `cnn-jalan` — Formula SDI → Klasterisasi K-Means

Dokumen ini adalah instruksi kerja untuk AI coding agent. Tujuannya: mengganti metode
labeling otomatis di repo `cnn-jalan` (Flask + SQLAlchemy + MySQL) dari formula SDI
berbasis Panjang x Lebar (P x L) ke metode klasterisasi K-Means atas fitur visual citra,
yang sudah divalidasi di notebook Google Colab dan terbukti jauh lebih baik.

Baca seluruh dokumen ini dulu sebelum mengubah kode apa pun. Ikuti urutan fase yang
diberikan. Jangan mengubah bagian yang ditandai "JANGAN DIUBAH".

---

## 0. Ringkasan Eksekutif

| | Sebelum | Sesudah |
|---|---|---|
| Sumber label | Kolom Excel Panjang (P) dan Lebar (L) per lokasi | Fitur visual citra (embedding MobileNetV2 + edge density) |
| Metode | Formula SDI Bina Marga, tapi P/L cuma proksi buatan (bukan hasil ukur retak/lubang/rutting asli) | Klasterisasi tak terawasi (K-Means, k=4) |
| Akurasi/konsistensi | ~46-50% cocok dengan kondisi visual foto | 82.86% self-consistency (lihat catatan penting di bagian 1.3) |
| Distribusi kelas | Timpang, sering nyangkut di beberapa nilai SDI tetap | Jauh lebih seimbang (lihat bagian 1.2) |
| Model tabel `label_kerusakan` | `persen_retak`, `jenis_retak`, `jumlah_lubang`, `kedalaman_rutting`, `sdi_score` | `metode`, `cluster_id`, `kepadatan_tepi`, `jarak_centroid`, `hasil_labeling_id` |

Yang berubah: **hanya subsistem labeling** — 1 model (rewrite), 3 model baru, 1 service baru,
1 controller (rewrite sebagian besar), 4 template (2 rewrite, 2 baru), 1 file test (hapus 5
fungsi test lama, tambah test baru).

Yang **tidak** berubah: pipeline CNN (`cnn_service/*`), preprocessing, augmentasi, split,
dedup, metrics, evaluasi, klasifikasi, peta. Daftar lengkap di bagian 2.

---

## 1. Konteks & Riwayat Masalah

### 1.1 Kenapa formula SDI berbasis P x L harus diganti

File `app/models/label_kerusakan.py` punya method `estimasi_dari_dimensi(panjang, lebar)`
yang menghitung `persen_retak`, `jumlah_lubang`, `kedalaman_rutting` dari luas area (P x L)
memakai konstanta asumsi (`SEGMEN_M2=700`, `LUBANG_M2=0.5`, `REF_RUTTING=4.0`, dst, lihat
komentar "ASUMSI kalibrasi" di file itu sendiri). Ini secara arsitektur sama persis dengan
pendekatan proxy P x L yang sudah diuji di notebook Colab dan terbukti hanya menghasilkan
~46-50% kecocokan dengan kondisi visual foto asli, karena P x L cuma dimensi kerusakan yang
diukur di lapangan, bukan representasi visual retak/lubang/rutting yang sebenarnya.

Riwayat percobaan di notebook (semua sudah dibuang berurutan):
1. Proxy P x L → formula SDI: ~46-50% cocok dengan kondisi visual.
2. Deteksi piksel manual (threshold warna/tekstur): 37.5% akurasi, rata-rata cuma menangkap
   0.0015% luas foto sebagai "retak" — jauh dari realistis.
3. **Klasterisasi K-Means atas fitur visual (metode final, sudah divalidasi): 82.86%
   self-consistency**, dipilih user secara eksplisit sebagai metode labeling non-manual.

### 1.2 Hasil validasi notebook (sumber: `hasil_klasifikasi_jalan_1.csv`, 280 baris)

Distribusi kelas hasil klasterisasi (kolom `Kelas`):
- Rusak Ringan: 105
- Rusak Berat: 64
- Baik: 62
- Sedang: 49

Distribusi hasil prediksi CNN setelah training di atas label ini (kolom `Kelas_Prediksi`):
- Rusak Ringan: 93
- Rusak Berat: 80
- Baik: 59
- Sedang: 48

Kolom `Cocok` (label klasterisasi == prediksi CNN): 232/280 baris = **82.86%**.

### 1.3 Catatan penting yang wajib disebut di bab metodologi skripsi

82.86% ini adalah **self-consistency di seluruh dataset** (termasuk data yang sudah dilihat
model saat training), bukan akurasi validasi pada data yang benar-benar belum pernah dilihat
model. Ini bukan angka yang bisa dibandingkan apple-to-apple dengan akurasi CV resmi sistem
Flask (~45%, lihat komentar di `app/controllers/klasifikasi_controller.py`:
`AMBANG_CONFIDENCE = 0.5`, "Akurasi CV resmi sistem sekitar 45%"). Setelah rewrite ini
selesai dan sistem dilatih ulang dengan label baru, jalankan K-Fold CV resmi
(`metrics_service.cv_summary`) untuk dapat angka akurasi held-out yang valid, lalu
bandingkan dengan baseline 45% tersebut. Jangan pernah melaporkan 82.86% sebagai "akurasi
CV" di skripsi — itu klaim yang salah.

### 1.4 Algoritma klasterisasi yang tervalidasi (dari `cnn_kerusakan_jalan_lhokseumawe.py`, Cell 3a)

Ini adalah spesifikasi wajib yang harus direplikasi persis di service Flask (dengan adaptasi
level-lokasi, lihat bagian 3.2):

```
1. Ekstraksi fitur per foto:
   - Load citra, convert BGR->RGB, resize ke 224x224 dengan interpolasi LANCZOS4.
   - Embedding: MobileNetV2(input_shape=(224,224,3), include_top=False, pooling='avg',
     weights='imagenet') -> vektor 1280 dimensi, lewat preprocess_input MobileNetV2
     terlebih dulu.
   - Kepadatan tepi (edge density): convert ke grayscale, cv2.Canny(low=50, high=150),
     lalu mean(tepi)/255 -> proksi keparahan retak.

2. Reduksi dimensi + standarisasi (dilakukan atas SELURUH kumpulan fitur sekaligus,
   bukan per foto):
   - StandardScaler pada embedding.
   - PCA(n_components=50, random_state=42).

3. Klasterisasi:
   - KMeans(n_clusters=4, random_state=42, n_init=10) pada hasil PCA.

4. Urutkan klaster jadi kelas SDI:
   - Hitung rata-rata kepadatan tepi per klaster.
   - Urutkan ascending (tepi paling sedikit = jalan paling mulus).
   - Petakan urutan ini ke ['Baik', 'Sedang', 'Rusak Ringan', 'Rusak Berat'].
   - Ini KONSISTEN dengan `app/kelas.py`: tingkat_kerusakan_id 4=Baik, 3=Sedang,
     2=Rusak Ringan, 1=Rusak Berat (index kelas CNN = tingkat_kerusakan_id - 1).
```

Jangan menebak parameter ini. Angka 224x224, Canny(50,150), PCA 50 komponen, KMeans k=4
random_state=42 n_init=10 adalah nilai yang benar-benar dipakai saat notebook menghasilkan
82.86% self-consistency itu — jadikan ini nilai default di `LabelingConfig` (boleh dibuat
bisa dikustomisasi lewat UI, tapi default harus sama persis).

---

## 2. Yang TIDAK Boleh Diubah

Modul-modul ini sudah lebih matang daripada notebook dan tidak berkaitan dengan masalah
labeling. Jangan disentuh sama sekali kecuali ada bug yang benar-benar ditemukan saat
mengerjakan tugas ini:

- `app/services/cnn_service/*` (model.py, dataset.py, training.py, evaluation.py,
  prediction.py) — pipeline training MobileNetV2/EfficientNetB0, augmentasi in-model,
  mixup, label smoothing, two-phase training, K-Fold CV + TTA.
- `app/services/preprocessing_service.py` — resize/crop/normalisasi/denoise.
- `app/services/augmentation_service.py`
- `app/services/split_service.py` dan `app/services/dedup_service.py` — stratified/grouped
  K-Fold split, deteksi foto duplikat/spasial.
- `app/services/metrics_service.py` — CV summary resmi.
- `app/controllers/arsitektur_controller.py`, `preprocessing_controller.py`,
  `augmentasi_controller.py`, `split_controller.py`, `klasifikasi_controller.py`,
  `peta_controller.py`, `evaluasi_controller.py`, `dashboard_controller.py`,
  `auth_controller.py`, `lokasi_controller.py`.
- `app/kelas.py` — definisi 4 kelas sudah benar dan konsisten, dipakai sebagai acuan.
- Semua model lain di `app/models/` selain `label_kerusakan.py` (lihat daftar field FK yang
  dipakai di bagian 3, tapi jangan diubah strukturnya).
- Semua test selain 5 fungsi SDI di `tests/test_p2.py` (lihat bagian 6).

**Verifikasi penting yang sudah dicek**: hasil grep menyeluruh di seluruh repo membuktikan
field/method lama (`sdi_score`, `hitung_sdi`, `tingkat_dari_sdi`, `estimasi_dari_dimensi`,
`persen_retak`, `jenis_retak`, `jumlah_lubang`, `kedalaman_rutting`, route `auto_label`,
route `hitung-sdi`) HANYA dipakai di 4 file: `app/models/label_kerusakan.py`,
`app/controllers/label_controller.py`, `app/templates/label/index.html`,
`app/templates/label/edit.html`, dan `tests/test_p2.py`. Tidak ada file lain yang perlu
disentuh untuk menghapus dependensi ke formula lama. Lakukan grep ulang setelah rewrite
untuk memastikan tidak ada sisa referensi.

---

## 3. Keputusan Arsitektur yang Sudah Diambil (jangan didesain ulang)

### 3.1 Konsistensi ID kelas

`tingkat_kerusakan_id` TIDAK berubah maknanya: 1=Rusak Berat, 2=Rusak Ringan, 3=Sedang,
4=Baik (lihat `app/kelas.py` dan `LabelKerusakan.tingkat_dari_sdi` lama sebagai bukti
konsistensi). Field FK `tingkat_kerusakan_id` di `LabelKerusakan` **dipertahankan**. Semua
downstream (`split_service`, training, evaluasi, peta, klasifikasi) bergantung pada field
ini terisi benar — jangan ganti nama atau tipe datanya.

### 3.2 Level agregasi fitur: per LOKASI, bukan per FOTO

Notebook bekerja per foto (satu baris CSV = satu foto). Tapi `LabelKerusakan.lokasi_id`
punya constraint `unique=True` — satu label per `LokasiKerusakan`, sedangkan satu lokasi
bisa punya banyak foto (`LokasiKerusakan.foto_list`, tanpa unique constraint di
`DokumentasiFoto.lokasi_id`). Ini sudah konsisten dengan cara data dipakai downstream:
`split_controller._get_labeled_items()` men-join `DokumentasiFoto` ke `LokasiKerusakan` ke
`LabelKerusakan`, sehingga setiap foto di lokasi yang sama otomatis mewarisi
`tingkat_kerusakan_id` yang sama dari lokasi induknya.

**Keputusan wajib diikuti**: ekstraksi fitur dilakukan per foto (embedding + edge density),
lalu **dirata-rata (mean) di level lokasi** sebelum masuk ke StandardScaler/PCA/KMeans.
Satu lokasi menghasilkan satu titik data untuk klasterisasi. Lokasi tanpa foto (foto_list
kosong) atau semua filenya hilang dari disk, dilewati (skip) dan dicatat sebagai
"tidak bisa dilabel otomatis, perlu foto" — jangan bikin sistem gagal total karena satu
lokasi bermasalah.

### 3.3 Alur kerja UI: Config → Run → Review → Terapkan (bukan langsung commit)

Auto-label lama (`auto_label` di `label_controller.py`) langsung menulis ke `LabelKerusakan`
tanpa jeda verifikasi. Notebook Cell 3b justru menekankan validasi visual dulu sebelum
dipakai ("BUKAN pelabelan manual, hanya spot-check cepat, tapi tetap perlu dicek"). Karena
klasterisasi tak terawasi bisa saja menghasilkan urutan klaster yang tidak masuk akal
(walau jarang), alur baru WAJIB punya tahap review sebelum hasil diterapkan ke
`LabelKerusakan`:

1. **Config**: admin atur parameter (n_cluster, komponen PCA, ambang Canny, random_state).
2. **Run**: jalankan ekstraksi fitur + klasterisasi, simpan hasil sementara di tabel baru
   (belum menyentuh `LabelKerusakan`).
3. **Review**: tampilkan distribusi kelas + galeri sampel per kelas (5 foto/kelas, meniru
   Cell 3b) supaya admin bisa menilai sekilas apakah urutan Baik→Rusak Berat masuk akal.
4. **Terapkan**: admin menekan tombol, baru hasil run itu di-upsert ke `LabelKerusakan`.
   Atau **Buang**: hasil run dihapus tanpa memengaruhi label yang sudah ada.

Ini mengikuti pola "Config + Hasil" yang sudah dipakai konsisten di seluruh repo
(`PreprocessingConfig`/`HasilPreprocessing`, `AugmentasiConfig`/`HasilAugmentasi`,
`SplitConfig`/`SplitItem`, `ArsitekturConfig`/`HasilTraining`).

### 3.4 ⚠️ KEPUTUSAN YANG BUTUH KONFIRMASI EKSPLISIT DARI USER SEBELUM DIEKSEKUSI

Data lama berikut ini dibangun di atas metodologi P x L yang sekarang dianggap tidak valid:
- Semua baris `label_kerusakan` existing (dari `auto_label` P x L atau input manual formula
  SDI lama).
- Semua baris `split_item` (K-Fold split dibangun dari label lama).
- Semua `arsitektur_config` yang sudah selesai training (`status` completed, punya
  `model_path`/`final_model_path`) — model itu dilatih dari label dan split yang sekarang
  tidak valid lagi.

**JANGAN otomatis men-drop atau men-truncate data ini.** Sebelum mengeksekusi migrasi
database yang mengubah skema `label_kerusakan` (bagian 4), AI agent WAJIB:
1. Menjalankan migrasi skema dulu (menambah kolom baru, TANPA menghapus data lama kalau
   memungkinkan — atau simpan backup/export CSV dari tabel `label_kerusakan`,
   `split_item` sebelum migrasi destructive).
2. Memberi tahu user secara eksplisit bahwa label lama akan menjadi tidak konsisten dengan
   metode baru, dan **menunggu konfirmasi user** sebelum menjalankan `hapus_semua` /
   truncate pada `label_kerusakan`, `split_item`, atau menghapus `arsitektur_config` lama.
3. Kalau user setuju dihapus: hapus lewat fitur yang sudah ada di UI (tombol "Hapus Semua"
   di `label/index.html`, reset di `split_controller`) — bukan lewat SQL manual — supaya
   file model dan cascade relationship ikut dibersihkan dengan benar.

Ini satu-satunya langkah yang boleh berhenti dan bertanya ke user. Semua langkah lain di
dokumen ini bisa dikerjakan langsung.

---

## 4. Rencana Skema Database (P0)

### 4.1 Rewrite `app/models/label_kerusakan.py`

Hapus total: kolom `persen_retak`, `jenis_retak`, `jumlah_lubang`, `kedalaman_rutting`,
`sdi_score`, dan static method `hitung_sdi`, `tingkat_dari_sdi`, `estimasi_dari_dimensi`
beserta konstanta `SEGMEN_M2`, `LUBANG_M2`, `REF_RUTTING`, `RUTTING_MAX`, `AMBANG_LEBAR`,
`LUBANG_MAX`.

Skema baru:

```python
from app import utcnow
from app import db


class LabelKerusakan(db.Model):
    __tablename__ = 'label_kerusakan'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lokasi_id            = db.Column(db.Integer, db.ForeignKey('lokasi_kerusakan.id', ondelete='CASCADE'), nullable=False, unique=True)
    tingkat_kerusakan_id = db.Column(db.Integer, db.ForeignKey('tingkat_kerusakan.id'), nullable=False)
    metode               = db.Column(db.Enum('klasterisasi', 'manual'), nullable=False, default='klasterisasi')
    cluster_id           = db.Column(db.Integer, nullable=True)
    kepadatan_tepi       = db.Column(db.Numeric(6, 4), nullable=True)
    jarak_centroid       = db.Column(db.Numeric(10, 4), nullable=True)
    hasil_labeling_id    = db.Column(db.Integer, db.ForeignKey('hasil_labeling.id', ondelete='SET NULL'), nullable=True)
    catatan              = db.Column(db.Text, nullable=True)
    pengguna_id          = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at           = db.Column(db.DateTime, default=utcnow)
    updated_at           = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    tingkat = db.relationship('TingkatKerusakan', backref='label_list', lazy=True)
    pengguna = db.relationship('Pengguna', backref='label_list', lazy=True)

    def __repr__(self):
        return f'<LabelKerusakan lokasi={self.lokasi_id} tingkat={self.tingkat_kerusakan_id} metode={self.metode}>'
```

Catatan: `metode='manual'` dipakai saat admin override lewat form edit langsung (bagian
5.3), `metode='klasterisasi'` saat berasal dari hasil run yang diterapkan
(`hasil_labeling_id` terisi). Saat manual, `hasil_labeling_id` boleh `NULL`.

### 4.2 Model baru: `app/models/labeling_config.py`

```python
from app import utcnow
from app import db


class LabelingConfig(db.Model):
    __tablename__ = 'labeling_config'

    id           = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_config  = db.Column(db.String(100), nullable=False)
    n_cluster    = db.Column(db.Integer, nullable=False, default=4)
    pca_komponen = db.Column(db.Integer, nullable=False, default=50)
    random_state = db.Column(db.Integer, nullable=False, default=42)
    canny_low    = db.Column(db.Integer, nullable=False, default=50)
    canny_high   = db.Column(db.Integer, nullable=False, default=150)
    is_default   = db.Column(db.Boolean, nullable=False, default=False)
    pengguna_id  = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at   = db.Column(db.DateTime, default=utcnow)

    hasil_list = db.relationship('HasilLabeling', backref='config', lazy=True, cascade='all, delete-orphan')
    pengguna   = db.relationship('Pengguna', backref='labeling_config_list', lazy=True)

    @classmethod
    def aktif(cls):
        """Config dari run klasterisasi terakhir yang SUDAH DITERAPKAN. Belum ada -> default/pertama."""
        from app.models.hasil_labeling import HasilLabeling
        terakhir = HasilLabeling.query.filter_by(is_diterapkan=True).order_by(HasilLabeling.id.desc()).first()
        return (terakhir.config if terakhir else None) \
            or cls.query.filter_by(is_default=True).first() or cls.query.order_by(cls.id).first()

    def __repr__(self):
        return f'<LabelingConfig {self.nama_config}>'
```

Field ini meng-cover semua parameter di bagian 1.4. Nilai default harus sama dengan nilai
default kolom (4, 50, 42, 50, 150) — cocok dengan notebook.

### 4.3 Model baru: `app/models/hasil_labeling.py` (satu baris = satu eksekusi run)

```python
from app import utcnow
from app import db


class HasilLabeling(db.Model):
    __tablename__ = 'hasil_labeling'

    id               = db.Column(db.Integer, primary_key=True, autoincrement=True)
    config_id        = db.Column(db.Integer, db.ForeignKey('labeling_config.id'), nullable=False)
    jumlah_lokasi    = db.Column(db.Integer, nullable=False, default=0)
    jumlah_dilewati  = db.Column(db.Integer, nullable=False, default=0)
    variansi_pca     = db.Column(db.Numeric(5, 4), nullable=True)
    distribusi_kelas = db.Column(db.Text, nullable=True)   # JSON string, mis. {"Baik": 62, "Sedang": 49, ...}
    status           = db.Column(db.Enum('selesai', 'gagal'), nullable=False, default='selesai')
    catatan          = db.Column(db.Text, nullable=True)
    is_diterapkan    = db.Column(db.Boolean, nullable=False, default=False)
    diterapkan_at    = db.Column(db.DateTime, nullable=True)
    pengguna_id      = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at       = db.Column(db.DateTime, default=utcnow)

    item_list = db.relationship('HasilLabelingItem', backref='run', lazy=True, cascade='all, delete-orphan')
    pengguna  = db.relationship('Pengguna', backref='hasil_labeling_list', lazy=True)

    def __repr__(self):
        return f'<HasilLabeling config={self.config_id} status={self.status} diterapkan={self.is_diterapkan}>'
```

### 4.4 Model baru: `app/models/hasil_labeling_item.py` (satu baris = satu lokasi dalam satu run)

```python
from app import db


class HasilLabelingItem(db.Model):
    __tablename__ = 'hasil_labeling_item'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    run_id               = db.Column(db.Integer, db.ForeignKey('hasil_labeling.id', ondelete='CASCADE'), nullable=False)
    lokasi_id            = db.Column(db.Integer, db.ForeignKey('lokasi_kerusakan.id', ondelete='CASCADE'), nullable=False)
    klaster              = db.Column(db.Integer, nullable=False)
    kepadatan_tepi       = db.Column(db.Numeric(6, 4), nullable=False)
    jarak_centroid       = db.Column(db.Numeric(10, 4), nullable=True)
    tingkat_kerusakan_id = db.Column(db.Integer, db.ForeignKey('tingkat_kerusakan.id'), nullable=False)

    lokasi  = db.relationship('LokasiKerusakan', lazy=True)
    tingkat = db.relationship('TingkatKerusakan', lazy=True)

    def __repr__(self):
        return f'<HasilLabelingItem lokasi={self.lokasi_id} klaster={self.klaster}>'
```

### 4.5 Update `app/models/__init__.py`

Tambahkan 3 import baru (urutan penting: `LabelingConfig` dan `HasilLabeling` harus
ter-import sebelum `LabelKerusakan` dipakai lintas modul, tapi karena SQLAlchemy
memakai string relationship, urutan import tidak kritikal — cukup pastikan ketiganya ada):

```python
from app.models.labeling_config import LabelingConfig
from app.models.hasil_labeling import HasilLabeling
from app.models.hasil_labeling_item import HasilLabelingItem
```

Tambahkan tepat sebelum atau sesudah baris `from app.models.label_kerusakan import LabelKerusakan`
yang sudah ada. Tanpa ini, Flask-Migrate/Alembic tidak akan mendeteksi tabel baru.

### 4.6 Migrasi database

Repo clone yang tersedia untuk riset ini tidak menyertakan folder `migrations/` (shallow
clone, commit tunggal). AI agent WAJIB mengecek keberadaan folder ini di working copy user
yang sebenarnya:

- Kalau `migrations/` sudah ada (Flask-Migrate sudah pernah di-init): jalankan
  `flask db migrate -m "rewrite label_kerusakan ke metode klasterisasi"` lalu **periksa
  manual** file migrasi yang dihasilkan sebelum `flask db upgrade` — pastikan kolom lama
  (`persen_retak`, dst) di-drop dan kolom baru sesuai bagian 4.1-4.4, dan foreign key
  `hasil_labeling_id` di `label_kerusakan` dibuat SETELAH tabel `hasil_labeling` ada
  (urutan operasi migrasi harus benar: buat `labeling_config` → `hasil_labeling` →
  `hasil_labeling_item` → alter `label_kerusakan`).
- Kalau `migrations/` belum ada: jalankan `flask db init` dulu, baru `flask db migrate`
  dan `flask db upgrade`.
- Ingat bagian 3.4: backup/export data `label_kerusakan` lama sebelum menjalankan migrasi
  yang men-drop kolom, dan minta konfirmasi user untuk langkah destructive.

---

## 5. Service Baru: `app/services/labeling_service.py`

Buat file baru ini. Bertanggung jawab penuh atas ekstraksi fitur dan klasterisasi,
supaya controller tetap tipis (konsisten dengan pola service lain di repo, mis.
`preprocessing_service.py`, `split_service.py`).

Fungsi yang wajib ada:

```python
def ekstrak_fitur_foto(image_path, canny_low=50, canny_high=150):
    """
    Return (embedding: np.ndarray shape (1280,), kepadatan_tepi: float) untuk satu foto.
    Load via cv2, BGR->RGB, resize 224x224 INTER_LANCZOS4.
    Embedding: MobileNetV2 pooling='avg', weights='imagenet', lewat preprocess_input.
    Kepadatan tepi: Canny(gray, canny_low, canny_high).mean() / 255.
    """

def ekstrak_fitur_lokasi(lokasi_list, upload_folder, canny_low=50, canny_high=150):
    """
    Untuk tiap LokasiKerusakan, panggil ekstrak_fitur_foto untuk setiap foto di
    lokasi.foto_list, lalu rata-ratakan embedding dan kepadatan_tepi di level lokasi
    (lihat bagian 3.2). Lokasi tanpa foto valid di disk di-skip.

    Return:
      fitur_dict: {lokasi_id: {'embedding': np.ndarray, 'kepadatan_tepi': float}}
      dilewati: [{'lokasi_id': int, 'alasan': str}, ...]
    """

def klasterisasi(fitur_dict, n_cluster=4, pca_komponen=50, random_state=42):
    """
    StandardScaler -> PCA(pca_komponen, random_state) -> KMeans(n_cluster, random_state, n_init=10).
    jarak_centroid = jarak euclidean titik (di ruang PCA) ke centroid klasternya sendiri.

    Return:
      hasil: {lokasi_id: {'klaster': int, 'jarak_centroid': float}}
      variansi_pca: float (pca.explained_variance_ratio_.sum())
    """

def urutkan_klaster_ke_tingkat(hasil_klaster, fitur_dict):
    """
    Hitung rata-rata kepadatan_tepi per klaster dari fitur_dict, urutkan ascending,
    petakan ke ['Baik', 'Sedang', 'Rusak Ringan', 'Rusak Berat'] lalu translasikan nama
    kelas itu ke tingkat_kerusakan_id lewat lookup:
    TingkatKerusakan.query.filter_by(nama_tingkat=nama).first().id
    (JANGAN hardcode id 1-4, ambil dari DB supaya tidak rusak kalau urutan seed beda).

    Return: {klaster_id: tingkat_kerusakan_id}
    """

def jalankan_klasterisasi(config, upload_folder, pengguna_id):
    """
    Orkestrasi penuh: ambil semua LokasiKerusakan, ekstrak_fitur_lokasi, klasterisasi,
    urutkan_klaster_ke_tingkat. Simpan HASIL SEMENTARA (belum menyentuh LabelKerusakan):
    - buat 1 baris HasilLabeling (status, jumlah_lokasi, jumlah_dilewati, variansi_pca,
      distribusi_kelas sebagai JSON string, is_diterapkan=False)
    - buat 1 baris HasilLabelingItem per lokasi yang berhasil diekstrak fiturnya
    Commit ke DB. Return objek HasilLabeling yang baru dibuat.

    Kalau ekstraksi gagal total (misal tidak ada lokasi dengan foto valid), buat
    HasilLabeling dengan status='gagal' dan catatan berisi alasannya, JANGAN raise
    exception mentah ke controller.
    """

def terapkan_hasil(run):
    """
    Untuk setiap HasilLabelingItem di `run`, upsert LabelKerusakan:
    cari LabelKerusakan by lokasi_id, kalau belum ada buat baru, isi
    tingkat_kerusakan_id, metode='klasterisasi', cluster_id, kepadatan_tepi,
    jarak_centroid, hasil_labeling_id=run.id, pengguna_id.
    Set run.is_diterapkan=True, run.diterapkan_at=utcnow(). Commit.
    Return jumlah lokasi yang diterapkan.
    """

def buang_hasil(run):
    """Hapus run (cascade menghapus semua HasilLabelingItem-nya). Commit."""
```

Import yang dibutuhkan sudah tersedia di `requirements.txt` (tidak perlu menambah
dependency baru): `tensorflow`, `opencv-python`, `numpy`, `scikit-learn`.

Performa: dataset saat ini berjumlah ratusan lokasi (~280 foto di CSV validasi). Ekstraksi
fitur MobileNetV2 forward-pass per foto itu ringan tapi tetap lebih berat dari resize biasa.
Jalankan **sinkron** di dalam request (seperti pola `preprocessing_controller.run()` yang
looping tanpa threading untuk jumlah foto serupa), BUKAN pakai background thread — kompleksitas
progress-polling (pola di `arsitektur_controller.py`) tidak diperlukan untuk skala data ini.
Kalau di masa depan dataset membesar drastis dan run terasa lambat di browser (timeout),
baru pertimbangkan pola threading + progress endpoint seperti training.

---

## 6. Controller: `app/controllers/label_controller.py`

### 6.1 Route yang DIHAPUS

- `POST /label/auto` (`auto_label`) — diganti oleh alur config/run/review di bawah.
- `POST /label/hitung-sdi` (`hitung_sdi`) — endpoint AJAX kalkulasi SDI, tidak relevan lagi.

### 6.2 Route yang TETAP ADA (tidak berubah logikanya)

- `GET /label/` (`index`) — tetap ambil semua `LokasiKerusakan`, tapi update konteks yang
  dikirim ke template (bagian 7.1).
- `POST /label/<lokasi_id>/delete` (`delete`) — tidak berubah.
- `POST /label/hapus-semua` (`hapus_semua`) — tidak berubah.

### 6.3 Route `edit` — disederhanakan total

Ganti form input formula SDI dengan dropdown manual `tingkat_kerusakan_id` langsung:

```python
@label_bp.route('/<int:lokasi_id>/edit', methods=['GET', 'POST'])
@admin_required
def edit(lokasi_id):
    lokasi = LokasiKerusakan.query.get_or_404(lokasi_id)
    label  = LabelKerusakan.query.filter_by(lokasi_id=lokasi_id).first()
    tingkat_list = TingkatKerusakan.query.order_by(TingkatKerusakan.skor_prioritas.desc()).all()

    if request.method == 'POST':
        tingkat_id = request.form.get('tingkat_kerusakan_id', type=int)
        catatan    = request.form.get('catatan', '').strip() or None

        if not tingkat_id:
            flash('Tingkat kerusakan wajib dipilih.', 'danger')
        else:
            if label:
                label.tingkat_kerusakan_id = tingkat_id
                label.metode               = 'manual'
                label.catatan              = catatan
                label.pengguna_id          = current_user.id
                # cluster_id, kepadatan_tepi, jarak_centroid, hasil_labeling_id
                # SENGAJA TIDAK direset ke None supaya riwayat asal-usul klasterisasi
                # sebelumnya (kalau ada) masih bisa ditelusuri walau sudah dioverride manual.
            else:
                label = LabelKerusakan(
                    lokasi_id=lokasi_id,
                    tingkat_kerusakan_id=tingkat_id,
                    metode='manual',
                    catatan=catatan,
                    pengguna_id=current_user.id,
                )
                db.session.add(label)

            db.session.commit()
            flash('Label berhasil disimpan.', 'success')
            return redirect(url_for('label.index'))

    return render_template('label/edit.html', lokasi=lokasi, label=label, tingkat_list=tingkat_list)
```

### 6.4 Route baru: konfigurasi klasterisasi (CRUD, pola sama seperti `preprocessing_controller.py`)

```
GET/POST /label/config/new     -> config_new
GET/POST /label/config/<id>/edit -> config_edit
POST     /label/config/<id>/delete -> config_delete
```

Ikuti persis pola `_config_from_form` / `_update_config_from_form` di
`preprocessing_controller.py`, sesuaikan field ke `LabelingConfig` (bagian 4.2).

### 6.5 Route baru: jalankan klasterisasi

```python
@label_bp.route('/config/<int:config_id>/run', methods=['POST'])
@admin_required
def run(config_id):
    config = LabelingConfig.query.get_or_404(config_id)
    upload_folder = current_app.config['UPLOAD_FOLDER']
    hasil = labeling_service.jalankan_klasterisasi(config, upload_folder, current_user.id)
    if hasil.status == 'gagal':
        flash(f'Klasterisasi gagal: {hasil.catatan}', 'danger')
        return redirect(url_for('label.index'))
    flash(f'Klasterisasi selesai — {hasil.jumlah_lokasi} lokasi diproses, '
          f'{hasil.jumlah_dilewati} dilewati. Silakan review sebelum menerapkan.', 'info')
    return redirect(url_for('label.review', run_id=hasil.id))
```

### 6.6 Route baru: review hasil sebelum diterapkan

```python
@label_bp.route('/review/<int:run_id>')
@admin_required
def review(run_id):
    run = HasilLabeling.query.get_or_404(run_id)
    items_per_kelas = {}  # {nama_tingkat: [HasilLabelingItem, ...][:5]} untuk galeri sampel
    # kelompokkan run.item_list berdasarkan item.tingkat.nama_tingkat, ambil 5 sampel/kelas
    return render_template('label/review.html', run=run, items_per_kelas=items_per_kelas)


@label_bp.route('/review/<int:run_id>/terapkan', methods=['POST'])
@admin_required
def review_terapkan(run_id):
    run = HasilLabeling.query.get_or_404(run_id)
    if run.is_diterapkan:
        flash('Hasil ini sudah pernah diterapkan.', 'warning')
    else:
        jumlah = labeling_service.terapkan_hasil(run)
        flash(f'{jumlah} label berhasil diterapkan.', 'success')
    return redirect(url_for('label.index'))


@label_bp.route('/review/<int:run_id>/buang', methods=['POST'])
@admin_required
def review_buang(run_id):
    run = HasilLabeling.query.get_or_404(run_id)
    labeling_service.buang_hasil(run)
    flash('Hasil klasterisasi dibuang.', 'info')
    return redirect(url_for('label.index'))
```

Tambahkan import: `from app.models.labeling_config import LabelingConfig`,
`from app.models.hasil_labeling import HasilLabeling`,
`from app.services import labeling_service`.

---

## 7. Template

### 7.1 `app/templates/label/index.html` — edit

- Hapus modal "Label Otomatis" (form yang POST ke `label.auto_label`, radio
  pending/semua) di sekitar baris 153.
- Ganti dengan tombol/section baru "Klasterisasi Otomatis": link ke daftar
  `LabelingConfig` (bisa halaman baru `label/config_list.html` atau digabung ke index) dan
  ke riwayat `HasilLabeling` (status diterapkan/belum, link ke halaman review kalau belum
  diterapkan).
- Kolom tabel: ganti `SDI` (baris ~237, `lbl.sdi_score`) jadi `Metode`, `Kepadatan Tepi`
  (`lbl.kepadatan_tepi`), tetap tampilkan `Tingkat` (`lbl.tingkat.nama_tingkat`,
  `warna_peta`) seperti sebelumnya.

### 7.2 `app/templates/label/edit.html` — rewrite total bagian form

- Hapus seluruh form parameter SDI: slider+input `persen_retak`, radio `jenis_retak`,
  slider+input `jumlah_lubang`, slider+input `kedalaman_rutting` (baris ~166-245).
- Hapus seluruh script JS `hitungSDI()` dan salinan formula (baris ~300-362, termasuk
  komentar "Salinan formula app/models/label_kerusakan.py::hitung_sdi").
- Ganti dengan satu `<select name="tingkat_kerusakan_id">` berisi `tingkat_list`
  (dari `TingkatKerusakan`, urut `skor_prioritas` descending, sama seperti yang sudah
  dikirim controller), pre-select `label.tingkat_kerusakan_id` kalau ada. Tambahkan
  `<textarea name="catatan">`. Bagian foto + mini-map di sisi kiri (yang menampilkan
  `lokasi.panjang`/`lokasi.lebar`/`keterangan`/`sumber_data`) **tetap dipertahankan** —
  P/L masih berguna sebagai informasi kontekstual untuk admin, hanya tidak lagi dipakai
  untuk menghitung label otomatis.
- Kalau `label.metode == 'klasterisasi'`, tampilkan info tambahan (read-only) di panel:
  cluster asal, kepadatan tepi, jarak ke centroid — supaya admin tahu label ini berasal
  dari run klasterisasi mana sebelum memutuskan override manual.

### 7.3 `app/templates/label/config_form.html` — baru

Form untuk `LabelingConfig`, pola sama seperti `preprocessing/config_form.html`: input
`nama_config`, `n_cluster` (default 4), `pca_komponen` (default 50), `random_state`
(default 42), `canny_low` (default 50), `canny_high` (default 150), checkbox
`is_default`. Submit ke `config_new`/`config_edit` sesuai `action`.

### 7.4 `app/templates/label/review.html` — baru

- Ringkasan run: `jumlah_lokasi`, `jumlah_dilewati`, `variansi_pca` (tampilkan sebagai
  persentase), distribusi kelas (parse `distribusi_kelas` JSON, tampilkan sebagai
  bar/tabel sederhana).
- Galeri sampel per kelas: untuk tiap kelas (Baik/Sedang/Rusak Ringan/Rusak Berat),
  tampilkan sampai 5 thumbnail foto (ambil dari `item.lokasi.foto_list[0].path_file`
  kalau ada) plus nama lokasi — meniru fungsi Cell 3b di notebook (spot-check visual,
  bukan validasi presisi).
- Tabel lengkap semua item (opsional, bisa dipaginasi kalau lokasi banyak).
- Dua tombol besar: "Terapkan ke Label" (POST ke `review_terapkan`, munculkan
  konfirmasi JS `confirm()` karena ini overwrite label existing) dan "Buang Hasil Ini"
  (POST ke `review_buang`).

---

## 8. Tests

### 8.1 `tests/test_p2.py` — hapus 5 fungsi test ini (baris 15-61 di versi saat ini)

```python
def test_hitung_sdi(self): ...
def test_tingkat_dari_sdi(self): ...
def test_estimasi_dari_dimensi_is_continuous_not_5_fixed_buckets(self): ...
def test_estimasi_dari_dimensi_monotonic_in_area(self): ...
def test_estimasi_dari_dimensi_caps_extreme_area(self): ...
```

**Jangan hapus fungsi test lain di file ini** — sudah diverifikasi bahwa
`test_split_service_is_stratified_and_deterministic`,
`test_read_excel_validates_and_maps_rows`, `test_group_aware_split_never_splits_a_group`,
`test_is_better_checkpoint_prefers_accuracy_over_loss`,
`test_is_better_checkpoint_uses_loss_as_tiebreaker`,
`test_five_crop_flip_views_shape_and_flip_correctness`,
`test_predict_with_tta_averages_all_views`,
`test_predict_probs_with_averages_across_ensemble_models`,
`test_read_excel_rejects_duplicate_or_invalid_rows`,
`test_mixup_dataset_yields_soft_labels_over_all_classes`,
`test_loss_is_categorical_only_when_mixup_or_label_smoothing`,
`test_augmentation_layers_can_be_disabled_per_layer`,
`test_hyperparams_cover_every_training_field_and_reach_train_final`,
`test_preprocessing_pipeline_has_four_steps_and_no_augmentation` semuanya menguji modul
lain yang tidak berubah (split, CNN service, preprocessing) — biarkan apa adanya.

Setelah menghapus, cek juga import di baris atas file: `from app.models.label_kerusakan
import LabelKerusakan` masih dipakai atau tidak oleh test lain di file itu — kalau
tidak dipakai lagi, hapus importnya supaya tidak ada unused-import.

### 8.2 File test lain — baca dulu sebelum menyentuh apa pun

`tests/test_p1.py` (520 baris), `tests/test_augmentation.py`, `tests/test_cnn_dataset.py`,
`tests/test_dedup_service.py`, `tests/test_security.py` belum pernah diperiksa isinya
secara menyeluruh dalam riset untuk dokumen ini. Baca seluruh isinya dulu sebelum
menyimpulkan tidak ada dependensi ke `LabelKerusakan` — hasil grep di bagian 2 sudah
memastikan tidak ada match untuk field/method lama di file manapun selain yang disebut,
tapi tetap jalankan full test suite (`python -m unittest discover tests`) setelah rewrite
untuk memastikan tidak ada breakage tak terduga.

### 8.3 Test baru: `tests/test_labeling_service.py`

Tulis test untuk `labeling_service.py`. Karena memanggil MobileNetV2 asli akan lambat dan
butuh download bobot ImageNet, mock/stub fungsi ekstraksi embedding di sebagian besar test,
kecuali kalau memang ingin ada 1-2 test integrasi lambat yang ditandai terpisah. Minimal
cakup:

- `urutkan_klaster_ke_tingkat` menghasilkan urutan yang benar: klaster dengan kepadatan
  tepi rata-rata terendah harus dapat `tingkat_kerusakan_id` untuk "Baik" (4), tertinggi
  untuk "Rusak Berat" (1) — pakai data fitur dummy/sintetis, tidak perlu foto asli.
- `klasterisasi` deterministik dengan `random_state` yang sama (jalankan dua kali, bandingkan
  hasil klaster identik) — pola serupa `test_split_service_is_stratified_and_deterministic`.
- `ekstrak_fitur_lokasi` melewati (skip) lokasi tanpa foto atau dengan path foto yang tidak
  ada di disk, dan mengembalikannya di `dilewati` dengan alasan yang jelas.
- `terapkan_hasil` benar-benar meng-upsert `LabelKerusakan` (baik untuk lokasi yang belum
  punya label maupun yang sudah), dan menandai `run.is_diterapkan=True`.
- `buang_hasil` menghapus run beserta semua item-nya (cascade), tanpa menyentuh
  `LabelKerusakan` yang sudah ada.

---

## 9. Definition of Done

Centang semua sebelum menganggap rewrite selesai:

- [ ] Migrasi database berjalan bersih (`flask db upgrade`) tanpa error, dan data lama
      sudah di-backup/dikonfirmasi ke user sesuai bagian 3.4.
- [ ] `app/models/__init__.py` sudah mengimpor `LabelingConfig`, `HasilLabeling`,
      `HasilLabelingItem`.
- [ ] Alur Config → Run → Review → Terapkan/Buang berfungsi end-to-end lewat UI, memakai
      parameter default sesuai bagian 1.4 (224x224, Canny 50/150, PCA 50, KMeans k=4
      random_state=42 n_init=10).
- [ ] Distribusi kelas hasil klasterisasi di data user cukup seimbang (bandingkan dengan
      distribusi di bagian 1.2 sebagai acuan kewajaran, tidak harus identik karena dataset
      beda).
- [ ] Form edit manual (`label/edit.html`) berfungsi tanpa formula SDI, hanya dropdown
      tingkat + catatan.
- [ ] `split_controller._get_labeled_items()` tetap berfungsi tanpa perubahan kode (karena
      `tingkat_kerusakan_id` tetap terisi dengan cara yang sama).
- [ ] Training (`arsitektur_controller`) dan evaluasi CV (`metrics_service.cv_summary`)
      berjalan normal di atas label baru, tanpa perubahan kode di modul-modul tersebut.
- [ ] Jalankan K-Fold CV resmi pasca-rewrite, catat angka akurasi held-out yang baru, dan
      bandingkan dengan baseline lama (~45%, dari komentar di `klasifikasi_controller.py`)
      — dengan pemahaman bahwa 82.86% notebook BUKAN angka pembanding yang valid (lihat
      1.3).
- [ ] `python -m unittest discover tests` lulus semua, termasuk test baru untuk
      `labeling_service.py`.
- [ ] Grep ulang seluruh repo untuk `sdi_score`, `hitung_sdi`, `tingkat_dari_sdi`,
      `estimasi_dari_dimensi`, `persen_retak`, `jenis_retak`, `jumlah_lubang`,
      `kedalaman_rutting`, `auto_label`, `hitung-sdi` — hasilnya harus nihil.
- [ ] Tidak ada perubahan kode di modul-modul yang didaftar di bagian 2.

---

## 10. Nice-to-have (P1/P2, kerjakan setelah P0 selesai dan stabil)

- **Cache embedding**: simpan embedding MobileNetV2 mentah per foto (mis. tabel cache
  keyed `dokumentasi_foto_id`) supaya re-run klasterisasi dengan parameter berbeda (ganti
  `n_cluster` atau `pca_komponen`) tidak perlu menghitung ulang forward-pass MobileNetV2
  dari nol — cukup ulangi StandardScaler/PCA/KMeans dari cache.
- **Override manual granular di halaman review**: dropdown per-item di tabel review supaya
  admin bisa koreksi satu-dua lokasi yang jelas salah klaster sebelum menekan "Terapkan",
  tanpa harus edit satu-satu lewat halaman `label/edit.html` setelahnya.
- **Metrik alternatif urutan klaster**: selain kepadatan tepi Canny, uji rata-rata
  intensitas gradien Sobel atau variance-of-Laplacian sebagai sinyal tambahan untuk
  mengurutkan klaster, terutama kalau ada klaster yang urutannya meragukan saat review.
  Jangan ganti default tanpa hasil eksperimen yang mendukung.
- **Ekspor CSV hasil run** (mirip format `hasil_klasifikasi_jalan_1.csv` dari notebook)
  dari halaman review, untuk didokumentasikan di lampiran skripsi.
- **Threading + progress bar** untuk `run/<config_id>` kalau nanti dataset membesar jauh
  dan ekstraksi fitur sinkron mulai terasa lambat di browser — ikuti pola
  `arsitektur_controller.py` (`_progress` dict + endpoint polling) hanya kalau benar-benar
  diperlukan.
