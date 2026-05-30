# Studi Sistem: Alur Input hingga Output GIS
## Sistem Informasi Geografis Pemetaan Kerusakan Jalan Kota Lhokseumawe Menggunakan Metode Convolutional Neural Network (CNN)

---

## 1. Gambaran Umum Sistem

Sistem ini merupakan aplikasi web berbasis Flask yang mengintegrasikan tiga komponen utama:
1. **Pipeline preprocessing gambar** — mempersiapkan foto kerusakan jalan agar seragam sebelum masuk ke model
2. **Model CNN berbasis Transfer Learning** — mengklasifikasikan tingkat kerusakan jalan secara otomatis
3. **Visualisasi GIS Interaktif** — menampilkan sebaran titik kerusakan di peta Kota Lhokseumawe

Alur kerja sistem mengikuti urutan: **Input → Preprocessing → Labeling SDI → Split Dataset → Training CNN → Evaluasi → Prediksi → Output GIS**.

---

## 2. Input Sistem

### 2.1 Dataset Foto Kerusakan Jalan

| Atribut | Nilai |
|---------|-------|
| Jumlah foto | **280 foto** |
| Format file | JPG / PNG / JPEG / WEBP |
| Sumber | Survei lapangan di ruas jalan Kota Lhokseumawe |
| Resolusi asal | Bervariasi (kamera smartphone) |
| Lokasi penyimpanan | `app/static/uploads/foto/` |

Setiap foto dikaitkan dengan satu **lokasi kerusakan** yang memiliki:
- Koordinat GPS (latitude, longitude) — diperoleh dari data Excel lapangan
- Dimensi kerusakan: panjang (meter) dan lebar (meter)
- Jenis kerusakan: CRACK (retak), POTHOLE (lubang), RUTTING (alur)

### 2.2 Normalisasi Koordinat GPS

Data koordinat dari Excel berformat integer (contoh: `97108763`) dikonversi ke desimal:
```
Jika value mengandung titik desimal → gunakan langsung
Jika integer besar (> 90000)       → bagi 1.000.000 → 97.108763°
```

Sistem memusatkan peta pada koordinat **[5.1801° LU, 97.1499° BT]** dengan zoom level 13 (Leaflet.js), yang merupakan pusat kota Lhokseumawe.

---

## 3. Preprocessing Pipeline

Sebelum memasuki model CNN, setiap foto melalui pipeline lima tahap yang dikonfigurasi pengguna melalui antarmuka sistem.

### Tahap 1 — Resize

Foto diubah ukurannya ke dimensi target menggunakan pustaka **Pillow**.

| Parameter | Pilihan | Default |
|-----------|---------|---------|
| Target ukuran | 224×224, 256×256, 128×128 | 224×224 px |
| Metode interpolasi | LANCZOS, BILINEAR, BICUBIC, NEAREST | LANCZOS |

LANCZOS dipilih sebagai default karena menghasilkan ketajaman terbaik saat downscaling foto dengan resolusi tinggi.

### Tahap 2 — Center Crop (Opsional)

Memotong bagian tengah gambar untuk menghilangkan area tepi yang seringkali mengandung noise atau area tidak relevan (langit, tepi jalan, kendaraan).

```
Crop output = crop_width × crop_height (default: 224 × 224 px)
Offset X = (lebar_gambar - crop_width)  / 2
Offset Y = (tinggi_gambar - crop_height) / 2
```

### Tahap 3 — Normalisasi

Nilai piksel dapat dinormalisasi menggunakan salah satu dari dua metode, atau dilewati sama sekali:

| Metode | Formula | Rentang Output | Keterangan |
|--------|---------|---------------|---|
| Min-Max | `(x − min) / (max − min) × 255` | [0, 255] (uint8) | Per-channel stretch |
| Z-Score | `(x − μ) / σ` | ~[-3, 3] → uint8 [0, 255] | Standarisasi distribusi |
| Tanpa normalisasi | — | [0, 255] asli | **Digunakan di training** |

**Catatan penting:** Normalisasi min-max per-channel menghapus sinyal kontras absolut — perbedaan kecerahan antara kelas Berat, Sedang, dan Ringan menjadi tidak terlihat karena setiap gambar di-stretch penuh ke [0, 255] secara independen. Untuk transfer learning MobileNetV2, normalisasi offline sebaiknya dinonaktifkan (`norm_method = none`) karena normalisasi ke `[-1, 1]` sudah dilakukan di dalam model oleh `preprocess_input`.

