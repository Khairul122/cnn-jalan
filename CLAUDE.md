# CLAUDE.md

Panduan ini menjelaskan project CNN-Jalan kepada Claude Code saat bekerja di repository ini.
UI dan konten database dalam Bahasa Indonesia.

## Project Overview

**CNN-Jalan** adalah aplikasi web GIS berbasis Flask untuk pemetaan kerusakan jalan di Kota Lhokseumawe, Aceh, Indonesia. Dikembangkan sebagai bagian dari skripsi (NIM 210170072).

**Tujuan utama:**
- Klasifikasi foto kerusakan jalan menggunakan CNN: **tingkat kerusakan** 4 kelas SDI Bina Marga: Rusak Berat / Rusak Ringan / Sedang / Baik (sejak 2026-09-24; definisi tunggal di `app/kelas.py`) (jenis CRACK/POTHOLE/RUTTING tidak diklasifikasi; tabel `jenis_kerusakan` tidak dipakai)
- Labeling SDI (Surface Distress Index) — standar Bina Marga
- Preprocessing pipeline gambar (Resize → Center Crop → Normalisasi → Denoise; augmentasi hanya di model saat training)
- Split dataset Stratified K-Fold untuk persiapan training CNN
- Visualisasi GIS interaktif dengan Leaflet.js

**Dataset:** 280 foto kerusakan jalan + `data/DATA JALAN REVISI.xlsx` (koordinat GPS, P/L dalam meter, keterangan Ukur/Estimasi). Foto asli di `data/jalan/`. Import ulang: `python scripts/seed_data.py --reset`.

---

## Setup & Running

```powershell
# Buat dan aktifkan virtual environment
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt

# Database: Postgres (Supabase). Isi DATABASE_URL di .env (Session pooler), lalu buat skema + data master + RLS:
$env:FLASK_APP = "run.py"
.\.venv\Scripts\python.exe -m flask db upgrade

# Pindahkan data dari MySQL lama (sekali jalan; --ganti mengosongkan tabel tujuan dulu):
.\.venv\Scripts\python.exe scripts\migrate_mysql_to_supabase.py --sumber "mysql+pymysql://root:PWD@localhost/db_cnn_jalan" --ganti

# Tes memakai database terpisah bila TEST_DATABASE_URL diset (jangan arahkan ke database utama):
# $env:TEST_DATABASE_URL = "postgresql+psycopg2://postgres:@127.0.0.1:5432/cnn_jalan_test"

# Jalankan server development — WAJIB pakai venv python
.\.venv\Scripts\python.exe run.py
```

Akses di: **http://127.0.0.1:5000**

**Akun default:** `admin@gmail.com` / `12345678` — **ganti** dengan `python scripts/create_admin.py --email admin@gmail.com`. Pendaftaran publik hanya membuat akun `viewer`; hanya `admin` yang boleh mengubah data (`app/auth_utils.py::admin_required`). Semua form POST memakai token CSRF (`{{ csrf_token() }}`), logout lewat POST.

**Konfigurasi:** salin `.env.example` → `.env`, isi `SECRET_KEY` (acak), `DATABASE_URL` (Postgres/Supabase, Session pooler), dan `FLASK_DEBUG` (1 hanya untuk dev lokal). `config.py` menolak start jika `SECRET_KEY`/`DATABASE_URL` belum diset.

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

Database: Postgres (Supabase). Skema dikelola Alembic (`migrations/`, `flask db upgrade`); semua tabel `ENABLE ROW LEVEL SECURITY` tanpa policy (aplikasi memakai role pemilik). Kolom enum disimpan sebagai VARCHAR (`native_enum=False`).

| Tabel | Deskripsi |
|---|---|
| `pengguna` | Akun user (role: admin/viewer), password bcrypt |
| `jenis_kerusakan` | Master jenis: CRACK, POTHOLE, RUTTING |
| `tingkat_kerusakan` | Master tingkat: Rusak Berat (id=1), Rusak Ringan (id=2), Sedang (id=3), Baik (id=4); indeks kelas CNN = id − 1 |
| `lokasi_kerusakan` | Data lokasi GPS + dimensi kerusakan (`panjang`, `lebar` DECIMAL meter) + `keterangan` (`Ukur` / `Estimasi (Ringan\|Sedang\|Berat)`) |
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
- `lokasi_kerusakan` â† `dokumentasi_foto` â† `hasil_klasifikasi_cnn`
- `lokasi_kerusakan` â† `label_kerusakan` → `tingkat_kerusakan`
- `dokumentasi_foto` â† `hasil_preprocessing` → `preprocessing_config`
- `split_config` â† `split_item` → `dokumentasi_foto`
- `split_item` → `tingkat_kerusakan` (label kelas untuk stratifikasi)
- `arsitektur_config` → `split_config` (data yang dipakai training)
- `arsitektur_config` â† `hasil_training` (riwayat epoch)
- `arsitektur_config` â† `hasil_evaluasi` (confusion matrix + metrik evaluasi otomatis)
- `arsitektur_config` â† `prediksi_model` → `dokumentasi_foto` (hasil prediksi per foto untuk GIS)

