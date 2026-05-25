# CLAUDE.md

Panduan ini menjelaskan project CNN-Jalan kepada Claude Code saat bekerja di repository ini.
UI dan konten database dalam Bahasa Indonesia.

## Project Overview

**CNN-Jalan** adalah aplikasi web GIS berbasis Flask untuk pemetaan kerusakan jalan di Kota Lhokseumawe, Aceh, Indonesia. Dikembangkan sebagai bagian dari skripsi (NIM 210170072).

**Tujuan utama:**
- Klasifikasi foto kerusakan jalan menggunakan CNN (CRACK / POTHOLE / RUTTING)
- Penilaian tingkat kerusakan: Berat / Sedang / Ringan
- Labeling SDI (Surface Distress Index) — standar Bina Marga
- Preprocessing pipeline gambar (Resize → Center Crop → Normalisasi → Augmentasi → Denoise)
- Split dataset Stratified K-Fold untuk persiapan training CNN
- Visualisasi GIS interaktif dengan Leaflet.js

**Dataset:** 280 foto kerusakan jalan + data Excel koordinat GPS (sudah diimport ke database).

---

## Setup & Running

```powershell
# Buat dan aktifkan virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Import database schema (MySQL harus running)
mysql -u root -p < db_cnn_jalan.sql

# Atau jalankan migration tambahan jika sudah ada database:
# Get-Content migrate_add_preprocessing.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_split.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_arsitektur.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_hasil_evaluasi.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_patience.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_prediksi_model.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_pred_type.sql | & mysql -u root db_cnn_jalan

# Jalankan server development — WAJIB pakai venv python
.\.venv\Scripts\python.exe run.py
```

Akses di: **http://127.0.0.1:5000**

**Akun default:** `admin@gmail.com` / `12345678`

**Konfigurasi database:** Edit `config.py` — ubah password MySQL di `SQLALCHEMY_DATABASE_URI`. Default: password kosong.

---

## Architecture

Flask MVC dengan Blueprints. Semua blueprint didaftarkan di `app/__init__.py` melalui `create_app()`.

| Controller File | Blueprint | URL Prefix | Deskripsi |
|---|---|---|---|
| `auth_controller.py` | `auth` | `/auth` | Login, logout, register |
| `dashboard_controller.py` | `dashboard` | `/` | Halaman utama, KPI stats |
| `lokasi_controller.py` | `lokasi` | `/lokasi` | CRUD lokasi kerusakan |
| `klasifikasi_controller.py` | `klasifikasi` | `/klasifikasi` | Upload foto + klasifikasi CNN |
| `label_controller.py` | `label` | `/label` | Manajemen label SDI |
| `preprocessing_controller.py` | `preprocessing` | `/preprocessing` | Pipeline preprocessing gambar |
| `split_controller.py` | `split` | `/split` | Stratified K-Fold split dataset |
| `arsitektur_controller.py` | `arsitektur` | `/arsitektur` | Konfigurasi & training CNN |
| `peta_controller.py` | `peta` | `/peta` | Peta GIS interaktif (GeoJSON) |
| `evaluasi_controller.py` | `evaluasi` | `/evaluasi` | Evaluasi model CNN |

---

## Database Schema

Database: `db_cnn_jalan` (MySQL utf8mb4)

