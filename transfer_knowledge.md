# Transfer Knowledge — CNN Jalan: Pipeline Labeling, Klasifikasi, dan Evaluasi

**Dibuat:** 27 September 2026  
**Proyek:** cnn-jalan (Flask + SQLAlchemy + MySQL + TensorFlow/Keras)  
**Database:** MySQL `db_cnn_jalan`  
**Lokasi proyek:** `D:\flask\cnn_jalan\`

---

## Daftar Isi

1. [Ikhtisar Sistem](#1-ikhtisar-sistem)
2. [Pipeline Data Secara Keseluruhan](#2-pipeline-data-secara-keseluruhan)
3. [Preprocessing](#3-preprocessing)
4. [Labeling & K-Means Clustering](#4-labeling--k-means-clustering)
5. [Augmentasi Citra](#5-augmentasi-citra)
6. [Split K-Fold](#6-split-k-fold)
7. [Arsitektur Model & Transfer Learning](#7-arsitektur-model--transfer-learning)
8. [Training & Fine-Tuning](#8-training--fine-tuning)
9. [Prediksi & Klasifikasi](#9-prediksi--klasifikasi)
10. [Evaluasi Model](#10-evaluasi-model)
11. [Labeling & Klasifikasi pada Peta](#11-labeling--klasifikasi-pada-peta)
12. [Workflow & Services — Arsitektur Internal](#12-workflow--services--arsitektur-internal)
13. [Struktur Database](#13-struktur-database)
14. [Konfigurasi & Nilai Aktual](#14-konfigurasi--nilai-aktual)
15. [Catatan Penting & Risiko](#15-catatan-penting--risiko)

---

## 1. Ikhtisar Sistem

Sistem `cnn-jalan` adalah aplikasi web Flask untuk **klasifikasi kondisi jalan** menggunakan CNN (MobileNetV2 / EfficientNetB0) berbasis transfer learning. Alur kerja dimulai dari foto lapangan, melalui preprocessing, labeling otomatis via K-Means, augmentasi, training, hingga prediksi dan pemetaan kondisi jalan.

**Skema klasifikasi (4 kelas, berdasarkan skema SDI Bina Marga):**

| Indeks | Kelas | Warna | SDI |
|--------|-------|-------|-----|
| 0 | Rusak Berat | `#E53E3E` | SDI > 150 |
| 1 | Rusak Ringan | `#F97316` | SDI 100–150 |
| 2 | Sedang | `#F59E0B` | SDI 50–100 |
| 3 | Baik | `#10B981` | SDI < 50 |

Sumber file: `app/kelas.py`

**Tiga sumber data klasifikasi:**
- **Labeling K-Means** (otomatis) → `label_kerusakan` → digunakan untuk split dan training
- **Prediksi CNN** (inferensi model) → `prediksi_model` → ditampilkan di peta
- **Klasifikasi tunggal** (upload foto manual) → `hasil_klasifikasi_cnn` → riwayat individual

---

## 2. Pipeline Data Secara Keseluruhan

```
Foto Lapangan (uploads/foto)
        │
        ▼
┌─────────────────────┐
│  Preprocessing      │  ← PreprocessingService
│  (resize, crop,     │     app/services/preprocessing_service.py
│   norm, denoise)    │     app/models/preprocessing_config.py
└────────┬────────────┘
         │ HasilPreprocessing (table)
         ▼
┌─────────────────────┐
│  Labeling K-Means   │  ← labeling_service.py
│  (embedding + PCA   │     app/services/labeling_service.py
│   + cluster)        │     app/models/hasil_labeling*.py
└────────┬────────────┘
         │ HasilLabelingItem → label_kerusakan (setelah "Terapkan")
         ▼
┌─────────────────────┐
│  Split K-Fold       │  ← SplitService
│  (StratifiedKFold)  │     app/services/split_service.py
└────────┬────────────┘
         │ SplitItem (train/val folds)
         ▼
┌─────────────────────┐
│  Augmentasi Citra   │  ← augmentation_service.py
│  (10 transformasi)  │     app/models/augmentasi_config.py
└────────┬────────────┘
         │ HasilAugmentasi (table)
         ▼
┌─────────────────────┐
│  Training CNN       │  ← cnn_service.model / training
│  (MobileNetV2 /     │     app/services/cnn_service/model.py
│   EfficientNetB0)   │     app/services/cnn_service/training.py
└────────┬────────────┘
         │ HasilTraining → ArsitekturConfig
         ▼
┌─────────────────────┐
│  Prediksi / Evaluasi│  ← cnn_service.prediction / evaluation
│  (predict_all,      │     app/models/prediksi_model.py
│   predict_cv,       │     app/services/cnn_service/evaluation.py
│   evaluate)         │     app/models/hasil_evaluasi.py
└────────┬────────────┘
         │ PrediksiModel → peta_kerusakan
         ▼
┌─────────────────────┐
│  Peta (GIS)         │  ← peta_controller / peta_kerusakan
│  (GeoJSON overlay)  │     app/templates/peta/index.html
└─────────────────────┘
```