---

## Features & Progress

| Fitur | Status | Blueprint | Catatan |
|---|---|---|---|
| Auth (login/register) | Selesai | `auth` | Flask-Login, Werkzeug bcrypt |
| Dashboard | Selesai | `dashboard` | KPI cards, statistik realtime |
| Lokasi Kerusakan | Selesai | `lokasi` | CRUD, mini-map Leaflet di halaman detail |
| Klasifikasi CNN | Selesai | `klasifikasi` | Inferensi nyata memakai model terbaik (macro-F1 evaluasi tertinggi); tanpa model terlatih, upload ditolak. Hanya memprediksi tingkat, jenis dikosongkan |
| Labeling SDI | Selesai | `label` | Auto-label dari P×L, kalkulasi real-time AJAX |
| Preprocessing | Selesai | `preprocessing` | Pipeline 4 tahap (Resize → Center Crop → Normalisasi → Denoise), OpenCV + Pillow, pagination, modal viewer |
| Split Data | Selesai | `split` | Stratified K-Fold (scikit-learn), distribusi tabel + Chart.js, export CSV |
| Arsitektur CNN | Selesai | `arsitektur` | MobileNetV2 & EfficientNetB0, transfer learning, background training, live progress, loss/acc chart |
| Evaluasi Hasil CNN | Selesai | `arsitektur` | Evaluasi otomatis dari val fold — confusion matrix 4×4, per-class precision/recall/F1, macro avg |
| Prediksi GIS (Single) | Selesai | `arsitektur` | `predict_all()` → simpan ke `prediksi_model`, tampil di peta `/arsitektur/<id>/gis` |
| Prediksi GIS (K-Fold CV) | Selesai | `arsitektur` | `predict_cv()` background thread, live progress, tiap foto diprediksi model yang tidak melihatnya |
| Peta GIS | Selesai | `peta` | Leaflet.js, GeoJSON endpoint, filter status |
| Evaluasi Model (Manual) | Selesai | `evaluasi` | Input manual metrik, tabel perbandingan |
| UI Modernisasi | Selesai | Semua | Split-screen auth, animated KPI, modern table, dropzone, civic govtech design |

---

## Status Akurasi CNN (per 2026-09-24)

**Belum ada metrik resmi untuk skema 4 kelas.** Pada 2026-09-24 skema label pindah dari 3 kelas ke 4 kelas
(lihat "SDI Calculation"), formula estimasi SDI diganti, dan seluruh data turunan (split, arsitektur, training,
prediksi, model `.keras`) dihapus karena tidak lagi sahih. Cadangan ada di `backup_3kelas_20260924/`.
Langkah berikutnya: split baru → training → Prediksi CV K-Fold → catat angka pertama di sini.

**Angka lama (skema 3 kelas, TIDAK sebanding dengan skema 4 kelas, hanya arsip):**
5-fold CV MobileNetV2, akurasi 47,1% ± 6,1, macro-F1 45,8% (`arsitektur_id=279`, run 2026-09-24). Catatan: run ini
memakai label formula diskrit lama, sedangkan DB saat itu ternyata sudah berisi label formula kontinu
(Berat 153 / Sedang 97 / Ringan 30), jadi baseline mayoritas sebenarnya 54,6% dan bukan 50,4%. Angka 48,9% (sebelum
2026-09-23) tidak valid karena `predict_cv()` crash diam-diam (`NameError`).

**Baseline yang harus dikalahkan (skema 4 kelas, label 2026-09-24):** distribusi Rusak Berat 40 / Rusak Ringan 37 /
Sedang 74 / Baik 129 dari 280 foto → kelas mayoritas (Baik) 46,1%.

**Target 70% belum tercapai dan kemungkinan tidak tercapai dari foto saja** — lihat "Catatan Kejujuran Akademik" di
`TODO.md`. Kelas ditentukan luas kerusakan (tidak tampak di foto tanpa skala).

**Catatan metodologi terbaru:**