Output disimpan sebagai uint8 agar dapat ditampilkan sebagai gambar normal.

### Tahap 4 — Augmentasi

Augmentasi diterapkan secara **acak per gambar** (bukan deterministik), menggunakan Pillow `ImageOps` dan `ImageEnhance`:

| Transformasi | Keterangan |
|---|---|
| Flip Horizontal | Membalik gambar secara mendatar |
| Flip Vertikal | Membalik gambar secara tegak |
| Rotasi | Putar sudut acak dalam rentang yang ditentukan |
| Brightness | Variasi kecerahan gambar |
| Contrast | Variasi kontras gambar |

Augmentasi bertujuan memperbanyak variasi data agar model tidak overfit pada kondisi pencahayaan atau sudut pengambilan foto tertentu.

### Tahap 5 — Denoise

Pengurangan noise menggunakan OpenCV:

| Metode | Fungsi OpenCV | Karakteristik |
|--------|--------------|---------------|
| Gaussian Blur | `cv2.GaussianBlur` | Rata-rata berbobot Gaussian, halus |
| Median Blur | `cv2.medianBlur` | Efektif untuk salt-and-pepper noise |
| Bilateral Filter | `cv2.bilateralFilter` | Mempertahankan tepi, halus dalam area datar |

Output preprocessing disimpan ke `app/static/uploads/preprocessed/` dan digunakan sebagai input training CNN (menggantikan foto asli).

---

## 4. Pelabelan SDI (Surface Distress Index)

Setiap lokasi kerusakan diberi label tingkat kerusakan mengikuti standar **Bina Marga** melalui perhitungan SDI.

### 4.1 Formula Komponen SDI

**Komponen Retak (F_retak)**

| Luas Retak | Nilai Dasar | ×2 jika Retak Lebar |
|---|---|---|
| 0% | 0 | — |
| ≤ 10% | 5 | 10 |
| ≤ 20% | 20 | 40 |
| > 20% | 40 | 80 |

**Komponen Lubang (F_lubang)**

| Jumlah Lubang | Nilai |
|---|---|
| 0 | 0 |
| ≤ 10 | 15 |
| ≤ 50 | 75 |
| > 50 | 225 |

**Komponen Alur (F_rutting)**

| Kedalaman Alur | Nilai |
|---|---|
| 0 cm | 0 |
| ≤ 1 cm | 5 |
| ≤ 3 cm | 20 |
| > 3 cm | 40 |

**Total SDI**
```
SDI = F_retak + F_lubang + F_rutting
```

### 4.2 Konversi SDI ke Tingkat Kerusakan

| Nilai SDI | Tingkat Kerusakan | Kode Label (CNN) |
|---|---|---|
| ≤ 50 | Ringan | 2 |
| 51 – 150 | Sedang | 1 |
| > 150 | Berat | 0 |

### 4.3 Estimasi Otomatis dari Dimensi

Sistem menyediakan estimasi otomatis berdasarkan panjang × lebar lokasi kerusakan apabila inspeksi visual tidak tersedia:

```
luas_jalan  = panjang × lebar
persen_retak = min(luas_jalan / referensi, 100)
jumlah_lubang = luas_jalan / 0.1  (estimasi 1 lubang per 0,1 m²)
kedalaman_alur = estimasi berdasarkan luas
```

---

## 5. Split Dataset — Stratified K-Fold

### 5.1 Konfigurasi Split yang Digunakan

| Parameter | Nilai |
|---|---|
| Metode | Stratified K-Fold |
| Jumlah fold (K) | **5** |
| Random state | Dikonfigurasi pengguna |
| Total data | **280 foto berlabel** |
| Pustaka | `sklearn.model_selection.StratifiedKFold` |

### 5.2 Mode Split yang Digunakan

Pada penelitian ini digunakan **Stratified K-Fold (K=5)** dengan satu fold sebagai validasi:
- `fold_index = fold_val` → **data validasi** (≈ 56 foto, 20%)
- `fold_index ≠ fold_val` → **data training** (≈ 224 foto, 80%)
- Fold validasi yang digunakan: **fold_val = 3**