---

## 3. Preprocessing

### File Utama
- **Service:** `app/services/preprocessing_service.py`
- **Model:** `app/models/preprocessing_config.py`
- **Hasil:** `app/models/hasil_preprocessing.py`

### Tahapan Pipeline (4 langkah, kumulatif)

| Step | Key | Deskripsi | Default |
|------|-----|-----------|---------|
| 1 | `resize` | Resize ke target dimensi + optional gray-world white balance | 256×256, LANCZOS, stretch |
| 2 | `crop` | Center crop | 224×224 (enabled) |
| 3 | `normalisasi` | MinMax / Z-score / CLAHE / none | none |
| 4 | `denoise` | Gaussian / Median / Bilateral / NLMeans / none | bilateral, ksize=3 |

### Detail Teknis

**Step 1 — Resize:**
- Menggunakan PIL `Image.Resampling.LANCZOS` (default) atau `LANCZOS_CV` (OpenCV `cv2.INTER_LANCZOS4`)
- Opsi `letterbox`: jaga aspect ratio, pad dengan hitam di sisi sisa
- Optional `illum_correction`: gray-world white balance (skalasi tiap kanal RGB ke mean abu-abu global) untuk mengurangi variasi warna antar sesi pemotretan

**Step 2 — Center Crop:**
- Crop dari tengah gambar ke ukuran `crop_width × crop_height`
- Default 224×224

**Step 3 — Normalisasi:**
- `minmax`: per-channel min-max stretch ke [0, 255]
- `zscore`: z-score global, rescale ke [0, 255]
- `clahe`: CLAHE di kanal L (LAB colorspace) — kontras lokal tanpa merusak kontras absolut
- `none`: tidak ada perubahan (default)

**Step 4 — Denoise:**
- `gaussian`: `cv2.GaussianBlur` dengan kernel ukuran ganjil
- `median`: `cv2.medianBlur`
- `bilateral`: `cv2.bilateralFilter` (default, ksize=3, sigma=75)
- `nlmeans`: `cv2.fastNlMeansDenoisingColored` (h=7, hColor=7, templateWindowSize=7, searchWindowSize=21)
- `none`: tidak ada denoise

**Konfigurasi default (`PreprocessingConfig.aktif()`):**
- Resize: 256×256, LANCZOS, stretch mode
- Illumination correction: False
- Crop: 224×224 enabled
- Norm: none
- Denoise: bilateral, ksize=3

### Penyimpanan
- Output disimpan di `uploads/preprocessed/{doc_id}/step_name.jpg`
- Setiap langkah disimpan sebagai gambar terpisah (kumulatif)
- Tabel `hasil_preprocessing`: `(dokumentasi_id, step_name, path_output, status)`

### Catatan Penting
- **Satu config aktif** — hanya ada satu preprocessing config yang menghasilkan data pada satu waktu (ditentukan oleh `HasilPreprocessing` terakhir)
- `TRAIN_EXPAND_STEPS = ('resize', 'crop', 'normalisasi', 'denoise')` — keempat step ini digunakan sebagai "expansion" untuk training data (satu foto → banyak sampel)
- File yang kontennya identik antar step (misal crop == resize saat crop disabled) **di-dedup** lewat MD5 hash di `dataset.py::distinct_stage_paths()`

---

## 4. Labeling & K-Means Clustering

### File Utama
- **Service:** `app/services/labeling_service.py`
- **Model:** `app/models/labeling_config.py`, `app/models/hasil_labeling.py`, `app/models/hasil_labeling_item.py`
- **Source of Truth:** `app/services/label_source.py`

### Alur Kerja

```
LabelingConfig (user setting)
    │
    ├─── ekstrak_fitur_lokasi()
    │       │
    │       ├── MobileNetV2 embedding (2048-dim, average pooling)
    │       └── Edge density (Canny edge detection)
    │
    ├─── klasterisasi()
    │       ├── StandardScaler
    │       ├── PCA (n_components=50, explained_variance_ratio_)
    │       └── KMeans (k=4, n_init=10, random_state=42)
    │
    └─── urutkan_klaster_ke_tingkat()
            └── Sort cluster by mean edge_density → map ke 4 TingkatKerusakan
                (Baik → Sedang → Rusak Ringan → Rusak Berat)
```

