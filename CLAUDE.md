# CLAUDE.md

Panduan ini menjelaskan project CNN-Jalan kepada Claude Code saat bekerja di repository ini.
UI dan konten database dalam Bahasa Indonesia.

## Project Overview

**CNN-Jalan** adalah aplikasi web GIS berbasis Flask untuk pemetaan kerusakan jalan di Kota Lhokseumawe, Aceh, Indonesia. Dikembangkan sebagai bagian dari skripsi (NIM 210170072).

**Tujuan utama:**
- Klasifikasi foto kerusakan jalan menggunakan CNN: **tingkat kerusakan** Berat / Sedang / Ringan (jenis CRACK/POTHOLE/RUTTING tidak diklasifikasi; tabel `jenis_kerusakan` tidak dipakai)
- Labeling SDI (Surface Distress Index) â€” standar Bina Marga
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

# Import database schema (MySQL harus running)
# Dump SQL lama sudah dihapus; gunakan migration SQL di scripts/.

# Atau jalankan migration tambahan jika sudah ada database:
# Get-Content migrate_add_preprocessing.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_split.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_arsitektur.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_hasil_evaluasi.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_patience.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_prediksi_model.sql | & mysql -u root db_cnn_jalan
# Get-Content migrate_add_pred_type.sql | & mysql -u root db_cnn_jalan