| Area | Status terbaru |
|---|---|
| Label utama | SDI 4 kelas dari `estimasi_dari_dimensi` (model segmen 100 m, diputuskan 2026-09-24); sudah di-apply ke DB. Tidak ada run CV yang memakai label ini. |
| Evaluasi utama | 5-fold CV; mode Single hanya visualisasi karena memprediksi foto latih |
| Model final | Dilatih pada 100% data setelah CV (`models/model_279_final.keras`); akurasinya tidak dilaporkan sebagai metrik uji |
| Augmentasi | Layer Keras di dalam model (termasuk color jitter/noise/cutout baru 2026-09-24); aktif hanya saat training |
| Hiperparameter | Satu sumber `cnn_service.hyperparams()` untuk snapshot controller, `predict_cv`, `train_final` (bug 2026-09-24: `predict_cv` dulu mengabaikan mixup/smoothing/dense/Jalur A) |
| Head model | `GAP → Dropout(d) → Dense(64, relu, L2) → Dropout(d/2) → Dense(4, softmax, L2)` |

**Target akurasi: 70% (belum tercapai)**
**Setting yang dipakai run 2026-09-24 (dan disarankan untuk run berikutnya):**
- Epochs: 80 (max; early stopping patience 20 biasanya berhenti lebih awal)
- Learning Rate: `0.0001` (`0.001` **salah** — berisiko class collapse ke kelas mayoritas)
- Batch Size: 32
- Dropout: 0.3
- Fine-tune: unfreeze 8 layer (MobileNetV2) / 12 layer (EfficientNetB0), lr/10
- Mixup: nonaktif (`mixup_alpha=0`, baru tersedia 2026-09-24, belum divalidasi lewat CV)

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

File: `app/controllers/klasifikasi_controller.py` memanggil `cnn_service.best_model()` lalu
`cnn_service.predict_image(arsitektur, path, base_dir, prep_config)` → `(kelas 0..2, confidence 0..1)`. Foto baru
diproses dengan pipeline preprocessing default (hasil tahap denoise) agar sama dengan data training. Kelas 0/1/2/3 =
Rusak Berat (id 1) / Rusak Ringan (id 2) / Sedang (id 3) / Baik (id 4).

**`best_model()`** (direvisi 2026-09-23): utamakan `ArsitekturConfig` yang sudah `pred_type='cv'` dengan
`cv_summary().macro_f1` tertinggi (metrik resmi, rata-rata 5 fold) — fallback ke `HasilEvaluasi.macro_f1` (1 fold)
kalau belum ada config yang di-CV sama sekali.

**Ensemble + TTA** (baru 2026-09-23, lihat [[cnn-ensemble-tta]]): `predict_cv()` sekarang menyimpan model TIAP fold
(`model_{id}_fold{k}.keras`, lewat `save_model`), bukan cuma dipakai sekali lalu dibuang. `predict_image()`/`predict_all()`
lewat `_resolve_prediction_models()` otomatis pakai SEMUA model fold sebagai ensemble (rata-rata probabilitas) kalau
sudah tersedia dari CV terakhir — fallback ke 1 model (final/fold tunggal) kalau belum pernah CV. Tiap model (baik
ensemble maupun tunggal) diprediksi dengan **TTA sederhana** (`_predict_with_tta`): rata-rata probabilitas gambar asli
+ flip horizontal. Model fold lama dihapus otomatis (`arsitektur_controller._remove_fold_models`) saat re-train atau
hapus config, supaya ensemble tidak diam-diam pakai model basi dari split/data sebelumnya.

Prediksi dengan confidence < `AMBANG_CONFIDENCE` (0,5, `klasifikasi_controller.py`) ditandai `is_valid=False` ("Perlu verifikasi manual").