### Ekstraksi Fitur

**MobileNetV2 Embedding:**
- Model: MobileNetV2 (weights='imagenet', include_top=False, pooling='avg')
- Input: 224×224 RGB, preprocessed via `preprocess_input`
- Output: vektor 1280-dim → rata-rata per lokasi dari semua foto

**Edge Density (Kepadatan Tepi):**
- Grayscale → Canny edge detection (`canny_low=50, canny_high=150`)
- `edge_density = edges.mean() / 255.0` → nilai 0..1
- Rata-rata per lokasi dari semua foto

### Klasterisasi

- **Jumlah klaster:** 4 (sesuai jumlah kelas)
- **PCA:** 50 komponen (atau jumlah fitur jika < 50)
- **KMeans:** `n_clusters=4, n_init=10, random_state=42`
- **Pengurutan klaster:** Diurutkan berdasarkan mean `kepadatan_tepi` ascending → cluster dengan edge density terendah = "Baik", tertinggi = "Rusak Berat"
- **Mapping ke tingkat:** `TingkatKerusakan.query.filter_by(nama_tingkat=name).first()`

### Hasil Penyimpanan

**Baris `HasilLabeling` (run):**
- `jumlah_lokasi`, `jumlah_dilewati`, `variansi_pca`, `distribusi_kelas` (JSON), `status` ('proses'/'selesai'/'gagal'), `is_diterapkan`

**Baris `HasilLabelingItem` (per lokasi):**
- `klaster`, `kepadatan_tepi`, `jarak_centroid`, `tingkat_kerusakan_id`

### label_source.py — Single Source of Truth

**Fungsi kunci:** `label_map(run_id=None)` → `{lokasi_id: tingkat_kerusakan_id}`

**Prioritas resolusi (yang pertama menang):**
1. **Label manual** (`metode='manual'`) — override manusia tetap precedence tertinggi
2. **Run klasterisasi terakhir** yang `status == 'selesai'` — sumber utama
3. **Label hasil Terapkan** (`metode='klasterisasi'`) — fallback jika run asalnya sudah dihapus

**Mengapa ini penting:** Historis, `label_kerusakan` hanya terisi setelah endpoint "Terapkan" dijalankan, padahal `hasil_labeling_item` sudah final sejak run selesai. Ini menyebabkan halaman split bisa melihat 0 foto berlabel padahal labeling sudah jalan. `label_source.py` menyatukan semua konsumen (split, staleness check, batch prediction, dashboard) ke satu fungsi.

### Database — Jumlah Data Aktual

| Tabel | Jumlah Baris |
|-------|-------------|
| `lokasi_kerusakan` | 280 |
| `dokumentasi_foto` | 280 |
| `split_item` | 280 |
| `label_kerusakan` | 0 (sebelum "Terapkan" dijalankan) |
| `tingkat_kerusakan` | 4 |

**Catatan:** `label_kerusakan` berisi 0 baris karena belum ada run labeling yang diterapkan (belum klik "Terapkan"). Data `hasil_labeling_item` tetap ada sebagai run klasterisasi yang sudah selesai.

---

## 5. Augmentasi Citra

### File Utama
- **Service:** `app/services/augmentation_service.py`
- **Model:** `app/models/augmentasi_config.py`
- **Hasil:** `app/models/hasil_augmentasi.py`
- **In-model layers:** `app/services/cnn_service/model.py` (`_augmentation_layers()`, `_augmentation_layers_colab()`)

### 10 Transformasi

| Key | Transformasi | Default Parameters |
|-----|-------------|-------------------|
| `flip` | Horizontal flip | `p=0.5` |
| `rotasi` | Rotation | `derajat=18.0` (±18°) |
| `zoom` | Zoom | `faktor=0.2` (±20%) |
| `translasi` | Translation | `faktor=0.1` (±10%) |
| `brightness` | Brightness | `faktor=0.3` (±30% of 255) |
| `contrast` | Contrast | `faktor=0.3` (±30%) |
| `hue` | Hue shift | `faktor=0.05` (±5° in HSV) |
| `saturasi` | Saturation | `faktor=0.2` (±20%) |
| `noise` | Pixel noise | `sigma=3.0` (Gaussian) |
| `erasing` | Random Erasing (Cutout) | `p=0.5`, `luas_min=0.02`, `luas_maks=0.08` |