| Tabel | Deskripsi |
|---|---|
| `pengguna` | Akun user (role: admin/viewer), password bcrypt |
| `jenis_kerusakan` | Master jenis: CRACK, POTHOLE, RUTTING |
| `tingkat_kerusakan` | Master tingkat: Berat (id=1), Sedang (id=2), Ringan (id=3) |
| `lokasi_kerusakan` | Data lokasi GPS + dimensi kerusakan (panjang, lebar) |
| `dokumentasi_foto` | File foto per lokasi, path di `uploads/foto/` |
| `hasil_klasifikasi_cnn` | Output CNN per foto (jenis, tingkat, confidence) |
| `peta_kerusakan` | Status pemetaan (draft→terverifikasi→diperbaiki) |
| `label_kerusakan` | Label SDI manual per lokasi (F_retak+F_lubang+F_rutting) |
| `preprocessing_config` | Konfigurasi pipeline preprocessing (resize/crop/norm/aug/denoise) |
| `hasil_preprocessing` | Record gambar yang telah diproses + path output |
| `evaluasi_model` | Metrik evaluasi CNN manual (akurasi, presisi, recall, F1, confusion matrix) |
| `split_config` | Konfigurasi sesi split K-Fold (nama, K, random_state, total_data) |
| `split_item` | Penugasan setiap foto ke fold tertentu (config_id, dokumentasi_id, fold_index) |
| `arsitektur_config` | Konfigurasi model CNN (model_type, lr, batch_size, epochs, patience, dropout, optimizer, pred_type, status) |
| `hasil_training` | Riwayat training per epoch (loss, accuracy, val_loss, val_accuracy) |
| `hasil_evaluasi` | Evaluasi otomatis model terlatih (confusion matrix JSON, per-class precision/recall/F1, macro avg) |
| `prediksi_model` | Hasil prediksi CNN per foto (arsitektur_id, dokumentasi_id, prediksi 0-2, aktual, confidence) |

**Relasi penting:**
- `lokasi_kerusakan` ← `dokumentasi_foto` ← `hasil_klasifikasi_cnn`
- `lokasi_kerusakan` ← `label_kerusakan` → `tingkat_kerusakan`
- `dokumentasi_foto` ← `hasil_preprocessing` → `preprocessing_config`
- `split_config` ← `split_item` → `dokumentasi_foto`
- `split_item` → `tingkat_kerusakan` (label kelas untuk stratifikasi)
- `arsitektur_config` → `split_config` (data yang dipakai training)
- `arsitektur_config` ← `hasil_training` (riwayat epoch)
- `arsitektur_config` ← `hasil_evaluasi` (confusion matrix + metrik evaluasi otomatis)
- `arsitektur_config` ← `prediksi_model` → `dokumentasi_foto` (hasil prediksi per foto untuk GIS)

---

## Features & Progress

| Fitur | Status | Blueprint | Catatan |
|---|---|---|---|
| Auth (login/register) | Selesai | `auth` | Flask-Login, Werkzeug bcrypt |
| Dashboard | Selesai | `dashboard` | KPI cards, statistik realtime |
| Lokasi Kerusakan | Selesai | `lokasi` | CRUD, mini-map Leaflet di halaman detail |
| Klasifikasi CNN | Placeholder | `klasifikasi` | `_mock_predict()` — belum model nyata |
| Labeling SDI | Selesai | `label` | Auto-label dari P×L, kalkulasi real-time AJAX |
| Preprocessing | Selesai | `preprocessing` | Pipeline 5 tahap (+ Center Crop), OpenCV + Pillow, pagination, modal viewer |
| Split Data | Selesai | `split` | Stratified K-Fold (scikit-learn), distribusi tabel + Chart.js, export CSV |
| Arsitektur CNN | Selesai | `arsitektur` | MobileNetV2 & EfficientNetB0, transfer learning, background training, live progress, loss/acc chart |
| Evaluasi Hasil CNN | Selesai | `arsitektur` | Evaluasi otomatis dari val fold — confusion matrix 3×3, per-class precision/recall/F1, macro avg |
| Prediksi GIS (Single) | Selesai | `arsitektur` | `predict_all()` → simpan ke `prediksi_model`, tampil di peta `/arsitektur/<id>/gis` |
| Prediksi GIS (K-Fold CV) | Selesai | `arsitektur` | `predict_cv()` background thread, live progress, tiap foto diprediksi model yang tidak melihatnya |
| Peta GIS | Selesai | `peta` | Leaflet.js, GeoJSON endpoint, filter status |
| Evaluasi Model (Manual) | Selesai | `evaluasi` | Input manual metrik, tabel perbandingan |
| UI Modernisasi | Selesai | Semua | Split-screen auth, animated KPI, modern table, dropzone, civic govtech design |

---

## Status Akurasi CNN (per 2026-05-25)

**Hasil training terbaik:** 66.07% (MobileNetV2, 80 epoch, fold 4)
**Confusion matrix:** Berat recall 76.5%, Sedang recall 74.1%, Ringan recall 33% ← bottleneck utama