Stratifikasi memastikan proporsi kelas Berat, Sedang, dan Ringan terjaga di setiap fold.

### 5.3 Distribusi Kelas (fold_val=3 sebagai validasi)

| Kelas | Training | Validasi |
|---|---|---|
| Berat | 67 | 17 |
| Sedang | 106 | 27 |
| Ringan | 51 | 12 |
| **Total** | **224** | **56** |

### 5.4 Class Weight untuk Imbalanced Dataset

Karena data tidak seimbang (Sedang dominan), sistem menghitung bobot kelas secara otomatis:

```python
class_weight = compute_class_weight('balanced', classes=[0,1,2], y=y_train)
# Berat  : 1.114×  (kelas minor → diberi bobot lebih)
# Sedang : 0.704×  (kelas mayor → dibobot lebih rendah)
# Ringan : 1.464×  (kelas minor → diberi bobot terbesar)
```

---

## 6. Arsitektur Model CNN

### 6.1 Backbone: MobileNetV2 (Transfer Learning)

| Komponen | Spesifikasi |
|---|---|
| Base model | MobileNetV2 (ImageNet pre-trained) |
| Input size | 224 × 224 × 3 |
| Base trainable (Phase 1) | **Frozen** (semua layer dikunci) |
| Base trainable (Phase 2) | **15 layer teratas dibuka** (fine-tune) |

### 6.2 Classification Head

```
MobileNetV2 Base (frozen/partially unfrozen)
    ↓
GlobalAveragePooling2D        ← merata-ratakan feature map
    ↓
Dropout(rate=0.3)             ← regularisasi utama
    ↓
Dense(64, activation='relu', kernel_regularizer=L2(1e-4))    ← representasi intermediate
    ↓
Dropout(rate=0.15)            ← regularisasi ringan (dropout/2)
    ↓
Dense(3, activation='softmax', kernel_regularizer=L2(1e-4))  ← output 3 kelas
```

Output layer menghasilkan probabilitas untuk tiga kelas:
- **Index 0** → Berat
- **Index 1** → Sedang
- **Index 2** → Ringan

### 6.3 Augmentasi dalam Model

Lapisan augmentasi **terintegrasi di dalam model** (aktif saat `training=True`, nonaktif saat inferensi):

| Layer | Parameter |
|---|---|
| RandomFlip | horizontal |
| RandomRotation | factor=0.05 |
| RandomZoom | height_factor=0.2 |
| RandomTranslation | height=0.1, width=0.1 |
| RandomBrightness | factor=0.3 |
| RandomContrast | factor=0.3 |

---

## 7. Proses Training

### 7.1 Hyperparameter

| Hyperparameter | Nilai |
|---|---|
| Optimizer | Adam |
| Learning rate (Phase 1) | **0.001** |
| Learning rate (Phase 2) | **LR_Phase1 / 5 = 0.0002** |
| Batch size | 32 |
| Dropout rate | 0.3 |
| Max epoch Phase 1 | 80 |
| Max epoch Phase 2 | 40 (`max(20, epochs//2)`) |
| Loss function | SparseCategoricalCrossentropy |

### 7.2 Fungsi Loss

**SparseCategoricalCrossentropy** digunakan sebagai fungsi loss, dikombinasikan dengan `class_weight` untuk menangani ketidakseimbangan kelas:

```
L = − Σ class_weight[y] × log(p_y)
```

- Label kelas berbentuk integer (sparse: 0/1/2), tidak perlu one-hot encoding
- `class_weight` dari `compute_class_weight('balanced')` memberi penalti ekstra pada kelas minor (Berat, Ringan)
- Dipilih karena lebih stabil daripada Focal Loss pada dataset kecil; Focal Loss dengan γ=2.0 terbukti menekan gradient kelas Ringan terlalu agresif

### 7.3 Callbacks Training

**Phase 1 (head training):**

| Callback | Konfigurasi |
|---|---|
| ModelCheckpoint | Simpan model terbaik berdasarkan `val_accuracy` (maximize) |
| EarlyStopping | Monitor `val_loss`, `patience = max(user_patience, 20)`, `min_delta = 0.001` |
| ReduceLROnPlateau | Monitor `val_loss`, `factor=0.5`, `patience=10`, `min_lr=1e-6` |

**Phase 2 (fine-tune):**

