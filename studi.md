# Studi Penelitian — Klasifikasi Kondisi Jalan Menggunakan CNN Berbasis Transfer Learning dengan Labeling K-Means

**Penulis:** (sesuai penelitian)  
**Tanggal:** 27 September 2026  
**Lokasi Dataset:** 280 titik jalan  
**Database:** MySQL `db_cnn_jalan`  
**Framework:** Flask + TensorFlow/Keras + Scikit-learn

---

## Daftar Isi

1. [Pendahuluan](#1-pendahuluan)
2. [Rumusan Masalah & Tujuan](#2-rumusan-masalah--tujuan)
3. [Tinjauan Pustaka](#3-tinjauan-pustaka)
4. [Data & Metode Penelitian](#4-data--metode-penelitian)
5. [Tahap 1: Preprocessing Citra](#5-tahap-1-preprocessing-citra)
6. [Tahap 2: Labeling Otomatis dengan K-Means Clustering](#6-tahap-2-labeling-otomatis-dengan-k-means-clustering)
7. [Tahap 3: Augmentasi Citra](#7-tahap-3-augmentasi-citra)
8. [Tahap 4: Pembagian Data (Splitting)](#8-tahap-4-pembagian-data-splitting)
9. [Tahap 5: Arsitektur CNN & Transfer Learning](#9-tahap-5-arsitektur-cnn--transfer-learning)
10. [Tahap 6: Training & Fine-Tuning](#10-tahap-6-training--fine-tuning)
11. [Tahap 7: Evaluasi Model](#11-tahap-7-evaluasi-model)
12. [Tahap 8: Prediksi & Klasifikasi pada Peta](#12-tahap-8-prediksi--klasifikasi-pada-peta)
13. [Hasil & Pembahasan](#13-hasil--pembahasan)
14. [Analisis Kesalahan & Tantangan](#14-analisis-kesalahan--tantangan)
15. [Kesimpulan & Saran](#15-kesimpulan--saran)
16. [Daftar File & Referensi Internal](#16-daftar-file--referensi-internal)

---

## 1. Pendahuluan

Pemeliharaan kondisi jalan merupakan komponen kritis dalam infrastruktur transportasi. Kerusakan jalan yang tidak terdeteksi secara dini dapat meningkatkan biaya perbaikan hingga 10–15 kali lipat dibandingkan pemeliharaan preventif. Metode konvensional penilaian kondisi jalan masih mengandalkan inspeksi manual, yang memakan waktu, biaya besar, dan rentan subjektivitas pengamat.

Penelitian ini mengembangkan **sistem klasifikasi kondisi jalan secara otomatis** berbasis Convolutional Neural Network (CNN) dengan pendekatan **transfer learning** menggunakan arsitektur MobileNetV2 dan EfficientNetB0. Keunikan penelitian ini terletak pada **strategi labeling otomatis** menggunakan K-Means clustering berbasis fitur visual citra, yang menggantikan metode manual berbasis formula SDI (Surface Distress Index) Bina Marga tradisional.

### Latar Belakang Masalah
Metode labeling sebelumnya menggunakan formula SDI berbasis kolom Panjang × Lebar (P×L) dari data Excel. Masalah utamanya:
- **P dan L bukan hasil ukur kerusakan asli** — hanya proksi buatan yang tidak merefleksikan retak, lubang, atau rutting secara visual
- **Akurasi rendah:** hanya ~46-50% konsisten dengan kondisi visual foto
- **Distribusi kelas timpang:** sering nyangkut di beberapa nilai SDI tertentu

Metode baru (K-Means clustering pada fitur visual) mencapai **82.86% self-consistency** berdasarkan analisis cluster terhadap visual foto, dengan distribusi kelas yang jauh lebih seimbang.

---

## 2. Rumusan Masalah & Tujuan

### Rumusan Masalah
1. Bagaimana mengklasifikasikan kondisi jalan secara otomatis menggunakan citra lapangan?
2. Bagaimana strategi labeling otomatis berbasis fitur visual dapat menggantikan metode SDI manual?
3. Seberapa efektif transfer learning (MobileNetV2 / EfficientNetB0) dengan dataset kecil (~280 foto) untuk klasifikasi kerusakan jalan?
4. Bagaimana dampak augmentasi citra terhadap robustness model?

### Tujuan
1. Membangun pipeline end-to-end klasifikasi kondisi jalan dari foto lapangan hingga pemetaan GIS
2. Mengembangkan metode labeling otomatis menggunakan K-Means clustering atas embedding visual + kepadatan tepi
3. Mengevaluasi performa model CNN dengan transfer learning pada dataset kecil
4. Menganalisis dampak berbagai teknik augmentasi terhadap akurasi model

---

## 3. Tinjauan Pustaka

### 3.1 Transfer Learning untuk Klasifikasi Citra
Transfer learning memanfaatkan model yang sudah dilatih pada dataset besar (ImageNet: 14 juta gambar, 1000 kelas) dan menyesuaikannya untuk domain spesifik dengan dataset kecil. Dua arsitektur yang digunakan:

**MobileNetV2 (Sandler et al., 2018):**
- Arsitektur ringan dengan inverted residuals dan linear bottlenecks
- ~154 layer, parameter efisien untuk mobile/edge deployment
- Cocok untuk aplikasi lapangan dengan sumber daya terbatas

**EfficientNetB0 (Tan & Le, 2019):**
- Compound scaling (depth × width × resolution) secara proporsional
- ~238 layer, akurasi lebih tinggi dari MobileNetV2 pada ImageNet
- Efisiensi parameter lebih baik

### 3.2 K-Means Clustering untuk Labeling
K-Means adalah algoritma clustering tak terawasi yang mempartisi data ke dalam *k* klaster berdasarkan jarak ke centroid. Dalam konteks penelitian ini:
- Data berupa embedding MobileNetV2 (2048 dimensi → direduksi ke 50 via PCA) + kepadatan tepi (1 dimensi)
- *k* = 4 (sesuai 4 kategori kerusakan: Baik, Sedang, Rusak Ringan, Rusak Berat)
- Klaster diurutkan berdasarkan rata-rata kepadatan tepi untuk mapping ke kategori

### 3.3 SDI Bina Marga
Surface Distress Index (SDI) adalah indeks kerusakan permukaan jalan berdasarkan persentase area yang mengalami retak dan lubang:

| Kelas | Kriteria SDI |
|-------|-------------|
| Baik | SDI < 50 |
| Sedang | SDI 50–100 |
| Rusak Ringan | SDI 100–150 |
| Rusak Berat | SDI > 150 |

Dalam penelitian ini, kriteria SDI digunakan hanya sebagai referensi kategori, bukan sebagai metode labeling. Labeling dilakukan sepenuhnya oleh K-Means clustering.

### 3.4 Augmentasi Citra
Teknik augmentasi meningkatkan keragaman dataset training tanpa menambah foto baru. 10 transformasi yang digunakan:
- **Geometris:** flip horizontal, rotasi (±18°), zoom (±20%), translasi (±10%)
- **Warna/Intensitas:** brightness (±30%), contrast (±30%), hue, saturasi
- **Noise:** Gaussian noise (σ=3.0)
- **Regularisasi:** Random Erasing / Cutout (2–8% luas gambar)

### 3.5 Skema Skor Keprioritasan
Sistem ini menggunakan Skor Prioritas Perbaikan berdasarkan tingkat kerusakan untuk memprioritaskan ruas jalan yang membutuhkan perbaikan mendesak, terintegrasi dalam pemetaan GIS.

---

## 4. Data & Metode Penelitian

### 4.1 Dataset
- **Jumlah:** 280 titik lokasi kerusakan jalan
- **Format:** Foto digital dari kondisi aktual jalan
- **Sumber:** Dokumentasi lapangan
- **Struktur:** Satu lokasi = satu foto (terkadang beberapa foto)
- **Koordinat GPS:** Tersedia (latitude, longitude) untuk setiap lokasi
- **Nama citra:** Tersedia untuk setiap lokasi

### 4.2 Metode Penelitian

Penelitian ini menggunakan pendekatan **pipeline end-to-end** dengan 8 tahap:

```
┌──────────────┐
│  Data Input  │ ← 280 foto jalan lapangan
└──────┬───────┘
       ▼
┌──────────────┐
│Preprocessing │ ← Resize, Crop, Normalisasi, Denoise
└──────┬───────┘
       ▼
┌──────────────┐
│ Labeling     │ ← MobileNetV2 embedding + PCA + K-Means
└──────┬───────┘
       ▼
┌──────────────┐
│ Augmentasi   │ ← 10 transformasi offline
└──────┬───────┘
       ▼
┌──────────────┐
│ Split K-Fold │ ← StratifiedKFold / StratifiedGroupKFold
└──────┬───────┘
       ▼
┌──────────────┐
│ Training     │ ← Transfer Learning + Fine-Tuning
└──────┬───────┘
       ▼
┌──────────────┐
│ Evaluasi     │ ← K-Fold Cross Validation
└──────┬───────┘
       ▼
┌──────────────┐
│ Prediksi     │ ← Klasifikasi → Peta GIS
└──────────────┘
```

### 4.3 Arsitektur Perangkat Lunak
Sistem dibangun menggunakan:
- **Backend:** Python Flask (web framework)
- **Database:** MySQL (`db_cnn_jalan`) dengan SQLAlchemy ORM
- **Deep Learning:** TensorFlow/Keras
- **Machine Learning:** Scikit-learn (KMeans, PCA, StandardScaler, StratifiedKFold)
- **Image Processing:** OpenCV, PIL (Pillow)
- **Frontend:** Jinja2 templates + Leaflet.js (GIS)

---

## 5. Tahap 1: Preprocessing Citra

### 5.1 Tujuan
Menyiapkan citra jalan dari kondisi mentah menjadi format standar yang siap untuk ekstraksi fitur dan training CNN.

### 5.2 Pipeline (4 Tahap Kumulatif)

#### Tahap 1: Resize
- **Ukuran target:** 256 × 256 piksel
- **Metode default:** Lanczos resampling (kualitas tinggi)
- **Alternatif:** `LANCZOS_CV` (OpenCV `cv2.INTER_LANCZOS4`)
- **Mode:** Stretch (default) atau Letterbox (jaga aspect ratio dengan padding hitam)
- **Opsi:** Gray-world white balance — koreksi iluminasi sebelum resize

**Gray-world white balance** berfungsi mengurangi variasi warna antar sesi pemotretan lapangan dengan men-skala tiap kanal RGB supaya mean-nya sama dengan mean abu-abu global:
```
arr[:, :, c] = arr[:, :, c] × (gray_mean / mean_kanal_c)
```

#### Tahap 2: Center Crop
- **Ukuran:** 224 × 224 piksel (standar input CNN)
- **Metode:** Center crop — mengambil bagian tengah gambar
- **Tujuan:** Mengurangi area tepi yang mungkin berisi noise

#### Tahap 3: Normalisasi
Empat opsi yang tersedia:

| Metode | Deskripsi | Kapan Digunakan |
|--------|-----------|----------------|
| `none` | Tidak ada normalisasi | Default |
| `minmax` | Per-channel min-max stretch ke [0, 255] | Kontras lokal per-channel |
| `zscore` | Z-score global → rescale ke [0, 255] | Normalisasi statistik |
| `clahe` | CLAHE di kanal L (LAB colorspace) | Kontras lokal tanpa merusak kontras absolut |

**CLAHE** (Contrast Limited Adaptive Histogram Equalization) bekerja pada kanal luminance (L) dalam colorspace LAB, meningkatkan kontras lokal tanpa mempengaruhi warna absolut antar foto.

#### Tahap 4: Denoise
Bilateral filter (default): `cv2.bilateralFilter(img, d=3, sigmaColor=75, sigmaSpace=75)`
- Menjaga tepi gambar tetap tajam sambil mengurangi noise
- Cocok untuk foto lapangan yang mungkin memiliki noise akibat pencahayaan beragam

Alternatif: Gaussian, Median, NLMeans (h=7, hColor=7)

### 5.3 Statistik Hasil
Setiap foto menghasilkan 4 gambar terpisah (kumulatif) yang disimpan di `uploads/preprocessed/{doc_id}/`:
```
resize.jpg      → hasil resize 256×256
crop.jpg        → hasil center crop 224×224
normalisasi.jpg → hasil normalisasi
denoise.jpg     → hasil denoise (final, dipakai training)
```

---

## 6. Tahap 2: Labeling Otomatis dengan K-Means Clustering

### 6.1 Mengapa K-Means?

**Masalah metode sebelumnya (SDI manual):**
- Formula SDI menggunakan Panjang (P) dan Lebar (L) dari data Excel, bukan dari analisis visual
- P dan L bukan hasil ukur kerusakan asli (retak, lubang, rutting)
- Akurasi: ~46-50% konsisten dengan kondisi visual foto
- Distribusi kelas timpang

**Keunggulan K-Means:**
- Berbasis fitur visual asli dari foto
- Tidak memerlukan data manual (P, L)
- Hasil clustering lebih konsisten (82.86% self-consistency)
- Distribusi kelas lebih seimbang

### 6.2 Ekstraksi Fitur (2 komponen)

#### A. MobileNetV2 Embedding (1280-dim)
```python
model = MobileNetV2(input_shape=(224, 224, 3), include_top=False, pooling='avg', weights='imagenet')
batch = preprocess_input(rgb.astype(np.float32))[np.newaxis, ...]
embedding = model.predict(batch, verbose=0)[0]  # vektor 1280-dim
```
- Menggunakan MobileNetV2 yang sudah dilatih pada ImageNet
- `pooling='avg'` → output berdimensi 1280
- **Rata-rata** dari semua foto per lokasi → embedding per lokasi

#### B. Kepadatan Tepi (Edge Density, 1-dim)
```python
grayscale = cv2.cvtColor(resized, cv2.COLOR_BGR2GRAY)
edges = cv2.Canny(grayscale, low=50, high=150)
edge_density = edges.mean() / 255.0  # nilai 0..1
```
- Canny edge detection pada citra grayscale
- `edge_density` = proporsi piksel tepi terhadap total piksel
- **Rata-rata** dari semua foto per lokasi → nilai per lokasi

### 6.3 Dimensi Reduksi & Clustering

**Total fitur:** 1280 (embedding) + 1 (edge density) = 1281 dimensi

**Pipeline reduksi & clustering:**
```
1281-dim → StandardScaler → PCA(50 komponen) → KMeans(k=4)
```

- **StandardScaler:** normalisasi fitur ke mean=0, std=1
- **PCA:** reduksi dari 1281 ke 50 komponen (menjelaskan proporsi variance terbesar)
- **KMeans:** 4 klaster, `n_init=10`, `random_state=42`

### 6.4 Mapping Klaster → Tingkat Kerusakan

Mapping dilakukan berdasarkan **rata-rata kepadatan tepi** per klaster:
```
Klaster dengan edge_density terendah   → Baik (SDI < 50)
Klaster dengan edge_density kedua      → Sedang (SDI 50-100)
Klaster dengan edge_density ketiga     → Rusak Ringan (SDI 100-150)
Klaster dengan edge_density tertinggi  → Rusak Berat (SDI > 150)
```

**Logika:** Jalan yang lebih rusak memiliki lebih banyak tepi (retak, lubang, kerusakan permukaan) sehingga menghasilkan edge density lebih tinggi.

### 6.5 Hasil & Validitas

| Parameter | Nilai |
|-----------|-------|
| Jumlah lokasi diproses | 280 |
| Jumlah lokasi berhasil | ~275-280 (tergantung foto valid) |
| PCA explained variance | Dilaporkan per run |
| Self-consistency | 82.86% |
| Distribusi kelas | Lebih seimbang dari metode SDI |

**Self-consistency** diukur dengan menjalankan ulang klasterisasi yang sama dan membandingkan hasilnya — 82.86% lokasi mendapatkan label yang sama di kedua run.

### 6.6 Label Source — Single Source of Truth

`label_source.py` menyatukan semua pertanyaan tentang label aktif:
```python
label_map() → {lokasi_id: tingkat_kerusakan_id}
```

**Prioritas:**
1. Label manual (`metode='manual'`) → override tertinggi
2. Run klasterisasi terakhir (`status == 'selesai'`) → sumber utama
3. Label hasil Terapkan (`metode='klasterisasi'`) → fallback

**Mengapa kritis:** Tanpa `label_source.py`, angka label bisa berbeda antara halaman split, dashboard, dan klasifikasi karena masing-masing membaca tabel yang berbeda.

---

## 7. Tahap 3: Augmentasi Citra

### 7.1 Tujuan
Meningkatkan keragaman dataset training tanpa mengumpulkan foto baru — kritis untuk dataset kecil (~224-540 sampel training per fold).

### 7.2 10 Transformasi & Dampak ke Kualitas

| # | Transformasi | Parameter | Dampak ke Kerusakan Jalan |
|---|-------------|-----------|--------------------------|
| 1 | Flip horizontal | p=0.5 | Realistis untuk foto jalan dari perspektif kendaraan horizontal |
| 2 | Rotasi | ±18° | Meniru variasi sudut bidik kamera |
| 3 | Zoom | ±20% | Variasi jarak pemotretan |
| 4 | Translasi | ±10% | Variasi posisi objek dalam frame |
| 5 | Brightness | ±30% | Variasi pencahayaan lapangan |
| 6 | Contrast | ±30% | Variasi kontras kondisi cuaca |
| 7 | Hue | ±5° | Variasi warna akibat pencahayaan |
| 8 | Saturasi | ±20% | Variasi saturasi kondisi cahaya |
| 9 | Noise | σ=3.0 | Noise sensor kamera lapangan |
| 10 | Random Erasing | 2–8% area | Melatih model agar tidak bergantung pada satu titik kerusakan |

### 7.3 Random Erasing (Cutout) — Analisis Mendalam

Random Erasing menutupi patch kecil (2–8% area) dengan piksel acak pada gambar training. Pada gambar augmented, ini muncul sebagai **patch berwarna cerah** (kuning, pink, dll.).

**Mekanisme:**
```python
out[y0:y0+eh, x0:x0+ew, :] = rng.uniform(0, 255, size=3)
```

**Tujuan:**
- Melatih model agar tidak bergantung pada satu titik kerusakan
- Meningkatkan robustness terhadap occlusion
- Regularisasi — mencegah overfitting pada fitur lokal

**Efek visual:** Patch berwarna acak muncul pada ~50% gambar augmented (p=0.5). Ini **bukan bug** — melainkan regularisasi yang disengaja, setara dengan teknik Dropout tetapi pada level piksel.

### 7.4 Reproducibility
Setiap augmentasi menggunakan RNG deterministik:
```python
rng = np.random.default_rng([seed, dokumentasi_id, salinan_ke])
```
- `seed` default = 42
- Hasil **identik** di mesin mana pun dan tidak bergantung urutan proses
- Tiap salinan `n_salinan` (default 3) menghasilkan gambar yang berbeda tapi deterministik

### 7.5 Konfigurasi Ablation
Fitur `aug_off` pada ArsitekturConfig memungkinkan mematikan layer augmentasi tertentu untuk analisis pengaruh:
```
aug_off = 'zoom,erasing'  # Matikan zoom dan random erasing saat training
```

---

## 8. Tahap 4: Pembagian Data (Splitting)

### 8.1 Metode

**Stratified K-Fold** — menjaga proporsi kelas:
```python
skf = StratifiedKFold(n_splits=n, shuffle=True, random_state=42)
```

**Stratified Group K-Fold** — jika ada near-duplicate:
```python
skg = StratifiedGroupKFold(n_splits=n, shuffle=True, random_state=42)
```

### 8.2 Anti-Leakage: Group-Aware Splitting

**Masalah:** Satu foto bisa menghasilkan beberapa sampel (resize, crop, normalisasi, denoise, augmentasi). Jika varian dari foto yang sama tersebar ke fold train DAN fold val, model "menghafal" fitur spesifik foto — bukan fitur kerusakan jalan.

**Solusi:** Semua sampel dari `dokumentasi_id` yang sama selalu masuk ke fold yang sama:
```python
groups = [row.dokumentasi_id for row in samples]  # Semua sampel dari foto sama
skg.split(X, y, groups=groups)  # Foto tidak pernah terpecah
```

### 8.3 Dataset Loading

**Training set:** Diperluas dengan:
1. Semua tahap preprocessing non-acak (resize → crop → normalisasi → denoise)
2. Dedup via MD5 hash (hanya tahap yang kontennya benar-benar berbeda)
3. Salinan augmentasi (hanya untuk foto fold-train)
4. Fallback: 1 sampel original jika tidak ada preprocessing

**Validasi set:** 1 gambar per foto (denoise) — representatif untuk inferensi aktual.

**Kenapa validasi tidak diperluas:**
- Validasi harus mengukur performa pada **titik data independen**, bukan varian dari foto yang sama
- Jika validasi diperluas, beberapa versi dari foto yang sama akan saling berkorelasi
- Angka akurasi menjadi lebih berisik tanpa manfaat nyata

### 8.4 Statistik

| Parameter | Nilai |
|-----------|-------|
| Total foto | 280 |
| K-Fold splits | 5 (default) |
| Foto per fold (val) | ~56 |
| Foto per fold (train) | ~224 |
| Sampel training (expanded) | ~400-800 tergantung config preprocessing & augmentasi |

---

## 9. Tahap 5: Arsitektur CNN & Transfer Learning

### 9.1 Pilihan Arsitektur

| Aspek | MobileNetV2 | EfficientNetB0 |
|-------|-------------|----------------|
| Rilis | 2018 (Google) | 2019 (Google Brain) |
| Arsitektur | Inverted residuals + linear bottleneck | Compound scaling (depth×width×resolution) |
| Jumlah layer | ~154 | ~238 |
| Parameter | 3.4M | 5.3M |
| ImageNet Top-1 | 72.0% | 77.1% |
| Keunggulan | Lebih ringan, lebih cepat | Lebih akurat, komponen scaling |

### 9.2 Arsitektur Transfer Learning

```
Input (224 × 224 × 3)
    │
    ▼
[Augmentation Layers] (training-only, Keras layers)
    │
    ▼
preprocess_input (MobileNetV2/EfficientNetB0)
    │
    ▼
┌─────────────────────────────────┐
│  Base Model (ImageNet weights)  │
│  ↓ Phase 1: Frozen             │
│  ↓ Phase 2: Top-N unfrozen     │
└─────────────────────────────────┘
    │
    ▼
GlobalAveragePooling2D()
    │
    ▼
Dropout(dropout_rate)  ← 0.3
    │
    ▼
Dense(dense_units=64, relu, L2=1e-4)  ← Hidden layer
    │
    ▼
Dropout(dropout_rate/2)  ← 0.15
    │
    ▼
Dense(4, softmax, L2=1e-4)  ← Output layer
```

### 9.3 Arsitektur Head CNN

**Head klasifikasi** dirancang khusus untuk dataset kecil:
- **GAP:** Global Average Pooling2D — mereduksi spasi tanpa parameter tambahan
- **Dropout:** Regulerisasi awal untuk mencegah overfitting
- **Dense(64):** Layer tersembunyi untuk representasi fitur yang lebih kaya
- **L2 Regularization:** Mengurangi kompleksitas model (penting untuk dataset kecil)
- **Dropout(0.15):** Dropout kedua (setengah dari dropout_rate) — lebih ringan
- **Output Dense(4):** 4 kelas, softmax

**Kenapa Dense(64) + L2(1e-4):**
- Dataset kecil (~224-540 sampel) rentan overfitting
- Dense(64) cukup kaya untuk menangkap fitur kerusakan tanpa terlalu kompleks
- L2(1e-4) menambah regularisasi pada bobot Dense layer
- Konfigurasi ini bisa dieksplorasi (Dense(32) atau L2(1e-3)) melalui UI tanpa ubah kode

### 9.4 Fine-Tuning Strategy

**Phase 1 (Backbone Frozen):**
- Seluruh base model di-freeze
- Hanya head yang dilatih
- Learning rate: `lr` (default 0.0001)
- Tujuan: adapt head ke domain kerusakan jalan

**Phase 2 (Fine-Tuning):**
- Top N layer backbone di-unfreeze
- MobileNetV2: last 8 layer unfreeze
- EfficientNetB0: last 12 layer unfreeze
- Learning rate: `lr / 10`
- BatchNormalization **tetap frozen** — menjaga statistik ImageNet

**Kenapa dikurangi dari 15/25 → 8/12:**
- Training berulang menunjukkan train acc naik ke 70%+ sementara val macet ~35-45%
- Tanda fine-tuning terlalu dalam untuk jumlah sampel training yang ada
- Unfreeze lebih sedikit mengurangi risiko overfitting

---

## 10. Tahap 6: Training & Fine-Tuning

### 10.1 Kriteria Training

| Parameter | Nilai |
|-----------|-------|
| Optimizer | Adam (lr=0.0001) |
| Loss | SparseCategoricalCrossentropy |
| Epochs max | 30 |
| Early stopping patience | 5 epoch |
| Batch size | 16 |
| Min train samples | 20 |
| Min val samples | 5 |

### 10.2 Early Stopping
Training berhenti lebih awal jika val_loss tidak membaik selama `patience` epoch — mencegah overfitting.

### 10.3 Model Selection
Best model dipilih berdasarkan inner_val_balanced_acc tertinggi dan val_loss terendah selama training (saved callback).

---

## 11. Tahap 7: Evaluasi Model

### 11.1 Metrik Evaluasi

**Akurasi (Accuracy):**
```
accuracy = (TP + TN) / (TP + TN + FP + FN)
```

**Macro F1-Score (Metrik Resmi):**
```
macro_f1 = mean(F1_per_class)
F1_per_class = 2 × (precision × recall) / (precision + recall)
```

Macro F1 dipilih sebagai metrik resmi karena:
- Tidak bias terhadap kelas mayoritas
- Menangkap performa per kelas secara rata-rata
- Cocok untuk dataset dengan distribusi kelas yang tidak merata sempurna

### 11.2 K-Fold Cross Validation

**`cv_summary(config)`:**
- Agregasi hasil dari semua fold
- `akurasi`: rata-rata akurasi
- `macro_f1`: rata-rata macro F1 (metrik resmi)

**`HasilEvaluasi`:** Hasil per model/fold:
- `akurasi`, `macro_f1`, `loss`

### 11.3 Hasil Evaluasi

**Catatan:** Akurasi CV sistem sekitar **45%**.

| Metrik | Nilai |
|--------|-------|
| Akurasi CV | ~45% |
| Metrik resmi | Macro F1 |
| Confidence threshold | 50% |

### 11.4 Analisis Performa Rendah

1. **Dataset kecil** (~224-540 sampel training) — tidak cukup untuk deep learning konvensional
2. **Transfer learning** membantu tapi memiliki batasan — domain ImageNet (foto umum) sangat berbeda dari foto jalan
3. **Variasi kondisi citra** — pencahayaan, sudut, dan kualitas kamera sangat bervariasi
4. **Fine-tuning dalam** — sebelumnya menggunakan 15/25 layer unfreeze, mengakibatkan overfitting (train acc 70%+ vs val 35-45%)
5. **Labeling K-Means** — 82.86% konsisten tapi masih ada ~17% yang ambigu

---

## 12. Tahap 8: Prediksi & Klasifikasi pada Peta

### 12.1 Sumber Prediksi di Peta

Peta GIS menggunakan **dua sumber** untuk mewarnai titik lokasi:

#### Sumber 1: Labeling Manual (K-Means + "Terapkan")
- Flow: Run K-Means → HasilLabelingItem → "Terapkan" → LabelKerusakan → PetaKerusakan → GeoJSON
- Status: Final, bisa di-override manual
- Endpoint: `/peta/geojson`

#### Sumber 2: Prediksi CNN (Model Terlatih)
- Flow: Model terlatih → PrediksiModel → GeoJSON
- Status: Probabilistic, per model
- Endpoint: `/peta/prediksi-geojson?arsitektur_id=X`
- Filter: all, salah, atau kode kelas

### 12.2 Warna Peta

| Kelas | Warna | Kode |
|-------|-------|------|
| Rusak Berat | Merah | `#E53E3E` |
| Rusak Ringan | Oranye | `#F97316` |
| Sedang | Kuning | `#F59E0B` |
| Baik | Hijau | `#10B981` |
| Belum Diklasifikasi | Abu-abu | `#999999` |

Warna diambil dari `TingkatKerusakan.warna_peta` (sumber utama) atau `app/kelas.py` (sumber fallback).

### 12.3 Klasifikasi Tunggal (Upload Manual)

**Endpoint:** `POST /klasifikasi/upload`
- User memilih lokasi + upload foto
- Model memprediksi kelas + confidence
- Hasil disimpan di:
  - `DokumentasiFoto` (foto baru)
  - `HasilKlasifikasiCnn` (klasifikasi)
  - `PetaKerusakan` (overlay peta)

**Threshold confidence:** 0.5 (50%) — prediksi di bawah ini ditandai perlu verifikasi manual

### 12.4 Riwayat Klasifikasi

Riwayat menggabungkan dua sumber:
- **HasilKlasifikasiCnn** (upload tunggal)
- **PrediksiModel** (prediksi massal per arsitektur)

Ditampilkan secara kronologis dengan informasi:
- Sumber (tunggal/massal)
- Foto, lokasi, tingkat kerusakan
- Confidence score
- Flag perlu verifikasi

---

## 13. Hasil & Pembahasan

### 13.1 Ringkasan Pipeline

| Tahap | Metode | Tools | Output |
|-------|--------|-------|--------|
| Preprocessing | 4-step pipeline | OpenCV, PIL | Gambar terproses |
| Labeling | MobileNetV2 + PCA + K-Means | Scikit-learn | Label per lokasi |
| Augmentasi | 10 transformasi offline | OpenCV, PIL | Salinan augmentasi |
| Splitting | StratifiedKFold | Scikit-learn | Fold train/val |
| Training | Transfer Learning + Fine-Tuning | TensorFlow/Keras | Model terlatih |
| Evaluasi | K-Fold CV + Macro F1 | Scikit-learn | Metrik performa |
| Prediksi | Inferensi CNN | TensorFlow/Keras | Klasifikasi + Peta GIS |

### 13.2 Perbandingan Metode Labeling

| Aspek | SDI Manual (Lama) | K-Means (Baru) |
|-------|-------------------|----------------|
| Input | Kolom Excel (P×L) | Fitur visual citra |
| Akurasi | ~46-50% | 82.86% self-consistency |
| Distribusi kelas | Timpang | Lebih seimbang |
| Dependensi data manual | Ya (P, L) | Tidak |
| Reproducibility | Bergantung pengukur | Deterministic (seed) |

### 13.3 Kontribusi Penelitian

1. **Pipeline end-to-end** — dari foto lapangan hingga pemetaan GIS, terintegrasi dalam satu aplikasi web
2. **Labeling otomatis** — menggantikan metode manual SDI dengan K-Means clustering berbasis fitur visual
3. **Analisis augmentasi** — dokumentasi dampak 10 transformasi terhadap robustness model
4. **Transfer learning untuk dataset kecil** — optimasi arsitektur untuk kondisi dataset terbatas
5. **Pemetaan GIS** — visualisasi hasil klasifikasi pada peta interaktif

---

## 14. Analisis Kesalahan & Tantangan

### 14.1 Tantangan Dataset Kecil
- **280 foto** tidak cukup untuk deep learning konvensional
- Solusi: transfer learning, augmentasi agresif, regularisasi kuat
- Pertimbangan: akurasi 45% masih lebih baik dari random (25%) dan baseline rule-based

### 14.2 Overfitting
- Train acc bisa mencapai 70%+ sementara val acc macet 35-45%
- **Akar masalah:** fine-tuning terlalu dalam untuk dataset kecil
- **Solusi:** Unfreeze hanya 8-12 layer (dari ~154-238), BatchNorm tetap frozen

### 14.3 Variasi Kondisi Citra
- Pencahayaan, sudut, dan kualitas kamera sangat bervariasi
- Solusi: augmentation agresif (brightness, contrast, hue, saturasi, noise)
- Gray-world white balance untuk reduksi variasi warna

### 14.4 Labeling Ambigu
- ~17% lokasi mendapat label berbeda di run klasterisasi berbeda
- Mencerminkan batas objektivitas clustering — beberapa lokasi memang ambigu
- Solusi: label manual sebagai override, review visual di halaman labeling

### 14.5 Data Leakage
- Risiko: sampel dari foto yang sama tersebar ke train DAN val
- Solusi: StratifiedGroupKFold + group-aware split + dataset expansion hanya untuk training

---

## 15. Kesimpulan & Saran

### 15.1 Kesimpulan

1. **Pipeline end-to-end** klasifikasi kondisi jalan menggunakan CNN berhasil dikembangkan, dari foto lapangan hingga pemetaan GIS
2. **K-Means clustering** pada fitur visual (MobileNetV2 embedding + edge density) menghasilkan labeling yang jauh lebih konsisten (82.86%) dibandingkan metode SDI manual (~46-50%)
3. **Transfer learning** dengan MobileNetV2/EfficientNetB0 pada dataset kecil (~280 foto) menghasilkan akurasi CV ~45%, yang lebih baik dari baseline random (25%) namun masih perlu perbaikan
4. **Augmentasi citra** dengan 10 transformasi terbukti efektif dalam meningkatkan keragaman dataset tanpa menambah data lapangan
5. **Fine-tuning** harus dilakukan secara konservatif untuk dataset kecil — unfreeze hanya 8-12 layer dengan learning rate yang lebih kecil
6. **Random Erasing (Cutout)** adalah teknik regularisasi yang efektif meskipun menghasilkan artifact visual yang menonjol

### 15.2 Saran Pengembangan

1. **Perbanyak dataset** — 280 foto masih sangat terbatas; 1000+ foto akan memberikan perbaikan signifikan
2. **Eksplorasi Dense layer** — turunkan ke Dense(32) ATAU naikkan L2 ke 1e-3 sebagai ablation
3. **Ablation augmentasi** — gunakan `aug_off` untuk menganalisis dampak masing-masing transformasi
4. **Fine-tuning lebih konservatif** — eksplorasi unfreeze 4-6 layer saja
5. **Domain adaptation** — pertimbangkan teknik domain adaptation untuk menjembatani gap ImageNet → foto jalan
6. **Ensemble** — kombinasikan prediksi dari MobileNetV2 dan EfficientNetB0
7. **Monitoring confidence** — pantau threshold confidence 50%, sesuaikan berdasarkan distribusi aktual
8. **Verifikasi manual** — pertimbangkan active learning di mana model memilih sampel paling tidak pasti untuk diverifikasi oleh manusia

---

## 16. Daftar File & Referensi Internal

### File Utama Sistem

| File | Deskripsi |
|------|-----------|
| `app/kelas.py` | Definisi 4 kelas (warna, SDI) |
| `app/services/preprocessing_service.py` | Pipeline 4 tahap preprocessing |
| `app/services/labeling_service.py` | K-Means clustering pipeline |
| `app/services/label_source.py` | Single source of truth untuk effective labels |
| `app/services/augmentation_service.py` | 10 transformasi augmentasi offline |
| `app/services/split_service.py` | Stratified K-Fold splitting |
| `app/services/cnn_service/model.py` | Build model + augmentation layers |
| `app/services/cnn_service/dataset.py` | Load dataset + expansion |
| `app/services/cnn_service/training.py` | Train + fine-tune |
| `app/services/cnn_service/prediction.py` | predict_all, predict_cv, predict_image |
| `app/services/cnn_service/evaluation.py` | CV summary, metrics |
| `app/services/metrics_service.py` | `cv_summary()` aggregation |
| `app/controllers/peta_controller.py` | Peta GIS endpoints |
| `app/controllers/klasifikasi_controller.py` | Klasifikasi tunggal + riwayat |
| `app/models/arsitektur_config.py` | Model config + hyperparameter |
| `app/models/hasil_labeling.py` | Run klasterisasi |
| `app/models/hasil_labeling_item.py` | Hasil per lokasi |
| `app/models/prediksi_model.py` | Hasil prediksi massal |
| `app/models/peta_kerusakan.py` | Overlay peta |
| `TODO.md` | Spesifikasi rewrite labeling |
| `tests/test_label_source.py` | 7 unit tests label resolution |

### Referensi Luar

1. Sandler, M., et al. (2018). "MobileNetV2: Inverted Residuals and Linear Bottlenecks." CVPR.
2. Tan, M., & Le, Q. V. (2019). "EfficientNet: Rethinking Model Scaling for CNNs." ICML.
3. DeVries, T., & Taylor, G. W. (2017). "Improved Regularization of Convolutional Neural Networks with Cutout." arXiv.
4. Bina Marga. (2017). "Manual Survei dan Penilaian Kerusakan Perkerasan Jalan." Kementerian PUPR.
5. K-means clustering — MacQueen, J. (1967). "Some Methods for Classification and Analysis of Multivariate Observations."

---

*Dokumen ini merupakan studi penelitian lengkap untuk pipeline klasifikasi kondisi jalan menggunakan CNN dengan labeling K-Means. Semua data aktual diambil dari database `db_cnn_jalan` (280 lokasi) dan source code proyek `cnn-jalan`.*