**Masalah yang sudah diidentifikasi dan diperbaiki:**

| # | Masalah | Severity | Fix yang Diterapkan |
|---|---------|----------|---------------------|
| 1 | Dataset sangat kecil (~280 foto, ~56 val/fold) | CRITICAL | Belum bisa difix dari kode — perlu tambah data |
| 2 | Recall Ringan hanya 33% — model bias ke Sedang | CRITICAL | Kembalikan class_weight (Ringan: 1.46x, Sedang: 0.70x) |
| 3 | Focal loss gamma=2.0 mereduksi gradient dari Ringan benar | HIGH | Ganti ke SparseCategoricalCrossentropy |
| 4 | Train pakai preprocessed (augmented), val pakai original | HIGH | load_dataset selalu pakai path_file original |
| 5 | Fine-tune 30 layer dengan 224 sampel → overfitting | MEDIUM | Kurangi 30→15 layer untuk MobileNetV2 |
| 6 | Dense layer langsung ke 3 kelas tanpa capacity | MEDIUM | Tambah Dense(128, relu) + L2(1e-4) sebelum output |
| 7 | EarlyStopping terlalu agresif | HIGH | patience min 20, min_delta 0.001 |
| 8 | ReduceLROnPlateau tidak ada | HIGH | Ditambah di Phase 1 & Phase 2 |
| 9 | predict_all() pakai gambar original bukan preprocessed | BUG | Diperbaiki dengan subquery HasilPreprocessing |

**Target akurasi: >70%**
**Setting yang disarankan untuk training baru:**
- Epochs: 60–80
- Learning Rate: `0.001`
- Batch Size: 32
- Dropout: 0.3–0.5 (model kini ada Dense(128) intermediate + Dropout(dropout/2))
- Patience: biarkan default (min 20)

**Arsitektur head model saat ini:**
`GAP → Dropout(d) → Dense(128, relu, L2) → Dropout(d/2) → Dense(3, softmax, L2)`

---

## Frontend Template System

### Base Template
`app/templates/base.html` — semua halaman authenticated extend ini.
- Bootstrap 5.3.3 + Tailwind CSS Play CDN (`preflight: false` agar tidak bentrok)
- Bootstrap Icons 1.11.3
- Font: **Inter** (Google Fonts) — bukan Fira Code/Fira Sans
- Sidebar navigasi dark, responsive dengan hamburger mobile

### CSS Variables (di `app/static/css/style.css`)
```
--c-bg        background halaman utama
--c-surface   background card/tabel
--c-text      teks utama
--c-muted     teks sekunder/placeholder
--c-border    border card/input
--c-accent    biru govtech (#0369A1) — BUKAN gold atau #38BDF8
--c-primary   navy (#0F172A)
--c-danger    merah (#E53E3E)
--r-card      border-radius card
--r-input     border-radius input/button
--sidebar-w   lebar sidebar
--shadow-card box-shadow card
```