### Eksekusi

- **Offline** dengan RNG ber-seed: `np.random.default_rng([seed, doc_id, salinan_ke])` → reproducible, hasil sama di mesin mana pun
- `n_salinan` default = 3 salinan per foto
- Output: `uploads/augmented/{timestamp}_{doc_id}_a{salinan_ke}.jpg`
- Tabel `HasilAugmentasi`: `(dokumentasi_id, config_id, salinan_ke, path_output, status)`
- Salinan **mewarisi** kelas dan fold dari foto asal (bukan label baru)

### Urutan Transformasi
Sama persis dengan layer augmentasi Keras di `model.py`: flip → rotasi+zoom+translasi (combined affine) → brightness → contrast → hue+saturasi (HSV) → noise → erasing.

### Konfigurasi
- `AugmentasiConfig.aktif()`: config dari `HasilAugmentasi` terakhir, fallback ke default/pertama
- `config.parameter` disimpan sebagai JSON `{transformasi: {aktif, ...besaran}}`

### Catatan Penting
- **Random Erasing (Cutout)** adalah penyebab munculnya "patch warna acak" pada gambar yang di-augment — ini **sengaja** untuk melatih model agar tidak bergantung pada satu titik kerusakan
- `AUG_KEYS` di `model.py` dan `KUNCI` di `augmentation_service.py` dijaga sinkron — jika ada augmentasi baru di salah satu, harus ditambahkan di keduanya
- `aug_off` (di ArsitekturConfig) memungkinkan ablation: mematikan layer tertentu saat training dengan memisahkan kunci koma

---

## 6. Split K-Fold

### File Utama
- **Service:** `app/services/split_service.py`
- **Model:** `app/models/split_config.py`, `app/models/split_item.py`
- **Dataset loader:** `app/services/cnn_service/dataset.py`

### Metode Splitting

**Stratified K-Fold** — menjaga proporsi kelas di setiap fold:
```python
skf = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
splits = skf.split(X, y)  # X = index, y = label_id
```

**Stratified Group K-Fold** — jika ada near-duplicate groups (anti-leakage):
```python
skg = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
splits = skg.split(X, y, groups=groups)  # groups dari dedup_service
```

**Group = dokumentasi_id** — semua sampel dari foto yang sama selalu di fold yang sama, mencegah data leakage.

### Dataset Loading (`dataset.py::load_dataset()`)

**Training set:**
- Setiap foto diperluas menjadi beberapa sampel:
  - Semua stage preprocessing non-acak yang tersedia (resize, crop, normalisasi, denoise) — **dedup** jika konten file identik
  - Salinan augmentasi offline ber-seed
- Fallback: 1 sampel original jika tidak ada preprocessing
- `hanya_denoise=True` (profil Colab): hanya 1 gambar per foto (tahap denoise)

**Validasi set:**
- **1 gambar per foto** — utamakan tahap `denoise`, fallback ke original
- Keputusan 2026-09-23: memperluas validasi seperti training membuat evaluasi mengukur sampel yang saling berkorelasi (varian dari foto yang sama), tidak lagi representatif sebagai titik data independen

**Group-aware split:** `_group_aware_split()` — train/inner-val split di level foto (bukan level sampel) agar varian tahap preprocessing dari foto yang sama tidak saling bocor.

### Data Statistik Aktual
- 280 lokasi → 280 foto
- Split K-Fold (misal 5-fold): ~56 foto per fold
- Training set per fold: ~224 foto (expanded via preprocessing stages + augmentasi)
- Validasi per fold: ~56 foto

### Batasan Minimum
- `MIN_TRAIN_SAMPLES = 20`, `MIN_VAL_SAMPLES = 5`

---

## 7. Arsitektur Model & Transfer Learning

### File Utama
- **Model builder:** `app/services/cnn_service/model.py`
- **Training:** `app/services/cnn_service/training.py`
- **Prediction:** `app/services/cnn_service/prediction.py`
- **Evaluation:** `app/services/cnn_service/evaluation.py`
- **Config:** `app/models/arsitektur_config.py`

### Arsitektur: Transfer Learning