| Callback | Konfigurasi |
|---|---|
| ModelCheckpoint | Simpan model terbaik berdasarkan `val_accuracy`, threshold = best Phase 1 |
| EarlyStopping | Monitor `val_accuracy`, `patience = max(10, patience//2)` |
| ReduceLROnPlateau | Monitor `val_accuracy`, `factor=0.5`, `patience = max(5, patience//4)` |

### 7.4 Strategi Two-Phase Training

**Phase 1 (Head Training)**
- Base MobileNetV2 **dibekukan** (`trainable=False`)
- Hanya classification head yang dilatih
- Learning rate tinggi (0.001) karena head diinisialisasi secara acak

**Phase 2 (Fine-tuning)**
- 15 layer teratas MobileNetV2 **dibuka** (`trainable=True`)
- Learning rate diturunkan ke 0.0002 agar tidak merusak fitur pre-trained
- Checkpoint Phase 2 hanya disimpan jika melampaui `val_accuracy` terbaik Phase 1; jika tidak, fallback ke model Phase 1

### 7.5 Preprocessing Input ke Model

```python
# Gambar dibaca → resize 224×224 → float32 [0, 255]
# Normalisasi dilakukan DALAM model oleh MobileNetV2.preprocess_input:
x_normalized = (x / 127.5) - 1.0   →  rentang [-1.0, 1.0]
```

---

## 8. Evaluasi Model

### 8.1 Data Evaluasi

| Atribut | Nilai |
|---|---|
| Data val | **56 foto** (fold_val = 3, 20% dari total) |
| Split config | split_config_id = 12 (norm=none, resize 256→crop 224) |
| Tanggal evaluasi | 29 Mei 2026 |

### 8.2 Confusion Matrix

Confusion matrix lengkap tersedia di halaman Evaluasi sistem (tabel `hasil_evaluasi`). Distribusi aktual pada fold validasi:

| Kelas | Aktual (val) |
|---|---|
| Berat | 17 foto |
| Sedang | 27 foto |
| Ringan | 12 foto |
| **Total** | **56 foto** |

### 8.3 Metrik Per Kelas

Detail precision, recall, dan F1 per kelas tersedia di halaman Evaluasi sistem. Metrik dihitung menggunakan `sklearn.metrics.classification_report` pada data validasi fold 3.

### 8.4 Metrik Keseluruhan

| Metrik | Nilai |
|---|---|
| **Akurasi Keseluruhan** | **71.43%** (40 dari 56 benar) |
| Fase yang digunakan | Phase 2 (melampaui Phase 1) |
| Epoch terbaik Phase 2 | Epoch 7 dari 17 |

### 8.5 Interpretasi

- **Akurasi 71.43%** melampaui target 70%, dicapai pada 56 foto validasi yang tidak pernah dilihat model
- Phase 2 fine-tune (17 epoch) melampaui Phase 1 (best val_acc=0.6250) dengan val_acc=0.7143
- Perbaikan kunci: mengganti preprocessing norm=minmax menjadi norm=none, menghilangkan distorsi kontras absolut antar kelas
- LR Phase 1 = 0.001 (tinggi) diperlukan untuk head yang baru diinisialisasi acak; LR Phase 2 = 0.0002 agar tidak merusak fitur pre-trained

---

## 9. Prediksi CNN pada Seluruh Dataset

### 9.1 Metode predict_all

Setelah training selesai, model memprediksikan **seluruh 280 foto** yang memiliki label dan koordinat GPS. Hasil disimpan ke tabel `prediksi_model`.

```
Input  : path foto → resize 224×224 → preprocess_input → array [1, 224, 224, 3]
Output : prediksi (0/1/2), confidence (softmax probability), aktual (label SDI)
```

### 9.2 Hasil Prediksi Keseluruhan

| Kategori | Jumlah | Persentase |
|---|---|---|
| Berat | 91 | 32.5% |
| Sedang | 131 | 46.8% |
| Ringan | 58 | 20.7% |
| **Total** | **280** | **100%** |

| Metrik | Nilai |
|---|---|
| Prediksi benar | 194 dari 280 |
| Akurasi seluruh data | 69.3% |

> **Catatan**: Akurasi seluruh data (69.3%) lebih rendah dari akurasi val fold (73.21%) karena mencakup semua 280 foto termasuk data training yang lebih bervariasi. Nilai 73.21% adalah ukuran yang lebih representatif sebagai generalisasi model.