Model **tidak** memprediksi jenis kerusakan (CRACK/POTHOLE/RUTTING); `hasil_klasifikasi_cnn.jenis_kerusakan_id` NULL
(`migrate_klasifikasi_jenis_nullable.sql`). Upload divalidasi oleh `app/uploads.py` (ekstensi + isi harus gambar).

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
F_retak:   0%(→0) | ≤10%(→5) | ≤30%(→20) | >30%(→40)  × 2 jika retak lebar
F_lubang:  0(→0)  | ≤10(→15) | ≤50(→75)  | >50(→225)
F_rutting: 0(→0)  | ≤1cm(→2,5) | ≤3cm(→10) | >3cm(→20)
Tingkat (4 kelas): SDI<50=Baik(4) | 50–100=Sedang(3) | 100–150=Rusak Ringan(2) | >150=Rusak Berat(1)
```
Diperbaiki 2026-09-24 (P0 TODO.md): F_rutting sebelumnya 5/20/40 (2× lipat standar) dan breakpoint F_retak tengah
20% (standar 30%). Verifikasi standar: UNILA, UNUD, japendi, FT UMI (lihat TODO.md). Bina Marga menghitung jumlah lubang
dan % retak per segmen 100 m.
Implementasi: `app/models/label_kerusakan.py::LabelKerusakan.hitung_sdi()`; salinan JS ada di `label/edit.html` (ubah
bersamaan).
Auto-estimasi dari dimensi (meter): `LabelKerusakan.estimasi_dari_dimensi(panjang, lebar)` (model diganti 2026-09-24):
```
luas              = panjang × lebar
persen_retak      = min(luas / SEGMEN_M2 × 100, 100)   # SEGMEN_M2 = 700 (100 m × 7 m)
jumlah_lubang     = min(luas / LUBANG_M2, 999)          # LUBANG_M2 = 0,5 m² per lubang
kedalaman_rutting = min(luas / 4.0, 5.0)  cm            # REF_RUTTING = 4.0
jenis_retak       = 'lebar' kalau luas > 2.0 m², selain itu 'halus'
```
SEGMEN_M2, LUBANG_M2, REF_RUTTING, AMBANG_LEBAR adalah **asumsi kalibrasi**, bukan hasil ukur dan bukan nilai baku:
dataset tidak punya jumlah lubang maupun kedalaman rutting, keduanya proksi dari luas. Akibatnya kelas Rusak
Ringan/Rusak Berat praktis hanya tercapai lewat F_lubang, yaitu ditentukan luas. Wajib disebut di bab metodologi.
Validasi silang tidak dipakai untuk menyetel konstanta: baris surveyor `Estimasi (Ringan)` 76/76 jatuh ke Baik,
`Estimasi (Berat)` 2/2 ke Rusak Berat, `Estimasi (Sedang)` 47 Sedang / 16 Rusak Ringan / 6 Baik.
Model lama (`luas/0,1` lubang, `luas/1,0` % retak) membuat luas > 5 m² otomatis SDI > 150 (Berat 55%) dan tidak
sejalan dengan penilaian surveyor.

**Temuan data terpisah (audit 2026-09-23):** 4 baris `lokasi_kerusakan` (id 123/125/126/127, semua `keterangan='Ukur'`)
punya `panjang` dalam ribuan meter (1000–8000 m) dengan `lebar` konstan 10 m — luas 10.000–80.000 m², jauh di luar
kisaran 276 baris lain (0,15–300 m²). Kemungkinan ini data segmen jalan (bukan patch kerusakan titik) atau salah unit
saat entry Excel. Formula SDI (lama maupun baru) tetap aman secara numerik karena semua parameter jenuh (capped), tapi
nilai `panjang`/`lebar` mentahnya sendiri layak diverifikasi manual ke `data/DATA JALAN REVISI.xlsx` — belum diperbaiki,
di luar cakupan P0/P1 saat ini.

**Sumber kelas (Auto-label):** semua dari SDI hasil estimasi P×L (keputusan pemilik, 2026-09-22). Kolom `keterangan`
(`Ukur` / `Estimasi (X)`) hanya disimpan sebagai informasi, tidak memengaruhi kelas (dipakai hanya sebagai validasi silang, lihat di atas).
Catatan untuk bab pembahasan: kelas dari P×L tidak tampak di foto (tanpa skala), sehingga akurasi CNN cenderung mendekati
baseline kelas mayoritas (uji 5-fold fitur beku: ~46–52% vs baseline 50,4%). Sebagai pembanding, kelas dari penilaian
surveyor (`Ket` untuk baris Estimasi) memberi macro-F1 lebih tinggi (~56–61%).

### Preprocessing Pipeline
**Satu config aktif global (2026-09-24):** `hasil_preprocessing` hanya berisi satu config. Menjalankan preprocessing
(`/preprocessing/run/<id>`) mengganti semua hasil sebelumnya (file + record); config yang sudah punya hasil tidak bisa
diedit sebelum hasilnya di-reset; menghapus config ikut menghapus file hasilnya. `PreprocessingConfig.aktif()` = config
dari hasil terbaru, dipakai klasifikasi foto baru supaya sama dengan data training. Training ditolak bila ada foto split
tanpa hasil denoise (`cnn_service.foto_tanpa_preprocessing`). Model tidak mencatat config-nya: setelah ganti config,
latih ulang model. Default config baru: resize 256×256 → center crop 224×224, norm `none`, denoise bilateral k=3
(semua foto 4:3, stretch menekan lebar ±25%). Config: baseline, `ablation A: tanpa denoise`, `ablation B: CLAHE`.
Service: `app/services/preprocessing_service.py::PreprocessingService.run_pipeline(img_path, config)`
- Step 1 Resize: Pillow `Image.resize()` dengan metode LANCZOS/BILINEAR/BICUBIC/NEAREST. `resize_mode` (baru 2026-09-23):
  `stretch` (default, resize langsung ke target — bisa distorsi) atau `letterbox` (jaga aspect ratio, resize masuk ke
  dalam target box lalu pad hitam di sisa ruang) — pilih di `preprocessing_config.resize_mode` saat buat/edit config.
  **Koreksi iluminasi** (toggle `illum_correction`, baru 2026-09-23): gray-world white balance diterapkan SEBELUM
  resize kalau aktif (`PreprocessingService._gray_world_white_balance` — skalakan tiap kanal RGB supaya mean-nya sama
  dengan mean abu-abu keseluruhan gambar), mengurangi variasi warna akibat pencahayaan beda antar sesi pemotretan.
- Step 2 Center Crop: crop tengah ke dimensi target (crop_width × crop_height), opsional. ROI-aware crop (anotasi bbox
  manual per foto) diusulkan di TODO.md P2 tapi **diskip** — belum ada anotasi bounding box untuk 280 foto.
- Step 3 Normalisasi: `minmax` (÷255), `zscore` ((x-µ)/σ), atau `clahe` (baru 2026-09-23 — Contrast Limited Adaptive
  Histogram Equalization di kanal L color space LAB, `clipLimit=2.0`, `tileGridSize=(8,8)`, kontras lokal naik tanpa
  merusak kontras absolut antar foto seperti minmax/zscore global); output disimpan sebagai uint8 [0-255]
- Step 4 Denoise (keluarannya yang dipakai training): OpenCV `GaussianBlur` / `medianBlur` / `bilateralFilter`. Default
  skema (config baru) diganti 2026-09-23 dari `none` ke `bilateral` k=3 (pertahankan tepi retak, redam noise area datar)
  — config yang dipakai training saat ini sudah `bilateral` k=3 sebelum perubahan ini. Ablation "tanpa denoise sama
  sekali" vs bilateral BELUM dijalankan (TODO.md P2, perlu training run baru).
**Augmentasi tidak ada di preprocessing** (tahap dihapus 2026-09-24, `migrate_p2_augmentasi.sql`): augmentasi training = 10 layer Keras di dalam model (`model.py::_augmentation_layers`), acak ulang tiap epoch, mati saat predict; tiap layer bisa dimatikan lewat `arsitektur_config.aug_off` (form Arsitektur) untuk ablation. Mixup dan label smoothing (opsional, default 0/nonaktif) memakai loss `CategoricalCrossentropy` dan label one-hot; Mixup butuh data fit ≥ `batch_size`.
Output: `app/static/uploads/preprocessed/`
Halaman hasil: pagination 24/halaman, modal viewer dengan navigasi prev/next + keyboard (â†→Esc), tombol Reset Semua.

**Reset Semua Preprocessing** (`/preprocessing/hasil/reset` POST):
- Menghapus file fisik di `uploads/preprocessed/` + semua record `HasilPreprocessing` di DB
- Sebelumnya hanya hapus DB records — file fisik sekarang ikut dihapus untuk menghindari orphan

### CNN Training Pipeline
Service: `app/services/cnn_service/` (dipecah dari 1 file jadi package 2026-09-23 — struktur folder,
bukan perubahan perilaku). Pemanggil lain tetap `from app.services import cnn_service` lalu
`cnn_service.<nama>`, tidak ada yang perlu berubah kecuali tes yang me-`mock.patch.object` konstanta/
helper (harus patch di submodule tempat didefinisikan, mis. `cnn_service.dataset.MIN_TRAIN_SAMPLES`,
`cnn_service.prediction._load_cached`).

| File | Isi |
|---|---|
| `dataset.py` | `load_dataset`, ekspansi tahap training, dedup konten, `_group_aware_split` |
| `model.py` | `build_model`, `_apply_fine_tuning` (arsitektur Keras) |
| `training.py` | `train`, `train_final`, `_fit_phase`, `_is_better_checkpoint`, `save_model` |
| `evaluation.py` | `evaluate` (1 fold — bukan metrik resmi) |
| `prediction.py` | `predict_cv`, `predict_all`, `predict_image`, `best_model`, ensemble+TTA |

**`build_model(model_type, input_size, dropout_rate, optimizer_name, learning_rate)`**
- `mobilenetv2`: MobileNetV2(include_top=False, ImageNet) + GlobalAvgPool + Dropout + Dense(4, softmax)
- `efficientnetb0`: EfficientNetB0(include_top=False, ImageNet) + head yang sama
- Augmentasi di dalam model (aktif saat training=True, off saat predict): RandomFlip H+V, RandomRotation(0.25), RandomZoom(0.2), RandomTranslation(0.1,0.1), RandomBrightness(0.3), RandomContrast(0.3)
- Phase 1: base frozen (`training=False`), head trainable

**`train(arsitektur, base_dir, on_epoch_end=None)`** (kriteria checkpoint direvisi 2026-09-22, lihat [[cnn-checkpoint-selection]])
- **Inner-val**: 15% data training (stratified **di level foto**, lihat `_group_aware_split`) dipisah untuk early stopping. Fold uji **tidak pernah** dipakai untuk memutuskan apa pun (early stopping, LR, pilihan epoch/fase) — hanya dievaluasi tiap epoch untuk grafik/log (`uji_loss`, `uji_acc`)
- Phase 1: frozen base, EarlyStopping(monitor=inner val_loss, patience=max(user,20), min_delta=0.001) + ReduceLROnPlateau(factor=0.5, patience=patience//2, min_lr=1e-6) — val_loss dipantau untuk KONTROL training (kapan berhenti/turunkan LR) saja
- **Pemilihan bobot terbaik** (`_fit_phase`, `_is_better_checkpoint`): pakai **BALANCED accuracy inner-val** (rata-rata recall antar kelas via `sklearn.metrics.balanced_accuracy_score`, dihitung tiap epoch dari prediksi `X_inner`), bukan val_loss/akurasi mentah — root-cause dari log training menunjukkan val_loss bisa terus turun (model makin percaya diri) tanpa akurasi ikut membaik, dan akurasi mentah bias ke kelas mayoritas (Sedang). val_loss cuma jadi tiebreaker saat balanced accuracy sama persis. Bobot disimpan di memori, tanpa file sementara
- Phase 2 (fine-tune): unfreeze top 8 layers MobileNetV2 / top 12 EfficientNetB0 (BatchNorm tetap frozen, diperketat dari
  15/25 layer — dataset kecil rawan overfit di fine-tune), lr/10 (diperketat dari lr/5), callback serupa (patience
  max(10, patience//2))
- Phase 2 dipakai hanya jika `_is_better_checkpoint` bilang balanced accuracy-nya lebih baik dari Phase 1, jika tidak kembali ke bobot Phase 1
- class_weight dari `compute_class_weight('balanced')` atas data fit (tanpa inner-val). **Sempat dicoba** boost tambahan ×1.5 khusus Ringan (2026-09-22) untuk atasi recall Ringan rendah, tapi **dibatalkan** (2026-09-23) — terbukti overcorrect: rasio Ringan:Sedang jadi 3,5x, model ganti bias ke Ringan/Berat dan recall Sedang anjlok (23%), macro-F1 malah turun dibanding tanpa boost. Kembali ke `balanced` polos
- Loss: `SparseCategoricalCrossentropy`; seed tetap (`SEED = 42`) agar hasil bisa direproduksi
- Grafik/`hasil_training.val_*` = fold uji per epoch; jangan baca "val acc terbaik" sebagai estimasi generalisasi — pakai `hasil_evaluasi` (model final) atau prediksi CV

**`load_dataset(split_config_id, fold_val, input_size, base_dir)`** (keputusan terakhir 2026-09-23, riwayat di [[cnn-training-data-expansion]])
- Query `split_item` JOIN `dokumentasi_foto`; fold==fold_val → val, sisanya → train
- **Training**: diperluas — setiap tahap non-acak yang tersedia per foto (`TRAIN_EXPAND_STEPS` = resize, crop, normalisasi, denoise) dipakai sebagai sampel terpisah dengan label yang sama. `augmentasi` dikecualikan (acak, tidak reproducible). Foto tanpa preprocessing fallback ke 1 sampel original
- **Dedup konten** (`distinct_stage_paths`, hash MD5 per file): tahap yang hasilnya identik byte-per-byte dengan tahap lain di foto yang sama (mis. `crop` == `resize` saat `preprocessing_config.crop_enabled=False`) **tidak** dihitung dua kali. `split_controller._expanded_sample_count` (statistik UI "Sampel Training Efektif") memakai `cnn_service.effective_sample_count` yang sama
- **Validasi/fold uji: 1 gambar per foto** (utamakan tahap denoise, fallback original) — **SAMA** seperti `predict_all`/`predict_cv`/klasifikasi foto baru. **Riwayat:** sempat dicoba ikut diperluas (2026-09-22) supaya "konsisten" dengan training, tapi **dibatalkan (2026-09-23)** setelah audit menemukan itu membuat `evaluate()`/`HasilEvaluasi` ("Akurasi Model Final") mengukur sampel yang saling berkorelasi (beberapa versi dari foto yang sama, bukan titik data independen) — tidak lagi sebanding dengan `cv_summary()`/`predict_cv` yang selalu 1 gambar/foto, dan bikin angka akurasi antar-run lebih berisik tanpa manfaat nyata
- Return: `(X_train, y_train, groups_train, X_val, y_val, groups_val)` — `groups_train` = `dokumentasi_id` per sampel training, dipakai `_group_aware_split` di `train()` supaya varian tahap dari foto yang sama tidak terpisah antara data fit dan inner-val (cegah leakage sampel nyaris-identik). `groups_val` isinya 1:1 dengan `y_val` (tidak dipakai untuk apa pun khusus, sekadar konsisten)
- Input: float32 [0,255] → `preprocess_input()` di dalam model yang normalize ke [-1,1]
- Label: `tingkat_kerusakan_id - 1` (Rusak Berat=0, Rusak Ringan=1, Sedang=2, Baik=3)
- **PENTING (audit metodologi 2026-09-23):** `HasilEvaluasi`/"Akurasi Model Final" di halaman detail arsitektur adalah metrik **1 FOLD SAJA**, BUKAN metrik CV resmi. Metrik yang boleh dilaporkan (lihat bagian "Evaluasi, Pipeline Ulang, dan Tes") adalah `cv_summary()` (`pred_type='cv'`, hasil "Prediksi CV K-Fold"). **Bug ditemukan & diperbaiki 2026-09-23:** `predict_cv()` selalu crash (`NameError: SimpleNamespace` tidak di-import) sejak awal project — errornya senyap (langsung ke-`pop()` sebelum sempat tampil), jadi `pred_type` tidak pernah `'cv'` sampai bug ini ditemukan. Angka resmi TERKINI ada di "Status Akurasi CNN" di atas (47,1% ± 6,1, 2026-09-24) — jangan pakai 45,4% (run 2026-09-23) sebagai acuan lagi, itu sudah digantikan setelah fine-tune diperketat & split jadi near-dup-aware (riwayat lengkap ada di bagian atas). Jangan bandingkan angka `HasilEvaluasi.akurasi` (1 fold) antar-run sebagai indikator naik/turun — variansnya besar

**`predict_cv(arsitektur, base_dir)`**
- K-Fold: setiap foto diprediksi oleh model yang di-train tanpa foto tersebut, dengan TTA (`_predict_with_tta`)
- Menggunakan preprocessed images tahap `denoise` (1 gambar/foto, konsisten dengan inferensi nyata) — tidak memakai ekspansi multi-tahap `load_dataset`
- **Menyimpan model tiap fold** (`model_{id}_fold{k}.keras`, baru 2026-09-23) — dipakai `_resolve_prediction_models` sebagai ensemble saat klasifikasi foto baru, bukan cuma untuk prediksi fold itu sendiri lalu dibuang
- Dijalankan sebagai background thread, progress via `_cv_progress`

**`predict_all(arsitektur, base_dir)`**
- Pakai `_resolve_prediction_models()` (ensemble fold CV + TTA kalau tersedia, fallback 1 model) — lihat bagian "CNN Integration Point"
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
- Warna marker: Rusak Berat=#E53E3E, Rusak Ringan=#F97316, Sedang=#F59E0B, Baik=#10B981 (`app/kelas.py`)

### Stratified K-Fold Split
Service: `app/services/split_service.py::SplitService.run(n_splits, random_state, items, groups=None)`
- Input: list foto yang punya `LabelKerusakan` (join `DokumentasiFoto → LokasiKerusakan → LabelKerusakan`)
- `StratifiedKFold` dari scikit-learn — shuffle=True, reproducible via random_state
- Hasil disimpan ke `split_item` dengan `fold_index` 0..K-1
- **Near-duplicate grouping** (baru 2026-09-23, lihat [[near-duplicate-split-grouping]]): `split_controller.new()`
  memanggil `dedup_service.find_duplicate_groups()` (average-hash 64-bit + union-find, tanpa dependency baru) atas
  SEMUA foto berlabel sebelum split — foto yang jaraknya ≤5 bit dianggap near-duplicate dan dipaksa satu `group_id`.
  `SplitService.run` otomatis pakai `StratifiedGroupKFold` (bukan `StratifiedKFold` polos) kalau ada grup berisi
  >1 foto, supaya foto near-identik tidak pernah kebagian fold berbeda (cegah leakage train/val). Kalau tidak ada
  duplikat terdeteksi, perilakunya identik dengan `StratifiedKFold` sebelumnya. User diberi tahu lewat flash message
  jumlah foto yang dikelompokkan. Di dataset 280 foto saat ini: **31 foto terdeteksi near-duplicate.**
- **Grup spasial + Repeated K-Fold (2026-09-24):** `radius_grup_m` (default 50 m, 0 = off) menggabungkan foto berjarak ≤ radius (haversine, single linkage) dengan grup near-duplicate; radius yang membuat grup lebih besar dari satu fold ditolak. Form punya "Jumlah ulangan" (1–5, seed berurutan). Ringkasan hasil ulangan: `/arsitektur/ringkasan-ulangan` (`metrics_service.cv_ulangan`, std antar-run).
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

### Cek Kebersihan Data (Cleaning Audit)
`scripts/check_data_quality.py` (baru 2026-09-23) — scan read-only semua `DokumentasiFoto`: file hilang/0 byte/korup,
resolusi < `--min-resolution` (default 64px), dan duplikat persis (MD5). **Tidak menghapus apa pun** — cuma cetak
laporan; keputusan hapus/tidak tetap manual. Jalankan: `.\.venv\Scripts\python.exe scripts\check_data_quality.py`

### Import Data (Excel → DB)
`scripts/seed_data.py` — kolom Excel: `Citra, x (lat), y (lon), P, L, Ket`. Semua nilai numerik (meter, derajat desimal), divalidasi sebelum ada yang dihapus.
- `--reset`: TRUNCATE tabel data model (lokasi, foto, label, preprocessing, split, arsitektur, training, evaluasi, prediksi) + hapus `uploads/foto`, `uploads/preprocessed`, `models/*.keras`
- Tabel master (`pengguna`, `jenis/tingkat_kerusakan`, `preprocessing_config`, `evaluasi_model`) tidak disentuh
- Setelah import: jalankan ulang Auto-label SDI → Preprocessing → Split → Training

---

## Configuration (`config.py`)

| Setting | Default | Deskripsi |
|---|---|---|
| `SECRET_KEY` | (wajib, dari `.env`) | Tidak ada default |
| `SQLALCHEMY_DATABASE_URI` | (wajib, dari `.env`) | Env var `DATABASE_URL` |
| `UPLOAD_FOLDER` | `app/static/uploads/foto` | Folder foto asli |
| `MAX_CONTENT_LENGTH` | 16 MB | Batas ukuran upload |
| `ALLOWED_EXTENSIONS` | `{png, jpg, jpeg, webp}` | Ekstensi yang diizinkan |

---

## Migration Files

Sejak 2026-09-24 basis data Postgres (Supabase) dengan Alembic: `migrations/versions/` (satu revisi awal = skema + data master 4 kelas +
RLS). Perubahan skema berikutnya: `flask db migrate -m "..."` lalu `flask db upgrade`. File `migrate_*.sql` lama (dialek MySQL) diarsipkan di
`scripts/legacy_mysql/` dan tidak boleh dijalankan; datanya dipindahkan dengan `scripts/migrate_mysql_to_supabase.py`.

## Evaluasi, Pipeline Ulang, dan Tes

- **Metrik yang boleh dilaporkan (juga precision/F1 per kelas, pola kesalahan ordinal, cross-entropy dari `prediksi_model.probabilitas`):** hasil K-Fold CV (`app/services/metrics_service.py::cv_summary`, tampil di halaman detail & GIS
  setelah "Prediksi CV K-Fold"): akurasi ± std antar fold, macro-F1, recall per kelas, dan baseline kelas mayoritas.
  Prediksi mode *Single* ikut memprediksi foto latih, jadi hanya untuk visualisasi (halaman GIS memberi peringatan).
- **Split basi:** `split_service.jumlah_label_basi(config_id)` menghitung item split yang kelasnya beda dengan label sekarang.
  Training ditolak sampai split dibuat ulang; banner tampil di halaman split dan arsitektur.
- **Start ganda:** status `training` diklaim atomik di `arsitektur.train`; saat `run.py` start, status `training` yang
  tersisa ditandai `gagal` (`tandai_training_terputus`).
- **Model final:** setelah CV, tombol "Latih Model Final" (halaman detail arsitektur) melatih satu model pada 100% data
  (`cnn_service.train_final`, early stopping tetap memakai inner-val) → `arsitektur_config.final_model_path`. Klasifikasi foto baru
  memakai model final bila ada. **Akurasi tidak dihitung dari model final** (tidak ada data uji tersisa); laporkan hasil K-Fold CV.
- **Ulang pipeline sekali jalan:** `python scripts/run_pipeline.py` (Auto-label → Preprocessing → Split → Training → CV → Model final);
  opsi `--skip-preprocessing`, `--no-cv`, `--no-final`, `--epochs`, `--fold`, dll. (`--help`).
- **Tes:** `python -m unittest discover -s tests -t . -v` (memakai DB dev; data uji sementara dibersihkan otomatis).