```
Input (224×224×3)
    │
    ├──► [Augmentation Layers] (training only, Keras layers)
    │
    ├──► preprocess_input (MobileNetV2/EfficientNetB0 specific)
    │
    ├──► Base Model (frozen → fine-tune)
    │     ├── MobileNetV2 (ImageNet weights, ~154 layers)
    │     └── EfficientNetB0 (ImageNet weights, ~238 layers)
    │
    ├──► GlobalAveragePooling2D
    │
    ├──► Dropout (dropout_rate)
    │
    ├──► Dense(dense_units=64, activation='relu', kernel_regularizer=L2=1e-4)
    │
    ├──► Dropout (0.3 if colab, else dropout_rate/2)
    │
    └──► Dense(N_CLASSES=4, activation='softmax')
```

### Backbone Options

| Parameter | MobileNetV2 | EfficientNetB0 |
|-----------|-------------|----------------|
| Layers | ~154 | ~238 |
| Unfreeze (fine-tune) | Last 8 | Last 12 |
| Unfreeze (Colab) | Last 6 | Last 6 |
| Input size default | 224×224 | 224×224 |

### Hyperparameter Default

| Parameter | Nilai |
|-----------|-------|
| `learning_rate` | 0.0001 |
| `batch_size` | 16 |
| `epochs` | 30 |
| `patience` | 5 (early stopping) |
| `dropout_rate` | 0.3 |
| `optimizer` | adam |
| `dense_units` | 64 |
| `dense_l2` | 1e-4 |
| `mixup_alpha` | 0 (nonaktif) |
| `label_smoothing` | 0 (nonaktif) |
| `skip_fine_tuning` | False |
| `profil` | 'standar' (atau 'colab') |
| `aug_off` | '' (semua aktif) |
| `input_size` | 224 |

### Fine-Tuning Strategy
- **Phase 1:** Backbone frozen, head dilatih
- **Phase 2 (optional):** Top N layer backbone dibuka (unfreeze), recompile dengan `lr/10` (standar) atau `lr/20` (colab)
- **BatchNormalization** tetap frozen (non-Colab) untuk preserve ImageNet statistics
- Keputusan 2026-09-23: jumlah unfreeze dikurangi dari 15/25 → **8/12** karena training berulang menunjukkan train acc naik ke 70%+ sementara val macet ~35-45% (tanda fine-tuning terlalu dalam untuk dataset kecil)

### Loss Function
- **Default:** `SparseCategoricalCrossentropy()` (label integer)
- **Jika Mixup/Label Smoothing aktif:** `CategoricalCrossentropy(label_smoothing=...)` (label one-hot/soft)

---

## 8. Training & Fine-Tuning

### File Utama
- `app/services/cnn_service/training.py`

### Proses
1. Model dibangun via `build_model()`
2. Jika `skip_fine_tuning=False`: Phase 1 (backbone frozen) → Phase 2 (fine-tuning)
3. Early stopping berdasarkan `patience` epoch
4. Best model disimpan (path ke checkpoint)

### Profil Colab
- `profil='colab'` → 6 layer augmentasi saja (flip, rotasi 20/360, brightness 0.25, contrast 0.25, zoom 0.15, translasi 0.1)
- Learning rate lebih rendah (×20 lebih kecil saat fine-tuning)
- Dropout kedua tetap 0.3, lapisan output tanpa regularizer
- `aug_off` kosong (semua augmentasi aktif)

---

## 9. Prediksi & Klasifikasi

### File Utama
- **Service:** `app/services/cnn_service/prediction.py`
- **Controller:** `app/controllers/klasifikasi_controller.py`
- **Model:** `app/models/prediksi_model.py`, `app/models/hasil_klasifikasi_cnn.py`

### Tiga Sumber Prediksi

#### A. Prediksi Tunggal (Upload Foto Manual)
- Endpoint: `POST /klasifikasi/upload`
- User memilih lokasi + foto → model memprediksi kelas
- `AMBANG_CONFIDENCE = 0.5` — prediksi di bawah ini ditandai perlu verifikasi manual
- Hasil disimpan di `HasilKlasifikasiCnn` + `DokumentasiFoto` + `PetaKerusakan`

#### B. Prediksi Massal (predict_all)
- Endpoint: via `ArsitekturConfig` → memprediksi semua foto dalam dataset
- Hasil disimpan di `PrediksiModel` (per foto)

#### C. Prediksi K-Fold Cross-Validation (predict_cv)
- Endpoint: via ArsitekturConfig dengan `pred_type='cv'`
- Setiap fold val diprediksi oleh model yang dilatih pada fold train
- Hasil dikompilasi menjadi `HasilEvaluasi` per model