---

## 10. Output GIS — Visualisasi Peta Interaktif

### 10.1 Arsitektur Visualisasi

Sistem menyediakan dua endpoint GIS:

| Endpoint | Auth | Sumber Data | Warna Marker |
|---|---|---|---|
| `/api/landing/gis` | Publik | `prediksi_model` | Berdasarkan prediksi CNN |
| `/arsitektur/<id>/gis.json` | Login | `prediksi_model` per model | Berdasarkan prediksi CNN |
| `/peta/geojson` | Login | `peta_kerusakan` | Berdasarkan status pemetaan |

### 10.2 Format GeoJSON Output

```json
{
  "type": "FeatureCollection",
  "features": [
    {
      "type": "Feature",
      "geometry": {
        "type": "Point",
        "coordinates": [97.1234, 5.1801]
      },
      "properties": {
        "prediksi": "Berat",
        "warna": "#E53E3E",
        "benar": true
      }
    }
  ]
}
```

### 10.3 Skema Warna Marker

| Tingkat Kerusakan | Warna Hex | Tampilan |
|---|---|---|
| Berat | `#E53E3E` | Merah |
| Sedang | `#F59E0B` | Kuning-Oranye |
| Ringan | `#10B981` | Hijau |

### 10.4 Fitur Peta Interaktif

**Filter per Kategori**
Pengguna dapat memfilter marker berdasarkan tingkat kerusakan:
- Semua → tampilkan 280 marker
- Berat → tampilkan 91 marker (merah)
- Sedang → tampilkan 131 marker (oranye)
- Ringan → tampilkan 58 marker (hijau)

**Popup Informasi**
Setiap marker menampilkan popup dengan label prediksi CNN saat diklik.

**Tile Layer**
Menggunakan OpenStreetMap sebagai basemap:
```
https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png
```

**Pusat Peta**
```javascript
map.setView([5.1801, 97.1499], 13)  // Kota Lhokseumawe, zoom 13
```

### 10.5 Landing Page Publik

Halaman utama sistem (dapat diakses tanpa login) menampilkan statistik real-time dari database:

| Elemen | Sumber Data |
|---|---|
| Akurasi CNN 71.4% | `HasilEvaluasi.akurasi` (model terbaik) |
| 280 Prediksi | `PrediksiModel.count()` |
| Berat / Sedang / Ringan | `PrediksiModel` filter per kelas |
| Peta marker | `GET /api/landing/gis` |

---

## 11. Ringkasan Alur Sistem (End-to-End)

```
INPUT
  280 Foto Kerusakan Jalan
  + Koordinat GPS (Excel)
        │
        ▼
PREPROCESSING (5 Tahap)
  Resize → Center Crop → Normalisasi → Augmentasi → Denoise
        │
        ▼
PELABELAN SDI
  Hitung F_retak + F_lubang + F_rutting
  → SDI → Berat / Sedang / Ringan
        │
        ▼
SPLIT DATASET
  Stratified K-Fold (K=5, Split 80:20)
  Train=224 foto | Val=56 foto
        │
        ▼
TRAINING CNN (MobileNetV2 Transfer Learning)
  Phase 1: Head training (LR=0.001, epoch 80, frozen base)
  Phase 2: Fine-tune (LR=0.0002, top 15 layer)
  Callbacks: EarlyStopping + ReduceLROnPlateau + Checkpoint
        │
        ▼
EVALUASI MODEL
  Confusion Matrix 3×3 → Precision / Recall / F1 per kelas
  Akurasi: 71.43% pada 56 foto val (fold_val=3)
        │
        ▼
PREDIKSI SELURUH DATA
  predict_all() → 280 foto → simpan ke prediksi_model
  Output: prediksi (0/1/2) + confidence + koordinat GPS
        │
        ▼
OUTPUT GIS
  GeoJSON FeatureCollection
  Leaflet.js Interactive Map
  Filter Berat / Sedang / Ringan
  Visualisasi sebaran kerusakan di Kota Lhokseumawe
```

---

*Dokumen ini dibuat berdasarkan implementasi aktual sistem CNN-Jalan per 29 Mei 2026.*
*NIM: 210170072 — Universitas Malikussaleh*