# Jalankan server development â€” WAJIB pakai venv python
.\.venv\Scripts\python.exe run.py
```

Akses di: **http://127.0.0.1:5000**

**Akun default:** `admin@gmail.com` / `12345678` â€” **ganti** dengan `python scripts/create_admin.py --email admin@gmail.com`. Pendaftaran publik hanya membuat akun `viewer`; hanya `admin` yang boleh mengubah data (`app/auth_utils.py::admin_required`). Semua form POST memakai token CSRF (`{{ csrf_token() }}`), logout lewat POST.

**Konfigurasi:** salin `.env.example` â†’ `.env`, isi `SECRET_KEY` (acak), `DATABASE_URL` (password MySQL), dan `FLASK_DEBUG` (1 hanya untuk dev lokal). `config.py` menolak start jika `SECRET_KEY`/`DATABASE_URL` belum diset.

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
| `lokasi_kerusakan` | Data lokasi GPS + dimensi kerusakan (`panjang`, `lebar` DECIMAL meter) + `keterangan` (`Ukur` / `Estimasi (Ringan\|Sedang\|Berat)`) |
| `dokumentasi_foto` | File foto per lokasi, path di `uploads/foto/` |
| `hasil_klasifikasi_cnn` | Output CNN per foto (jenis, tingkat, confidence) |
| `peta_kerusakan` | Status pemetaan (draftâ†’terverifikasiâ†’diperbaiki) |
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
- `lokasi_kerusakan` â† `label_kerusakan` â†’ `tingkat_kerusakan`
- `dokumentasi_foto` â† `hasil_preprocessing` â†’ `preprocessing_config`
- `split_config` â† `split_item` â†’ `dokumentasi_foto`
- `split_item` â†’ `tingkat_kerusakan` (label kelas untuk stratifikasi)
- `arsitektur_config` â†’ `split_config` (data yang dipakai training)
- `arsitektur_config` â† `hasil_training` (riwayat epoch)
- `arsitektur_config` â† `hasil_evaluasi` (confusion matrix + metrik evaluasi otomatis)
- `arsitektur_config` â† `prediksi_model` â†’ `dokumentasi_foto` (hasil prediksi per foto untuk GIS)

---

## Features & Progress

| Fitur | Status | Blueprint | Catatan |
|---|---|---|---|
| Auth (login/register) | Selesai | `auth` | Flask-Login, Werkzeug bcrypt |
| Dashboard | Selesai | `dashboard` | KPI cards, statistik realtime |
| Lokasi Kerusakan | Selesai | `lokasi` | CRUD, mini-map Leaflet di halaman detail |
| Klasifikasi CNN | Selesai | `klasifikasi` | Inferensi nyata memakai model terbaik (macro-F1 evaluasi tertinggi); tanpa model terlatih, upload ditolak. Hanya memprediksi tingkat, jenis dikosongkan |
| Labeling SDI | Selesai | `label` | Auto-label dari PÃ—L, kalkulasi real-time AJAX |
| Preprocessing | Selesai | `preprocessing` | Pipeline 5 tahap (+ Center Crop), OpenCV + Pillow, pagination, modal viewer |
| Split Data | Selesai | `split` | Stratified K-Fold (scikit-learn), distribusi tabel + Chart.js, export CSV |
| Arsitektur CNN | Selesai | `arsitektur` | MobileNetV2 & EfficientNetB0, transfer learning, background training, live progress, loss/acc chart |
| Evaluasi Hasil CNN | Selesai | `arsitektur` | Evaluasi otomatis dari val fold â€” confusion matrix 3Ã—3, per-class precision/recall/F1, macro avg |
| Prediksi GIS (Single) | Selesai | `arsitektur` | `predict_all()` â†’ simpan ke `prediksi_model`, tampil di peta `/arsitektur/<id>/gis` |
| Prediksi GIS (K-Fold CV) | Selesai | `arsitektur` | `predict_cv()` background thread, live progress, tiap foto diprediksi model yang tidak melihatnya |
| Peta GIS | Selesai | `peta` | Leaflet.js, GeoJSON endpoint, filter status |
| Evaluasi Model (Manual) | Selesai | `evaluasi` | Input manual metrik, tabel perbandingan |
| UI Modernisasi | Selesai | Semua | Split-screen auth, animated KPI, modern table, dropzone, civic govtech design |

---

## Status Akurasi CNN (per 2026-09-22)

**Metrik utama:** 5-fold CV MobileNetV2 = **48,9% ± 4,5**; baseline kelas mayoritas = **42,9%**.
**Kesimpulan:** target 70% belum tercapai. Backbone beku + regresi logistik berada di kisaran ±56–61% pada label surveyor, tetapi dengan label SDI kisarannya kembali ±46–52%.

**Catatan metodologi terbaru:**

| Area | Status terbaru |
|---|---|
| Label utama | Semua label dari SDI; kolom `keterangan` hanya informasi |
| Evaluasi utama | 5-fold CV; mode Single hanya visualisasi karena memprediksi foto latih |
| Model final | Dilatih pada 100% data setelah CV; akurasinya tidak dilaporkan sebagai metrik uji |
| Augmentasi | Layer Keras di dalam model; aktif hanya saat training |
| Head model | `GAP → Dropout(d) → Dense(64, relu, L2) → Dropout(d/2) → Dense(3, softmax, L2)` |

**Target akurasi: 70% (belum tercapai)**
**Setting awal yang disarankan untuk training baru:**
- Epochs: 60–80
- Learning Rate: `0.0001` (diperbaiki 2026-09-23 — `0.001` **salah**, form UI sendiri sudah menandai "⚠ terlalu tinggi, berisiko class collapse ke kelas mayoritas" dan semua run nyata sejauh ini memang memakai 0.0001)
- Batch Size: 32
- Dropout: 0.3–0.5
- Patience: biarkan default (min 20)

---|---------|----------|---------------------|
| 1 | Dataset sangat kecil (~280 foto, ~56 val/fold) | CRITICAL | Belum bisa difix dari kode â€” perlu tambah data |
| 2 | Recall Ringan hanya 33% â€” model bias ke Sedang | CRITICAL | Kembalikan class_weight (Ringan: 1.46x, Sedang: 0.70x) |
| 3 | Focal loss lama mereduksi gradient kelas Ringan | HIGH | Ganti ke SparseCategoricalCrossentropy |
| 4 | Train pakai preprocessed (augmented), val pakai original | HIGH | load_dataset selalu pakai path_file original |
| 5 | Fine-tune 30 layer dengan 224 sampel â†’ overfitting | MEDIUM | Kurangi 30â†’15 layer untuk MobileNetV2 |
| 6 | Dense layer langsung ke 3 kelas tanpa capacity | MEDIUM | Tambah Dense(128, relu) + L2(1e-4) sebelum output |
| 7 | EarlyStopping terlalu agresif | HIGH | patience min 20, min_delta 0.001 |
| 8 | ReduceLROnPlateau tidak ada | HIGH | Ditambah di Phase 1 & Phase 2 |
| 9 | predict_all() pakai gambar original bukan preprocessed | BUG | Diperbaiki dengan subquery HasilPreprocessing |

**Target akurasi: >70%**
**Setting yang disarankan untuk training baru:**
- Epochs: 60â€“80
- Learning Rate: `0.0001` (lihat catatan di atas â€” `0.001` berisiko class collapse)
- Batch Size: 32
- Dropout: 0.3â€“0.5 (model kini ada Dense(64) intermediate + Dropout(dropout/2))
- Patience: biarkan default (min 20)

**Arsitektur head model saat ini:**
`GAP â†’ Dropout(d) â†’ Dense(128, relu, L2) â†’ Dropout(d/2) â†’ Dense(3, softmax, L2)`

---

## Frontend Template System

### Base Template
`app/templates/base.html` â€” semua halaman authenticated extend ini.
- Bootstrap 5.3.3 + Tailwind CSS Play CDN (`preflight: false` agar tidak bentrok)
- Bootstrap Icons 1.11.3
- Font: **Inter** (Google Fonts) â€” bukan Fira Code/Fira Sans
- Sidebar navigasi dark, responsive dengan hamburger mobile

### CSS Variables (di `app/static/css/style.css`)
```
--c-bg        background halaman utama
--c-surface   background card/tabel
--c-text      teks utama
--c-muted     teks sekunder/placeholder
--c-border    border card/input
--c-accent    biru govtech (#0369A1) â€” BUKAN gold atau #38BDF8
--c-primary   navy (#0F172A)
--c-danger    merah (#E53E3E)
--r-card      border-radius card
--r-input     border-radius input/button
--sidebar-w   lebar sidebar
--shadow-card box-shadow card
```

**PENTING:** Selalu gunakan `--c-accent` (#0369A1) untuk warna utama. Jangan overwrite `style.css` tanpa backup â€” semua token, keyframes, dan animasi ada di sana.

### CSS Classes Penting
- `.btn-cnn-primary` â€” tombol utama gradient biru
- `.cnn-table` â€” tabel modern dengan navy thead
- `.cnn-dropzone` â€” dropzone upload drag-and-drop
- `.cnn-breadcrumb` â€” breadcrumb topbar
- `.auth-split`, `.auth-hero`, `.auth-glass-card` â€” layout split-screen login/register
- `.cnn-skeleton`, `.cnn-confidence-track`, `.cnn-confidence-fill` â€” skeleton loader & progress bar confidence
- `.skip-link` â€” accessibility skip navigation
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
- `page_header.html` â€” judul halaman. Set `{% set ph_title = 'Judul' %}` sebelum include
- `kpi_card.html` â€” kartu statistik dashboard
- `status_badge.html` â€” badge status berwarna
- `table_actions.html` â€” tombol aksi tabel (edit/hapus)
- `detail_row.html` â€” baris detail label-value
- `empty_table_row.html` â€” baris kosong tabel
- `quick_action.html` â€” tombol aksi cepat

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
- `app/static/js/peta.js` â€” Leaflet.js, fetch GeoJSON, render circle marker warna per tingkat, skeleton loader + error state + retry
- `app/static/js/toast.js` â€” toast notification dari Flask flash messages
- Inline `<script>` di template untuk logika per-halaman

---

## CNN Integration Point

File: `app/controllers/klasifikasi_controller.py` memanggil `cnn_service.best_model()` lalu
`cnn_service.predict_image(arsitektur, path, base_dir, prep_config)` â†’ `(kelas 0..2, confidence 0..1)`. Foto baru
diproses dengan pipeline preprocessing default (hasil tahap denoise) agar sama dengan data training. Kelas 0/1/2 =
Berat (id 1) / Sedang (id 2) / Ringan (id 3).

**`best_model()`** (direvisi 2026-09-23): utamakan `ArsitekturConfig` yang sudah `pred_type='cv'` dengan
`cv_summary().macro_f1` tertinggi (metrik resmi, rata-rata 5 fold) â€” fallback ke `HasilEvaluasi.macro_f1` (1 fold)
kalau belum ada config yang di-CV sama sekali.

**Ensemble + TTA** (baru 2026-09-23, lihat [[cnn-ensemble-tta]]): `predict_cv()` sekarang menyimpan model TIAP fold
(`model_{id}_fold{k}.keras`, lewat `save_model`), bukan cuma dipakai sekali lalu dibuang. `predict_image()`/`predict_all()`
lewat `_resolve_prediction_models()` otomatis pakai SEMUA model fold sebagai ensemble (rata-rata probabilitas) kalau
sudah tersedia dari CV terakhir â€” fallback ke 1 model (final/fold tunggal) kalau belum pernah CV. Tiap model (baik
ensemble maupun tunggal) diprediksi dengan **TTA sederhana** (`_predict_with_tta`): rata-rata probabilitas gambar asli
+ flip horizontal. Model fold lama dihapus otomatis (`arsitektur_controller._remove_fold_models`) saat re-train atau
hapus config, supaya ensemble tidak diam-diam pakai model basi dari split/data sebelumnya.

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
F_retak:   0%(â†’0) | â‰¤10%(â†’5) | â‰¤20%(â†’20) | >20%(â†’40)  Ã— 2 jika retak lebar
F_lubang:  0(â†’0)  | â‰¤10(â†’15) | â‰¤50(â†’75)  | >50(â†’225)
F_rutting: 0(â†’0)  | â‰¤1cm(â†’5) | â‰¤3cm(â†’20) | >3cm(â†’40)
Tingkat: SDIâ‰¤50=Ringan | 51â€“150=Sedang | >150=Berat
```
Implementasi: `app/models/label_kerusakan.py::LabelKerusakan.hitung_sdi()`
Auto-estimasi dari dimensi (meter): `LabelKerusakan.estimasi_dari_dimensi(panjang, lebar)`

**Sumber kelas (Auto-label):** semua dari SDI hasil estimasi PÃ—L (keputusan pemilik, 2026-09-22). Kolom `keterangan`
(`Ukur` / `Estimasi (X)`) hanya disimpan sebagai informasi, tidak memengaruhi kelas.
Catatan untuk bab pembahasan: kelas dari PÃ—L tidak tampak di foto (tanpa skala), sehingga akurasi CNN cenderung mendekati
baseline kelas mayoritas (uji 5-fold fitur beku: ~46â€“52% vs baseline 50,4%). Sebagai pembanding, kelas dari penilaian
surveyor (`Ket` untuk baris Estimasi) memberi macro-F1 lebih tinggi (~56â€“61%).

### Preprocessing Pipeline
Service: `app/services/preprocessing_service.py::PreprocessingService.run_pipeline(img_path, config)`
- Step 1 Resize: Pillow `Image.resize()` dengan metode LANCZOS/BILINEAR/BICUBIC/NEAREST
- Step 2 Center Crop: crop tengah ke dimensi target (crop_width Ã— crop_height), opsional
- Step 3 Normalisasi: numpy â€” min-max (`Ã·255`) atau z-score (`(x-Âµ)/Ïƒ`); output disimpan sebagai uint8 [0-255]
- Step 5 Augmentasi (tahap TERAKHIR, hanya visualisasi â€” tidak dipakai training; augmentasi training ada di dalam model): Pillow `ImageOps`, `ImageEnhance` â€” flip H/V, rotate, brightness, contrast; **setiap transform bersifat random per gambar** (bukan deterministik semua identik)
- Step 4 Denoise (keluarannya yang dipakai training): OpenCV `GaussianBlur` / `medianBlur` / `bilateralFilter`
Output: `app/static/uploads/preprocessed/`
Halaman hasil: pagination 24/halaman, modal viewer dengan navigasi prev/next + keyboard (â†â†’Esc), tombol Reset Semua.

**Reset Semua Preprocessing** (`/preprocessing/hasil/reset` POST):
- Menghapus file fisik di `uploads/preprocessed/` + semua record `HasilPreprocessing` di DB
- Sebelumnya hanya hapus DB records â€” file fisik sekarang ikut dihapus untuk menghindari orphan

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
- `mobilenetv2`: MobileNetV2(include_top=False, ImageNet) + GlobalAvgPool + Dropout + Dense(3, softmax)
- `efficientnetb0`: EfficientNetB0(include_top=False, ImageNet) + head yang sama
- Augmentasi di dalam model (aktif saat training=True, off saat predict): RandomFlip H+V, RandomRotation(0.25), RandomZoom(0.2), RandomTranslation(0.1,0.1), RandomBrightness(0.3), RandomContrast(0.3)
- Phase 1: base frozen (`training=False`), head trainable

**`train(arsitektur, base_dir, on_epoch_end=None)`** (kriteria checkpoint direvisi 2026-09-22, lihat [[cnn-checkpoint-selection]])
- **Inner-val**: 15% data training (stratified **di level foto**, lihat `_group_aware_split`) dipisah untuk early stopping. Fold uji **tidak pernah** dipakai untuk memutuskan apa pun (early stopping, LR, pilihan epoch/fase) â€” hanya dievaluasi tiap epoch untuk grafik/log (`uji_loss`, `uji_acc`)
- Phase 1: frozen base, EarlyStopping(monitor=inner val_loss, patience=max(user,20), min_delta=0.001) + ReduceLROnPlateau(factor=0.5, patience=patience//2, min_lr=1e-6) â€” val_loss dipantau untuk KONTROL training (kapan berhenti/turunkan LR) saja
- **Pemilihan bobot terbaik** (`_fit_phase`, `_is_better_checkpoint`): pakai **BALANCED accuracy inner-val** (rata-rata recall antar kelas via `sklearn.metrics.balanced_accuracy_score`, dihitung tiap epoch dari prediksi `X_inner`), bukan val_loss/akurasi mentah â€” root-cause dari log training menunjukkan val_loss bisa terus turun (model makin percaya diri) tanpa akurasi ikut membaik, dan akurasi mentah bias ke kelas mayoritas (Sedang). val_loss cuma jadi tiebreaker saat balanced accuracy sama persis. Bobot disimpan di memori, tanpa file sementara
- Phase 2 (fine-tune): unfreeze top 15 layers MobileNetV2 / top 25 EfficientNetB0 (BatchNorm tetap frozen), lr/5, callback serupa (patience max(10, patience//2))
- Phase 2 dipakai hanya jika `_is_better_checkpoint` bilang balanced accuracy-nya lebih baik dari Phase 1, jika tidak kembali ke bobot Phase 1
- class_weight dari `compute_class_weight('balanced')` atas data fit (tanpa inner-val). **Sempat dicoba** boost tambahan Ã—1.5 khusus Ringan (2026-09-22) untuk atasi recall Ringan rendah, tapi **dibatalkan** (2026-09-23) â€” terbukti overcorrect: rasio Ringan:Sedang jadi 3,5x, model ganti bias ke Ringan/Berat dan recall Sedang anjlok (23%), macro-F1 malah turun dibanding tanpa boost. Kembali ke `balanced` polos
- Loss: `SparseCategoricalCrossentropy`; seed tetap (`SEED = 42`) agar hasil bisa direproduksi
- Grafik/`hasil_training.val_*` = fold uji per epoch; jangan baca "val acc terbaik" sebagai estimasi generalisasi â€” pakai `hasil_evaluasi` (model final) atau prediksi CV

**`load_dataset(split_config_id, fold_val, input_size, base_dir)`** (keputusan terakhir 2026-09-23, riwayat di [[cnn-training-data-expansion]])
- Query `split_item` JOIN `dokumentasi_foto`; fold==fold_val â†’ val, sisanya â†’ train
- **Training**: diperluas â€” setiap tahap non-acak yang tersedia per foto (`TRAIN_EXPAND_STEPS` = resize, crop, normalisasi, denoise) dipakai sebagai sampel terpisah dengan label yang sama. `augmentasi` dikecualikan (acak, tidak reproducible). Foto tanpa preprocessing fallback ke 1 sampel original
- **Dedup konten** (`distinct_stage_paths`, hash MD5 per file): tahap yang hasilnya identik byte-per-byte dengan tahap lain di foto yang sama (mis. `crop` == `resize` saat `preprocessing_config.crop_enabled=False`) **tidak** dihitung dua kali. `split_controller._expanded_sample_count` (statistik UI "Sampel Training Efektif") memakai `cnn_service.effective_sample_count` yang sama
- **Validasi/fold uji: 1 gambar per foto** (utamakan tahap denoise, fallback original) â€” **SAMA** seperti `predict_all`/`predict_cv`/klasifikasi foto baru. **Riwayat:** sempat dicoba ikut diperluas (2026-09-22) supaya "konsisten" dengan training, tapi **dibatalkan (2026-09-23)** setelah audit menemukan itu membuat `evaluate()`/`HasilEvaluasi` ("Akurasi Model Final") mengukur sampel yang saling berkorelasi (beberapa versi dari foto yang sama, bukan titik data independen) â€” tidak lagi sebanding dengan `cv_summary()`/`predict_cv` yang selalu 1 gambar/foto, dan bikin angka akurasi antar-run lebih berisik tanpa manfaat nyata
- Return: `(X_train, y_train, groups_train, X_val, y_val, groups_val)` â€” `groups_train` = `dokumentasi_id` per sampel training, dipakai `_group_aware_split` di `train()` supaya varian tahap dari foto yang sama tidak terpisah antara data fit dan inner-val (cegah leakage sampel nyaris-identik). `groups_val` isinya 1:1 dengan `y_val` (tidak dipakai untuk apa pun khusus, sekadar konsisten)
- Input: float32 [0,255] â†’ `preprocess_input()` di dalam model yang normalize ke [-1,1]
- Label: `tingkat_kerusakan_id - 1` (Berat=0, Sedang=1, Ringan=2)
- **PENTING (audit metodologi 2026-09-23):** `HasilEvaluasi`/"Akurasi Model Final" di halaman detail arsitektur adalah metrik **1 FOLD SAJA**, BUKAN metrik CV resmi. Metrik yang boleh dilaporkan (lihat bagian "Evaluasi, Pipeline Ulang, dan Tes") adalah `cv_summary()` (`pred_type='cv'`, hasil "Prediksi CV K-Fold"). **Bug ditemukan & diperbaiki 2026-09-23:** `predict_cv()` selalu crash (`NameError: SimpleNamespace` tidak di-import) sejak awal project â€” errornya senyap (langsung ke-`pop()` sebelum sempat tampil), jadi `pred_type` tidak pernah `'cv'` sampai bug ini ditemukan. Hasil CV pertama yang valid di project ini (split baru, arsitektur MobileNetV2 default): **akurasi 45,4% Â± 6,7, macro-F1 44,6%, baseline mayoritas 50,4%** â€” model masih di BAWAH baseline, jadi jangan anggap 45,4% ini "target tercapai". Jangan bandingkan angka `HasilEvaluasi.akurasi` (1 fold) antar-run sebagai indikator naik/turun â€” variansnya besar (per-fold di run ini: 37,5%â€“55,4%)

**`predict_cv(arsitektur, base_dir)`**
- K-Fold: setiap foto diprediksi oleh model yang di-train tanpa foto tersebut, dengan TTA (`_predict_with_tta`)
- Menggunakan preprocessed images tahap `denoise` (1 gambar/foto, konsisten dengan inferensi nyata) â€” tidak memakai ekspansi multi-tahap `load_dataset`
- **Menyimpan model tiap fold** (`model_{id}_fold{k}.keras`, baru 2026-09-23) â€” dipakai `_resolve_prediction_models` sebagai ensemble saat klasifikasi foto baru, bukan cuma untuk prediksi fold itu sendiri lalu dibuang
- Dijalankan sebagai background thread, progress via `_cv_progress`

**`predict_all(arsitektur, base_dir)`**
- Pakai `_resolve_prediction_models()` (ensemble fold CV + TTA kalau tersedia, fallback 1 model) â€” lihat bagian "CNN Integration Point"
- Prediksi semua foto berlabel dengan koordinat GPS
- Hasil disimpan ke tabel `prediksi_model`

**`evaluate(arsitektur, base_dir)`**
- Load model â†’ predict X_val â†’ sklearn confusion_matrix + classification_report
- Return: `{total_data_val, akurasi, confusion_matrix(JSON), per_class{berat/sedang/ringan}, macro}`

Model tersimpan di: `app/static/models/model_{id}.keras`
Training history per epoch di tabel `hasil_training`.

### Training Flow Otomatis (setelah klik Train)
```
train() â†’ save_model() â†’ evaluate() [auto] â†’ predict_all() [auto]
â†’ set status='selesai', pred_type='single'
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
- Input: list foto yang punya `LabelKerusakan` (join `DokumentasiFoto â†’ LokasiKerusakan â†’ LabelKerusakan`)
- `StratifiedKFold` dari scikit-learn â€” shuffle=True, reproducible via random_state
- Hasil disimpan ke `split_item` dengan `fold_index` 0..K-1
- Halaman detail: tabel distribusi kelas per fold + grouped bar chart (Chart.js 4)
- Export CSV: `nama_file, fold_index, tingkat, latitude, longitude`

**Reset Items Split** (`/split/<id>/reset` POST):
- Hapus semua `SplitItem` milik config tanpa menghapus `SplitConfig` itu sendiri
- Reset `total_data = 0` di `SplitConfig`
- **Ditolak** jika ada `ArsitekturConfig` yang merujuk split tersebut (FK constraint)
- Berguna untuk re-split setelah preprocessing ulang

### SQLAlchemy Cascade Note
`ArsitekturConfig.split_config` relationship menggunakan `passive_deletes=True` pada backref. Ini mencegah ORM mencoba SET NULL saat `SplitConfig` dihapus â€” karena kolom `split_config_id` adalah NOT NULL, ORM tidak boleh issue UPDATE tersebut; biarkan DB yang handle via FK constraint.

### Labeling SDI â€” Hapus Semua
Route `label.hapus_semua` (`/label/hapus-semua` POST) menghapus semua record `LabelKerusakan`. Tombol "Hapus Semua" di `label/index.html` muncul hanya jika `sudah > 0`, dengan modal konfirmasi Bootstrap custom. Endpoint **bukan** `label.delete_all` â€” function name `hapus_semua` dipakai untuk menghindari konflik routing.

### Restore Foto Utility
`restore_foto.py` â€” script standalone untuk memulihkan foto yang terhapus dari `uploads/foto/`:
- Baca `DokumentasiFoto` dari DB, strip 21-char timestamp prefix dari `nama_file`
- Cari file asli di `data/jalan/` (case-insensitive), copy ke `uploads/foto/`
- DB tidak diubah sama sekali

### Import Data (Excel â†’ DB)
`scripts/seed_data.py` â€” kolom Excel: `Citra, x (lat), y (lon), P, L, Ket`. Semua nilai numerik (meter, derajat desimal), divalidasi sebelum ada yang dihapus.
- `--reset`: TRUNCATE tabel data model (lokasi, foto, label, preprocessing, split, arsitektur, training, evaluasi, prediksi) + hapus `uploads/foto`, `uploads/preprocessed`, `models/*.keras`
- Tabel master (`pengguna`, `jenis/tingkat_kerusakan`, `preprocessing_config`, `evaluasi_model`) tidak disentuh
- Setelah import: jalankan ulang Auto-label SDI â†’ Preprocessing â†’ Split â†’ Training

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

Jalankan **berurutan** sesuai kebutuhan database. Dump SQL lama sudah dihapus karena berisi skema/data lama; migration SQL di `scripts/` menjadi rujukan perubahan schema.

| File | Fungsi | Status |
|---|---|---|
| `migrate_remove_kecamatan.sql` | Hapus tabel & kolom kecamatan | Sudah dijalankan |
| `migrate_add_preprocessing.sql` | Tambah tabel preprocessing_config & hasil_preprocessing | Sudah dijalankan |
| `migrate_add_split.sql` | Tambah tabel split_config & split_item + indexes | Sudah dijalankan |
| `migrate_add_arsitektur.sql` | Tambah tabel arsitektur_config & hasil_training | Sudah dijalankan |
| `migrate_add_hasil_evaluasi.sql` | Tambah tabel hasil_evaluasi (FK arsitektur_config) | Sudah dijalankan |
| `migrate_add_patience.sql` | Tambah kolom `patience` di arsitektur_config | Sudah dijalankan |
| `migrate_add_prediksi_model.sql` | Tambah tabel prediksi_model (arsitektur_id, dok_id, prediksi, aktual, confidence) | Sudah dijalankan |
| `migrate_add_pred_type.sql` | Tambah kolom `pred_type` VARCHAR(10) di arsitektur_config (none/single/cv) | Sudah dijalankan |
| `migrate_revisi_lokasi.sql` | `panjang`/`lebar` â†’ DECIMAL(8,2) meter, tambah `keterangan` di lokasi_kerusakan | Sudah dijalankan |
| `migrate_klasifikasi_jenis_nullable.sql` | `hasil_klasifikasi_cnn.jenis_kerusakan_id` boleh NULL | Sudah dijalankan |
| `migrate_add_final_model.sql` | Tambah kolom `final_model_path` di arsitektur_config | Sudah dijalankan |
| `seed_data.py` | Reset data model + import Excel revisi & foto (`scripts/seed_data.py --reset`) | Sudah dijalankan |

---

## Evaluasi, Pipeline Ulang, dan Tes

- **Metrik yang boleh dilaporkan:** hasil K-Fold CV (`app/services/metrics_service.py::cv_summary`, tampil di halaman detail & GIS
  setelah "Prediksi CV K-Fold"): akurasi Â± std antar fold, macro-F1, recall per kelas, dan baseline kelas mayoritas.
  Prediksi mode *Single* ikut memprediksi foto latih, jadi hanya untuk visualisasi (halaman GIS memberi peringatan).
- **Split basi:** `split_service.jumlah_label_basi(config_id)` menghitung item split yang kelasnya beda dengan label sekarang.
  Training ditolak sampai split dibuat ulang; banner tampil di halaman split dan arsitektur.
- **Start ganda:** status `training` diklaim atomik di `arsitektur.train`; saat `run.py` start, status `training` yang
  tersisa ditandai `gagal` (`tandai_training_terputus`).
- **Model final:** setelah CV, tombol "Latih Model Final" (halaman detail arsitektur) melatih satu model pada 100% data
  (`cnn_service.train_final`, early stopping tetap memakai inner-val) â†’ `arsitektur_config.final_model_path`. Klasifikasi foto baru
  memakai model final bila ada. **Akurasi tidak dihitung dari model final** (tidak ada data uji tersisa); laporkan hasil K-Fold CV.
- **Ulang pipeline sekali jalan:** `python scripts/run_pipeline.py` (Auto-label â†’ Preprocessing â†’ Split â†’ Training â†’ CV â†’ Model final);
  opsi `--skip-preprocessing`, `--no-cv`, `--no-final`, `--epochs`, `--fold`, dll. (`--help`).
- **Tes:** `python -m unittest discover -s tests -t . -v` (memakai DB dev; data uji sementara dibersihkan otomatis).