### Indeks Kelas
- `indeks = tingkat_kerusakan_id - 1` (lihat `app/kelas.py`)
- Class 0 = Rusak Berat, Class 1 = Rusak Ringan, Class 2 = Sedang, Class 3 = Baik

### Confidence & Validitas
- `confidence_score` di `HasilKlasifikasiCnn`: 0..1
- `confidence` di `PrediksiModel`: sudah persen (0..100)
- `is_valid = confidence >= AMBANG_CONFIDENCE`

---

## 10. Evaluasi Model

### File Utama
- **Service:** `app/services/cnn_service/evaluation.py`
- **Model:** `app/models/evaluasi_model.py`, `app/models/hasil_evaluasi.py`
- **Metrics:** `app/services/metrics_service.py`

### Metrik

**`cv_summary(config)`** — mengagregasi hasil K-Fold CV:
- `akurasi`: rata-rata akurasi dari semua fold
- `macro_f1`: rata-rata macro F1-score dari semua fold (metrik resmi sistem)

**`HasilEvaluasi`** — hasil evaluasi per model (1 fold):
- `akurasi`, `macro_f1`, `loss`

### Display Logic di Peta
- Prioritaskan `cv_summary().macro_f1` (CV resmi) untuk config dengan `pred_type='cv'`
- Fallback ke `HasilEvaluasi` jika CV belum dijalankan
- `best_id` = config dengan `macro_f1` tertinggi

### Catatan Penting
- **Akurasi CV sistem sekitar 45%** — prediksi di bawah ambang confidence 50% ditandai perlu verifikasi manual
- Angka ini masih rendah, mencerminkan tantangan dataset kecil dan variasi kondisi citra lapangan

---

## 11. Labeling & Klasifikasi pada Peta

### File Utama
- **Controller:** `app/controllers/peta_controller.py`
- **Model:** `app/models/peta_kerusakan.py`
- **Template:** `app/templates/peta/index.html`

### Alur Data Peta

```
PetaKerusakan (table)
    ├── lokasi_id → LokasiKerusakan (latitude, longitude, nama_citra)
    ├── hasil_klasifikasi_id → HasilKlasifikasiCnn (tingkat_kerusakan_id, confidence)
    │   └── tingkat_kerusakan → warna_peta, nama_tingkat
    ├── prediksi_model → PrediksiModel → tingkat_kerusakan → warna_peta
    ├── status_pemetaan ('draft' / 'validasi' / dll.)
    └── prioritas_perbaikan
```

### Two Sources for Peta Coloring

**1. Dari Labeling K-Means (manual):**
- `PetaKerusakan` ↔ `HasilKlasifikasiCnn` ↔ `TingkatKerusakan.warna_peta`
- `label_kerusakan` → `HasilKlasifikasiCnn` → `TingkatKerusakan`
- Warna dari `app/kelas.py`: Rusak Berat=#E53E3E, Rusak Ringan=#F97316, Sedang=#F59E0B, Baik=#10B981

**2. Dari Prediksi CNN:**
- `PrediksiModel` → `LABEL[prediksi]` + `WARNA[prediksi]` (dari `app/kelas.py`)
- Endpoint `/peta/prediksi-geojson?arsitektur_id=X&filter=all/salah/&lt;kode_kelas>`

### GeoJSON Endpoints

**`/peta/geojson?status=`** — Peta dari `PetaKerusakan`:
- Menampilkan semua lokasi dengan status pemetaan tertentu
- Properti: `id`, `nama_citra`, `jenis`, `tingkat`, `warna`, `status`, `prioritas`
- Warna fallback: `#999999` jika belum diklasifikasi

**`/peta/prediksi-geojson?arsitektur_id=X&filter=all`** — Peta dari prediksi CNN:
- Menampilkan semua prediksi untuk config arsitektur tertentu
- Filter: `all` (semua), `salah` (hanya salah prediksi), atau kode kelas
- Properti: `nama_citra`, `prediksi`, `label_pred`, `aktual`, `confidence`, `warna`, `benar`

### Classifikasi pada Peta — Ringkasan

| Sumber | Tabel | Status |
|--------|-------|--------|
| Labeling manual (K-Means + "Terapkan") | `label_kerusakan` → `HasilKlasifikasiCnn` | Final, override |
| Prediksi CNN (model terlatih) | `PrediksiModel` | Probabilistik, per model |
| Klasifikasi tunggal (upload manual) | `HasilKlasifikasiCnn` | Per foto upload |

---

## 12. Workflow & Services — Arsitektur Internal

### Service Layer Overview