**PENTING:** Selalu gunakan `--c-accent` (#0369A1) untuk warna utama. Jangan overwrite `style.css` tanpa backup — semua token, keyframes, dan animasi ada di sana.

### CSS Classes Penting
- `.btn-cnn-primary` — tombol utama gradient biru
- `.cnn-table` — tabel modern dengan navy thead
- `.cnn-dropzone` — dropzone upload drag-and-drop
- `.cnn-breadcrumb` — breadcrumb topbar
- `.auth-split`, `.auth-hero`, `.auth-glass-card` — layout split-screen login/register
- `.cnn-skeleton`, `.cnn-confidence-track`, `.cnn-confidence-fill` — skeleton loader & progress bar confidence
- `.skip-link` — accessibility skip navigation
- Keyframes tersedia: `fadeInUp`, `countUp`, `pulseRing`, `gradientShift`, `floatUp`

### Template Blocks
| Block | Fungsi |
|---|---|
| `title` | Judul halaman (ditambah " \| CNN Lhokseumawe") |
| `breadcrumb` | Breadcrumb di topbar |
| `content` | Konten halaman utama |
| `extra_css` | CSS tambahan per halaman |
| `extra_js` | JS tambahan per halaman |

### Components (`app/templates/components/`)
- `page_header.html` — judul halaman. Set `{% set ph_title = 'Judul' %}` sebelum include
- `kpi_card.html` — kartu statistik dashboard
- `status_badge.html` — badge status berwarna
- `table_actions.html` — tombol aksi tabel (edit/hapus)
- `detail_row.html` — baris detail label-value
- `empty_table_row.html` — baris kosong tabel
- `quick_action.html` — tombol aksi cepat

### Sidebar
- Macro `nav_link` pakai Bootstrap Icons (`bi bi-*`)
- Section labels: "Menu Utama" dan "Analisis"
- User footer: avatar + nama + role + logout icon
- Topbar: breadcrumb `{% block breadcrumb %}` + avatar + role badge

### Accessibility
- `skip-link` di atas setiap halaman
- `aria-current="page"` pada link aktif sidebar
- `aria-label` pada semua tombol ikon
- `aria-hidden="true"` pada icon dekoratif
- `scope="col"` pada semua `<th>` tabel
- `prefers-reduced-motion` di CSS

### JavaScript
- `app/static/js/peta.js` — Leaflet.js, fetch GeoJSON, render circle marker warna per tingkat, skeleton loader + error state + retry
- `app/static/js/toast.js` — toast notification dari Flask flash messages
- Inline `<script>` di template untuk logika per-halaman

---

## CNN Integration Point

File: `app/controllers/klasifikasi_controller.py`

```python
def _mock_predict(filepath):
    # GANTI ini dengan inference model CNN nyata
    # Return: (JenisKerusakan object, TingkatKerusakan object, float confidence)
    ...
```

Model harus menerima path absolut file gambar dan mengembalikan tuple `(JenisKerusakan, TingkatKerusakan, confidence_score)`.
Tiga jenis: CRACK / POTHOLE / RUTTING. Tiga tingkat: Berat (id=1) / Sedang (id=2) / Ringan (id=3).

---

## Key Patterns

### Upload Gambar
Disimpan ke `app/static/uploads/foto/` dengan prefix timestamp:
```python
ts = datetime.utcnow().strftime('%Y%m%d%H%M%S%f')
filename = f'{ts}_{secure_filename(original_name)}'
```
`path_file` di database: path relatif `uploads/foto/namafile.jpg`

### SDI Calculation (Bina Marga)
```
SDI = F_retak + F_lubang + F_rutting
F_retak:   0%(→0) | ≤10%(→5) | ≤20%(→20) | >20%(→40)  × 2 jika retak lebar
F_lubang:  0(→0)  | ≤10(→15) | ≤50(→75)  | >50(→225)
F_rutting: 0(→0)  | ≤1cm(→5) | ≤3cm(→20) | >3cm(→40)
Tingkat: SDI≤50=Ringan | 51–150=Sedang | >150=Berat
```
Implementasi: `app/models/label_kerusakan.py::LabelKerusakan.hitung_sdi()`
Auto-estimasi dari dimensi: `LabelKerusakan.estimasi_dari_dimensi(panjang, lebar)`

### Preprocessing Pipeline
Service: `app/services/preprocessing_service.py::PreprocessingService.run_pipeline(img_path, config)`
- Step 1 Resize: Pillow `Image.resize()` dengan metode LANCZOS/BILINEAR/BICUBIC/NEAREST
- Step 2 Center Crop: crop tengah ke dimensi target (crop_width × crop_height), opsional
- Step 3 Normalisasi: numpy — min-max (`÷255`) atau z-score (`(x-µ)/σ`); output disimpan sebagai uint8 [0-255]
- Step 4 Augmentasi: Pillow `ImageOps`, `ImageEnhance` — flip H/V, rotate, brightness, contrast; **setiap transform bersifat random per gambar** (bukan deterministik semua identik)
- Step 5 Denoise: OpenCV `GaussianBlur` / `medianBlur` / `bilateralFilter`
Output: `app/static/uploads/preprocessed/`
Halaman hasil: pagination 24/halaman, modal viewer dengan navigasi prev/next + keyboard (←→Esc), tombol Reset Semua.

**Reset Semua Preprocessing** (`/preprocessing/hasil/reset` POST):
- Menghapus file fisik di `uploads/preprocessed/` + semua record `HasilPreprocessing` di DB
- Sebelumnya hanya hapus DB records — file fisik sekarang ikut dihapus untuk menghindari orphan

### CNN Training Pipeline
Service: `app/services/cnn_service.py`

**`build_model(model_type, input_size, dropout_rate, optimizer_name, learning_rate)`**
- `mobilenetv2`: MobileNetV2(include_top=False, ImageNet) + GlobalAvgPool + Dropout + Dense(3, softmax)
- `efficientnetb0`: EfficientNetB0(include_top=False, ImageNet) + head yang sama
- Augmentasi di dalam model (aktif saat training=True, off saat predict): RandomFlip H+V, RandomRotation(0.25), RandomZoom(0.2), RandomTranslation(0.1,0.1), RandomBrightness(0.3), RandomContrast(0.3)
- Phase 1: base frozen (`training=False`), head trainable

**`train(arsitektur, base_dir, on_epoch_end=None)`**
- Phase 1: frozen base, callbacks: ModelCheckpoint + EarlyStopping(patience=max(user,20), min_delta=0.001) + ReduceLROnPlateau(factor=0.5, patience=10, min_lr=1e-6)
- Phase 2 (fine-tune): unfreeze top 30 layers MobileNetV2 / top 50 EfficientNetB0, lr/5, callbacks serupa
- Hanya simpan Phase 2 jika melampaui best val_accuracy Phase 1, fallback ke Phase 1 jika tidak
- class_weight otomatis dari `compute_class_weight('balanced')` untuk handle imbalance
- Loss: Focal Loss (gamma=2.0)

**`load_dataset(split_config_id, fold_val, input_size, base_dir)`**
- Query `split_item` JOIN `dokumentasi_foto` + outerjoin `hasil_preprocessing` (prioritaskan gambar preprocessed)
- fold==fold_val → val, sisanya → train
- Input: float32 [0,255] → `preprocess_input()` di dalam model yang normalize ke [-1,1]
- Label: `tingkat_kerusakan_id - 1` (Berat=0, Sedang=1, Ringan=2)

**`predict_cv(arsitektur, base_dir)`**
- K-Fold: setiap foto diprediksi oleh model yang di-train tanpa foto tersebut
- Menggunakan preprocessed images (konsisten dengan training)
- Dijalankan sebagai background thread, progress via `_cv_progress`

**`predict_all(arsitektur, base_dir)`**
- Load model `.keras` dari `app/static/models/`
- Prediksi semua foto berlabel dengan koordinat GPS
- Hasil disimpan ke tabel `prediksi_model`

**`evaluate(arsitektur, base_dir)`**
- Load model → predict X_val → sklearn confusion_matrix + classification_report
- Return: `{total_data_val, akurasi, confusion_matrix(JSON), per_class{berat/sedang/ringan}, macro}`

Model tersimpan di: `app/static/models/model_{id}.keras`
Training history per epoch di tabel `hasil_training`.

### Training Flow Otomatis (setelah klik Train)
```
train() → save_model() → evaluate() [auto] → predict_all() [auto]
→ set status='selesai', pred_type='single'
```
Semua berjalan di background thread. Progress dipoll via `/arsitektur/<id>/progress`.

### GIS Prediksi Model (`/arsitektur/<id>/gis`)
- Tampilkan `prediksi_model` di peta Leaflet
- GeoJSON endpoint: `/arsitektur/<id>/gis.json`
- Dua mode prediksi: **Single** (`predict_all`) dan **K-Fold CV** (`predict_cv`)
- `pred_type` di `arsitektur_config`: `none` | `single` | `cv`
- Warna marker: Berat=#E53E3E, Sedang=#F59E0B, Ringan=#10B981

### Stratified K-Fold Split
Service: `app/services/split_service.py::SplitService.run(n_splits, random_state, items)`
- Input: list foto yang punya `LabelKerusakan` (join `DokumentasiFoto → LokasiKerusakan → LabelKerusakan`)
- `StratifiedKFold` dari scikit-learn — shuffle=True, reproducible via random_state
- Hasil disimpan ke `split_item` dengan `fold_index` 0..K-1
- Halaman detail: tabel distribusi kelas per fold + grouped bar chart (Chart.js 4)
- Export CSV: `nama_file, fold_index, tingkat, latitude, longitude`

**Reset Items Split** (`/split/<id>/reset` POST):
- Hapus semua `SplitItem` milik config tanpa menghapus `SplitConfig` itu sendiri
- Reset `total_data = 0` di `SplitConfig`
- **Ditolak** jika ada `ArsitekturConfig` yang merujuk split tersebut (FK constraint)
- Berguna untuk re-split setelah preprocessing ulang

### SQLAlchemy Cascade Note
`ArsitekturConfig.split_config` relationship menggunakan `passive_deletes=True` pada backref. Ini mencegah ORM mencoba SET NULL saat `SplitConfig` dihapus — karena kolom `split_config_id` adalah NOT NULL, ORM tidak boleh issue UPDATE tersebut; biarkan DB yang handle via FK constraint.

### Labeling SDI — Hapus Semua
Route `label.hapus_semua` (`/label/hapus-semua` POST) menghapus semua record `LabelKerusakan`. Tombol "Hapus Semua" di `label/index.html` muncul hanya jika `sudah > 0`, dengan modal konfirmasi Bootstrap custom. Endpoint **bukan** `label.delete_all` — function name `hapus_semua` dipakai untuk menghindari konflik routing.

### Restore Foto Utility
`restore_foto.py` — script standalone untuk memulihkan foto yang terhapus dari `uploads/foto/`:
- Baca `DokumentasiFoto` dari DB, strip 21-char timestamp prefix dari `nama_file`
- Cari file asli di `data/jalan/` (case-insensitive), copy ke `uploads/foto/`
- DB tidak diubah sama sekali

### Coordinate Normalization
Data Excel: integer `97108763` → float `97.108763°`. Deteksi: jika string mengandung `.` → pakai langsung, jika integer besar → bagi 1,000,000.

---

## Configuration (`config.py`)

| Setting | Default | Deskripsi |
|---|---|---|
| `SECRET_KEY` | `cnn-jalan-secret-2024` | Override via env var `SECRET_KEY` |
| `SQLALCHEMY_DATABASE_URI` | `mysql+pymysql://root:@localhost/db_cnn_jalan` | Override via env var `DATABASE_URL` |
| `UPLOAD_FOLDER` | `app/static/uploads/foto` | Folder foto asli |
| `MAX_CONTENT_LENGTH` | 16 MB | Batas ukuran upload |
| `ALLOWED_EXTENSIONS` | `{png, jpg, jpeg, webp}` | Ekstensi yang diizinkan |

---

## Migration Files

Jalankan **berurutan** pada fresh install (setelah `db_cnn_jalan.sql`):

| File | Fungsi | Status |
|---|---|---|
| `db_cnn_jalan.sql` | Schema lengkap (fresh install) | — |
| `migrate_remove_kecamatan.sql` | Hapus tabel & kolom kecamatan | Sudah dijalankan |
| `migrate_add_preprocessing.sql` | Tambah tabel preprocessing_config & hasil_preprocessing | Sudah dijalankan |
| `migrate_add_split.sql` | Tambah tabel split_config & split_item + indexes | Sudah dijalankan |
| `migrate_add_arsitektur.sql` | Tambah tabel arsitektur_config & hasil_training | Sudah dijalankan |
| `migrate_add_hasil_evaluasi.sql` | Tambah tabel hasil_evaluasi (FK arsitektur_config) | Sudah dijalankan |
| `migrate_add_patience.sql` | Tambah kolom `patience` di arsitektur_config | Sudah dijalankan |
| `migrate_add_prediksi_model.sql` | Tambah tabel prediksi_model (arsitektur_id, dok_id, prediksi, aktual, confidence) | Sudah dijalankan |
| `migrate_add_pred_type.sql` | Tambah kolom `pred_type` VARCHAR(10) di arsitektur_config (none/single/cv) | Sudah dijalankan |
| `seed_data.py` | Import 280 data dari Excel + copy gambar ke uploads/foto/ | Sudah dijalankan |