| Service | File | Tanggung Jawab |
|---------|------|---------------|
| `PreprocessingService` | `preprocessing_service.py` | 4-step image pipeline |
| `LabelingService` (funcs) | `labeling_service.py` | K-Means clustering pipeline |
| `label_source` (funcs) | `label_source.py` | Single source of truth untuk effective labels |
| `SplitService` | `split_service.py` | Stratified K-Fold splitting |
| `augmentation_service` (funcs) | `augmentation_service.py` | 10-transformasi offline augmentasi |
| `cnn_service.model` | `cnn_service/model.py` | Build model, augmentation layers |
| `cnn_service.dataset` | `cnn_service/dataset.py` | Load dataset K-Fold + augmentation |
| `cnn_service.training` | `cnn_service/training.py` | Train model, early stopping |
| `cnn_service.prediction` | `cnn_service/prediction.py` | predict_all, predict_cv, predict_image |
| `cnn_service.evaluation` | `cnn_service/evaluation.py` | CV summary, metrics |
| `metrics_service` | `metrics_service.py` | `cv_summary()` aggregation |
| `dedup_service` | `dedup_service.py` | Near-duplicate detection |

### Controller Routing

| Blueprint | Prefix | Endpoint Utama |
|-----------|--------|---------------|
| `peta_bp` | `/peta` | `/`, `/geojson`, `/prediksi-geojson` |
| `klasifikasi_bp` | `/klasifikasi` | `/upload`, `/hasil/<id>`, `/riwayat`, `/riwayat/hapus-semua` |
| `arsitektur_bp` | `/arsitektur` | `/`, `/form`, `/detail/<id>`, `/evaluasi`, `/gis` |
| `split_bp` | `/split` | `/new`, `/<id>` |
| `label_bp` | `/labeling` | (labeling workflow) |
| `preprocessing_bp` | `/preprocessing` | (preprocessing config) |
| `augmentasi_bp` | `/augmentasi` | (augmentation config) |
| `dashboard_bp` | `/dashboard` | (overview) |

### Data Flow Between Services

1. `label_source.label_map()` dipanggil oleh split, staleness check, batch prediction, dan dashboard — menjamin konsistensi angka label
2. `SplitService.run()` → `SplitItem` → `dataset.load_dataset()` → model training
3. `augmentation_service.jalankan()` → `HasilAugmentasi` → `dataset.load_dataset()` → training samples
4. `cnn_service.predict_image()` → `HasilKlasifikasiCnn` → `PetaKerusakan`
5. `cnn_service.predict_all()` / `predict_cv()` → `PrediksiModel` → peta overlay

---

## 13. Struktur Database

### Tabel Inti (23 tabel MySQL)

| Tabel | Deskripsi |
|-------|-----------|
| `pengguna` | User management |
| `lokasi_kerusakan` | 280 lokasi (lat, long, nama_citra) |
| `dokumentasi_foto` | 280 foto per lokasi |
| `labeling_config` | Konfigurasi K-Means (n_cluster, pca_komponen, dll.) |
| `hasil_labeling` | Run klasterisasi (jumlah_lokasi, variansi_pca, distribusi_kelas) |
| `hasil_labeling_item` | Per-lokasi: klaster, kepadatan_tepi, jarak_centroid, tingkat_kerusakan_id |
| `label_kerusakan` | Label final per lokasi (metode, cluster_id, kepadatan_tepi, jarak_centroid) |
| `tingkat_kerusakan` | 4 tingkat (Rusak Berat, Rusak Ringan, Sedang, Baik) + warna_peta |
| `preprocessing_config` | Resize, crop, norm, denoise settings |
| `hasil_preprocessing` | Per-foto per-step processed image paths |
| `augmentasi_config` | 10 transformasi parameters |
| `hasil_augmentasi` | Per-foto salinan augmentasi |
| `split_config` | K-Fold parameters |
| `split_item` | Per-foto fold_index + label_id |
| `arsitektur_config` | Model config (MobileNetV2/EfficientNetB0, lr, batch, dll.) |
| `hasil_training` | Training logs |
| `prediksi_model` | Hasil prediksi massal per arsitektur |
| `hasil_klasifikasi_cnn` | Hasil klasifikasi tunggal |
| `hasil_evaluasi` | Evaluasi per model (akurasi, macro_f1) |
| `peta_kerusakan` | Overlay peta (lokasi + hasil_klasifikasi + status) |
| `jenis_kerusakan` | Jenis kerusakan (retak, lubang, dll.) |
| `dokumentasi_foto` | Foto dokumentasi |

### Relasi Kunci
- `hasil_labeling_item.run_id` → `hasil_labeling.id` (CASCADE)
- `hasil_labeling_item.lokasi_id` → `lokasi_kerusakan.id` (CASCADE)
- `label_kerusakan.lokasi_id` → `lokasi_kerusakan.id`
- `split_item.dokumentasi_id` → `dokumentasi_foto.id`
- `prediksi_model.arsitektur_id` → `arsitektur_config.id`
- `peta_kerusakan.lokasi_id` → `lokasi_kerusakan.id`
- `peta_kerusakan.hasil_klasifikasi_id` → `hasil_klasifikasi_cnn.id`

---

## 14. Konfigurasi & Nilai Aktual

### Konfigurasi Default yang Berlaku

| Komponen | Nilai |
|----------|-------|
| Preprocessing resize | 256×256 LANCZOS, stretch |
| Preprocessing crop | 224×224 |
| Preprocessing norm | none |
| Preprocessing denoise | bilateral, ksize=3 |
| Augmentasi default | 10 layer, 3 salinan, seed=42 |
| Labeling | k=4, PCA=50, canny 50/150, random_state=42 |
| Split | StratifiedKFold, shuffle, random_state |
| Model | MobileNetV2, 224×224, lr=0.0001, batch=16, epoch=30 |
| Fine-tuning | 8 layer (MobileNetV2) / 12 (EfficientNetB0) |
| Confidence threshold | 0.5 (50%) |
| Optimizer | Adam |
| Loss | SparseCategoricalCrossentropy |

### Data Aktual di Database

- **Lokasi:** 280 (semuanya memiliki koordinat)
- **Foto:** 280 (satu per lokasi)
- **Split items:** 280
- **Hasil labeling run:** minimal 1 run selesai (belum tentu diterapkan)
- **Label kerusakan:** 0 baris sebelum "Terapkan"
- **Arsitektur configs:** minimal 1 terlatih
- **Prediksi model:** bergantung pada arsitektur yang dipilih

### Environment
- Database: MySQL (`db_cnn_jalan`), credentials di `.env`
- Flask server: PID 2340, port 5000
- Backend code changes memerlukan restart server

---

## 15. Catatan Penting & Risiko

### 1. Labeling Belum Diterapkan
`label_kerusakan` berisi 0 baris karena belum ada run yang diterapkan (endpoint "Terapkan" belum dijalankan). `label_source.label_map()` tetap bisa mengambil data dari `hasil_labeling_item` sebagai sumber utama.

### 2. Akurasi Model Rendah
Akurasi CV sekitar 45%. Ini masih di bawah harapan dan mencerminkan:
- Dataset kecil (~224-540 training samples)
- Variasi kondisi citra lapangan yang besar
- Kemungkinan overfitting pada fase fine-tuning (train acc 70%+ sementara val macet 35-45%)

### 3. Satu Config Aktif
Hanya ada **satu** preprocessing config dan **satu** augmentasi config yang aktif pada satu waktu. Ini menjamin konsistensi tapi membatasi eksperimen paralel.

### 4. Random Erasing = Patch Warna
Random Erasing (Cutout) dengan `luas_min=0.02, luas_maks=0.08` menghasilkan patch warna acak pada gambar augmentasi. Ini **sengaja** dan bukan bug — melainkan strategi regularisasi agar model tidak bergantung pada satu titik kerusakan.

### 5. Group-Aware Splitting
Semua sampel dari foto yang sama (dokumentasi_id) selalu masuk ke fold yang sama. Ini mencegah data leakage dari near-duplicate (varian tahap preprocessing dari foto yang sama).

### 6. Kode vs Template Aliases
- `tokens.css` mendefinisikan variabel CSS modern (`--surface-*`, `--ink-*`, `--rule`, `--accent`)
- Template masih merujuk legacy alias (`--c-surface`, `--c-border`, `--c-text`) melalui layer alias di `tokens.css`
- Konsistensi warna Chart.js di `detail.html` masih menggunakan hardcoded hex colors (`#EF4444`, `#38BDF8`, `#F59E0B`, `#10B981`) — disengaja untuk coding per-domain

---

*Dokumentasi ini mencakup seluruh pipeline dari foto mentah hingga prediksi di peta, termasuk preprocessing, labeling K-Means, augmentasi, split K-Fold, arsitektur CNN, training, evaluasi, dan integrasi GIS. Semua data faktual diambil dari source code dan database `db_cnn_jalan`.*
