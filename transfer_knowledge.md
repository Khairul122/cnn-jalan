# Transfer Knowledge
## Sistem GIS Pemetaan Kerusakan Jalan — CNN Lhokseumawe

---

## Bagian I: Explicit Knowledge

*Pengetahuan yang dapat didokumentasikan, direplikasi, dan dipindahkan secara langsung melalui teks, formula, kode, dan angka.*

---

### 1. Pengetahuan Domain: Standar Bina Marga

#### 1.1 Formula SDI (Surface Distress Index)

Metode penilaian kondisi perkerasan jalan berdasarkan Pedoman Bina Marga:

```
SDI = F_retak + F_lubang + F_rutting
```

| Komponen | Kondisi | Nilai | Modifikasi |
|---|---|---|---|
| F_retak | 0% retak | 0 | — |
| | ≤ 10% | 5 | ×2 jika retak lebar |
| | ≤ 20% | 20 | ×2 jika retak lebar |
| | > 20% | 40 | ×2 jika retak lebar |
| F_lubang | 0 lubang | 0 | — |
| | ≤ 10 lubang | 15 | — |
| | ≤ 50 lubang | 75 | — |
| | > 50 lubang | 225 | — |
| F_rutting | 0 cm | 0 | — |
| | ≤ 1 cm | 5 | — |
| | ≤ 3 cm | 20 | — |
| | > 3 cm | 40 | — |

**Klasifikasi tingkat kerusakan berdasarkan SDI:**

| SDI | Tingkat | Label Kelas CNN |
|---|---|---|
| ≤ 50 | Ringan | 2 |
| 51 – 150 | Sedang | 1 |
| > 150 | Berat | 0 |

#### 1.2 Jenis Kerusakan Jalan

| Kode | Nama | Deskripsi |
|---|---|---|
| CRACK | Retak | Retakan pada permukaan aspal, dapat memanjang atau melebar |
| POTHOLE | Lubang | Lubang berlubang pada permukaan jalan |
| RUTTING | Alur | Deformasi permanen berbentuk cekungan memanjang mengikuti jejak roda |

---

### 2. Pengetahuan Arsitektur CNN

#### 2.1 Spesifikasi Model (Konfigurasi Final)

| Parameter | Nilai |
|---|---|
| Backbone | MobileNetV2 (ImageNet weights) |
| Input | 224 × 224 × 3 px, float32 |
| Normalisasi input | `(x / 127.5) − 1.0` → [-1, 1] |
| Head | GAP → Dropout(0.3) → Dense(128, relu, L2) → Dropout(0.15) → Dense(3, softmax) |
| Output | Probabilitas 3 kelas: Berat / Sedang / Ringan |

#### 2.2 Konfigurasi Training Terbaik

| Hyperparameter | Phase 1 | Phase 2 |
|---|---|---|
| Learning rate | 0.001 | 0.0002 |
| Optimizer | Adam | Adam |
| Batch size | 32 | 32 |
| Max epoch | 80 | 50 |
| Dropout | 0.3 | 0.3 |
| Frozen layers | Semua base | 15 layer teratas dibuka |
| Loss | Focal Loss (γ=2) | Focal Loss (γ=2) |
| EarlyStopping patience | 20 | 20 |
| ReduceLROnPlateau factor | 0.5 | 0.5 |

#### 2.3 Formula Class Weight

Untuk menangani ketidakseimbangan kelas:
```python
class_weight = sklearn.utils.compute_class_weight(
    class_weight='balanced',
    classes=[0, 1, 2],
    y=y_train
)
# Hasil: Berat=1.114, Sedang=0.698, Ringan=1.493
```

#### 2.4 Focal Loss

```
FL(p_t) = −α_t × (1 − p_t)^γ × log(p_t)
```
- `γ = 2.0`: faktor fokus — mengurangi bobot contoh yang sudah diprediksi benar dengan confidence tinggi
- `α_t`: class weight per kelas (dari `compute_class_weight`)
- Digunakan karena dataset kecil dan tidak seimbang

---

### 3. Pengetahuan Metrik Evaluasi

#### 3.1 Definisi Metrik

| Metrik | Formula |
|---|---|
| Precision | `TP / (TP + FP)` |
| Recall | `TP / (TP + FN)` |
| F1-Score | `2 × (Precision × Recall) / (Precision + Recall)` |
| Akurasi | `(TP₁ + TP₂ + TP₃) / Total` |
| Macro Avg | Rata-rata aritmetika metrik per kelas (tanpa pembobotan) |

#### 3.2 Confusion Matrix Model Terbaik (56 data val)

```
                  Prediksi
              Berat   Sedang   Ringan
Aktual Berat  [ 14       2        1  ]
       Sedang [  5      19        2  ]
       Ringan [  1       4        8  ]
```

#### 3.3 Hasil Metrik Lengkap

| Kelas | Precision | Recall | F1 | Support |
|---|---|---|---|---|
| Berat | 70.00% | **82.35%** | 75.68% | 17 |
| Sedang | 76.00% | 73.08% | 74.51% | 26 |
| Ringan | 72.73% | 61.54% | 66.67% | 13 |
| **Macro** | 72.91% | 72.32% | 72.28% | 56 |
| **Overall** | — | — | — | **73.21%** |

#### 3.4 Perbedaan Akurasi Val vs Akurasi Seluruh Data

| Ukuran | Nilai | Data |
|---|---|---|
| Akurasi val fold | 73.21% | 56 foto (tidak dilihat saat training) |
| Akurasi predict_all | 69.3% | 280 foto (semua data) |

Akurasi val fold adalah ukuran yang lebih valid untuk kemampuan generalisasi model.

---

### 4. Pengetahuan Pipeline Preprocessing

#### 4.1 Urutan Tahap dan Pustaka

| Tahap | Pustaka | Fungsi Utama |
|---|---|---|
| Resize | Pillow `Image.resize()` | Seragamkan dimensi input |
| Center Crop | Pillow `Image.crop()` | Fokus ke area tengah, buang tepi |
| Normalisasi | NumPy | Standarisasi rentang nilai piksel |
| Augmentasi | Pillow `ImageOps`, `ImageEnhance` | Perbanyak variasi data |
| Denoise | OpenCV | Kurangi noise untuk ketajaman fitur |

#### 4.2 Prioritas Gambar Saat Training

```python
# Jika tersedia gambar preprocessed → gunakan
# Jika tidak → fallback ke foto asli
LEFT JOIN hasil_preprocessing ON (dokumentasi_id, config_id)
```

Ini memastikan model dilatih dengan gambar yang sudah bersih dan seragam.

---

### 5. Pengetahuan Teknis GIS

#### 5.1 Koordinat Sistem

- **Sistem koordinat**: WGS84 (EPSG:4326)
- **Format GeoJSON**: `[longitude, latitude]` (X, Y)
- **Format Leaflet**: `[latitude, longitude]` (Y, X) → **urutan terbalik dari GeoJSON**
- **Pusat peta**: `[5.1801, 97.1499]`, zoom 13

#### 5.2 Format GeoJSON Endpoint

```json
{
  "type": "FeatureCollection",
  "features": [{
    "type": "Feature",
    "geometry": { "type": "Point", "coordinates": [97.xxxx, 5.xxxx] },
    "properties": { "prediksi": "Berat", "warna": "#E53E3E", "benar": true }
  }]
}
```

#### 5.3 Skema Warna Marker

```
Berat  → #E53E3E (merah)
Sedang → #F59E0B (oranye)
Ringan → #10B981 (hijau)
```

#### 5.4 Perbedaan Dua Endpoint GIS

| Endpoint | Data Sumber | Warna | Akses |
|---|---|---|---|
| `/api/landing/gis` | `prediksi_model` (CNN) | Tingkat prediksi | Publik |
| `/peta/geojson` | `peta_kerusakan` | Status pemetaan | Login |

Kedua endpoint berbeda secara semantik: satu menampilkan **hasil prediksi CNN**, satunya menampilkan **status verifikasi lapangan**.

---

### 6. Pengetahuan Database

#### 6.1 Relasi Kunci untuk GIS

```
lokasi_kerusakan (GPS)
    ← dokumentasi_foto (path foto)
        ← prediksi_model (hasil CNN: prediksi, aktual, confidence)
        ← hasil_preprocessing (gambar yang diproses)
        ← split_item (penugasan ke fold)
```

#### 6.2 Tabel prediksi_model

| Kolom | Tipe | Keterangan |
|---|---|---|
| `prediksi` | INT | 0=Berat, 1=Sedang, 2=Ringan |
| `aktual` | INT | Label SDI sesungguhnya (bisa NULL jika tidak berlabel) |
| `confidence` | FLOAT | Probabilitas kelas tertinggi dari softmax |
| `pred_type` | VARCHAR | `single` (predict_all) atau `cv` (K-Fold CV) |

---

---

## Bagian II: Tacit Knowledge

*Pengetahuan yang diperoleh dari pengalaman langsung, percobaan yang gagal, intuisi teknis, dan keputusan desain yang tidak selalu tertulis dalam dokumentasi resmi.*

---

### 1. Pemilihan Arsitektur Model

#### 1.1 Mengapa MobileNetV2, Bukan ResNet atau VGG?

Dataset hanya berisi 280 foto — jauh di bawah ribuan yang biasanya diperlukan ResNet. MobileNetV2 dirancang untuk dataset ringan dan inferensi cepat; kompleksitas parameternya lebih kecil sehingga risiko overfitting pada 224 sampel training lebih rendah. VGG terlalu berat untuk dataset sekecil ini.

#### 1.2 Mengapa Menambah Dense(128) di Antara Head?

Versi awal head langsung dari GAP → Dense(3). Ini menghasilkan head yang terlalu dangkal; model tidak memiliki kapasitas untuk mempelajari representasi intermediate antara 1280 fitur MobileNetV2 dan 3 kelas output. Menambah Dense(128) + L2 regularisasi memberi model "ruang berpikir" tanpa menambah risiko overfitting secara signifikan.

#### 1.3 Mengapa Fine-tune Hanya 15 Layer Teratas?

Percobaan dengan membuka 30 layer (awal) mengakibatkan overfitting karena jumlah parameter yang di-fine-tune terlalu besar untuk 224 sampel. Membuka 15 layer teratas adalah kompromi: cukup untuk mengadaptasi fitur level tinggi (tekstur permukaan jalan) tanpa merusak fitur level rendah (tepi, warna) yang sudah dipelajari dari ImageNet.

---

### 2. Kesalahan Kritis dan Pelajarannya

#### 2.1 Learning Rate Phase 1 yang Salah

**Kesalahan**: Training kedua menggunakan `LR = 0.0001` untuk Phase 1 → akurasi stagnan di 53.57% meski training berjalan 112 epoch.

**Pelajaran**: Phase 1 melatih head yang baru diinisialisasi secara acak. Head ini membutuhkan LR yang cukup besar (0.001) agar gradien bisa mendorong bobot jauh dari nilai random. LR 0.0001 membuat head belajar sangat lambat dan terjebak di local minimum.

**Aturan praktis**: LR Phase 1 = 10× LR Phase 2. Jangan turunkan LR Phase 1 hanya karena Phase 2 butuh LR rendah — kedua fase memiliki kebutuhan yang sangat berbeda.

#### 2.2 Focal Loss yang Menekan Kelas Ringan

**Kesalahan**: Versi awal menggunakan Focal Loss dengan gamma=2.0 tanpa class weight → recall Ringan di bawah 30%.

**Pelajaran**: Focal Loss gamma=2 secara agresif mengurangi gradient dari contoh yang sudah diprediksi dengan confidence tinggi. Pada kelas Ringan yang sedikit (50 training), mayoritas sampel Ringan mendapat gradient kecil karena model cepat "yakin" Ringan adalah Sedang. Solusinya: gabungkan Focal Loss + class weight, bukan pilih salah satu.

#### 2.3 Preprocessing Tidak Konsisten antara Training dan Inferensi

**Kesalahan**: `predict_all()` versi awal menggunakan foto asli, bukan foto preprocessed. Model dilatih dengan gambar preprocessed, namun diprediksi dengan gambar asli → distribusi input berbeda.

**Pelajaran**: Preprocessing bukan hanya "peningkatan kualitas" tetapi bagian dari **distribusi input yang dipelajari model**. Jika training menggunakan gambar preprocessed, inferensi harus menggunakan preprocessing yang identik.

#### 2.4 EarlyStopping Terlalu Agresif

**Kesalahan**: EarlyStopping dengan `patience=5` menghentikan training di epoch 30-an meskipun model belum konvergen optimal. `val_loss` sering naik-turun pada dataset kecil karena variance tinggi.

**Pelajaran**: Pada dataset kecil, `val_loss` sangat noisy. Patience minimum 20 diperlukan agar model punya kesempatan melewati fase "plateau sementara" yang sering terjadi saat LR turun via ReduceLROnPlateau.

---

### 3. Intuisi tentang Dataset Kecil

#### 3.1 Tanda-tanda Model Bermasalah pada Dataset Kecil

Saat bekerja dengan ~280 foto dan 3 kelas tidak seimbang, kenali tanda-tanda ini:

- **`val_loss` turun tetapi `val_acc` datar**: Model belajar probabilitas yang lebih terkalibrasi, bukan kelas yang benar. Tidak selalu buruk, tetapi monitor keduanya.
- **Perbedaan besar `train_acc` dan `val_acc` (> 15%)**: Overfitting. Tingkatkan dropout atau kurangi layer yang di-fine-tune.
- **Recall satu kelas mendekati 0%**: Model "menyerah" pada kelas tersebut. Cek class weight dan pastikan kelas ini terwakili di setiap batch.
- **Phase 2 tidak melampaui Phase 1**: Lumrah jika Phase 1 sudah cukup baik. Fallback ke Phase 1 adalah keputusan yang benar, bukan kegagalan.

#### 3.2 Mengapa Akurasi 73% Sudah Bermakna di Sini

Pada dataset 280 foto dengan 3 kelas tidak seimbang, baseline acak hanya menghasilkan ~33-38% (tergantung distribusi). Model dengan recall Berat 82% secara praktis berarti sistem bisa mendeteksi jalan rusak berat dengan handal — ini relevan secara langsung untuk prioritas perbaikan infrastruktur.

---

### 4. Keputusan Desain Sistem yang Tidak Tertulis di Kode

#### 4.1 Endpoint GIS Publik Terpisah

Semua endpoint GIS awal dilindungi `@login_required`. Keputusan membuat `/api/landing/gis` sebagai endpoint publik terpisah (bukan menghapus dekorator dari endpoint yang ada) diambil karena:
1. Endpoint publik hanya mengembalikan data minimal (prediksi + koordinat), tanpa path foto atau data sensitif
2. Endpoint internal tetap aman dan bisa dikembangkan dengan data lebih lengkap
3. Pemisahan concern: landing page tidak perlu tahu tentang detail internal sistem

#### 4.2 Mengapa Standalone Template, Bukan Extends base.html

Landing page tidak di-extend dari `base.html` karena `base.html` memuat sidebar, topbar, dan aset CSS/JS yang dirancang untuk pengguna yang sudah login. Memuat semua itu untuk pengunjung anonim akan membebani halaman dan menampilkan elemen navigasi yang tidak relevan. Standalone template juga memudahkan desain visual yang berbeda (light theme vs dark sidebar).

#### 4.3 Mengapa Tidak Pakai Motion.js CDN

Motion.js (Framer Motion vanilla) versi 11 dari CDN tidak mengekspor `animate` sebagai named export di bundle ESM. Mengandalkan CDN pihak ketiga untuk animasi kritis berisiko: URL bisa berubah, cache browser CDN tidak terjamin, dan bundle size lebih besar dari yang dibutuhkan. Vanilla JS dengan `IntersectionObserver` + `requestAnimationFrame` menghasilkan animasi identik dengan dependensi nol.

#### 4.4 Pilihan Split 80:20 vs K-Fold Penuh

Meski sistem mendukung K-Fold penuh, penelitian ini menggunakan Split 80:20 (fold_index 0 dan 1 dari K=5) karena:
- Dataset hanya 280 foto; evaluasi K-Fold penuh membutuhkan training 5× model yang berbeda
- Split 80:20 dengan stratifikasi sudah cukup representatif untuk menunjukkan kemampuan generalisasi
- Menggunakan fold_index=1 sebagai val memungkinkan sistem `predict_cv` diperluas ke full K-Fold di masa depan tanpa mengubah skema data

---

### 5. Pelajaran Transfer untuk Proyek Serupa

#### 5.1 Yang Bisa Langsung Direplikasi

- Formula SDI Bina Marga dan skema 3-kelas (Berat/Sedang/Ringan) berlaku untuk semua jalan di Indonesia
- Arsitektur head CNN (GAP → Dropout → Dense(128) → Dropout(d/2) → Dense(3)) terbukti efektif untuk dataset kecil < 500 foto
- Konfigurasi training (LR=0.001, batch=32, patience=20, class_weight) dapat menjadi titik awal yang baik

#### 5.2 Yang Perlu Disesuaikan

- **Class weight** harus dihitung ulang dari distribusi data baru; jangan pakai nilai `1.114 / 0.698 / 1.493` secara literal
- **Jumlah layer fine-tune** (15 untuk MobileNetV2) bisa perlu dikurangi jika dataset lebih kecil atau ditingkatkan jika lebih besar
- **Koordinat peta** harus diperbarui sesuai kota/wilayah penelitian baru

#### 5.3 Hambatan Terbesar yang Diantisipasi

| Hambatan | Dampak | Mitigasi |
|---|---|---|
| Dataset terlalu kecil (< 200 foto) | Model tidak konvergen | Tambah augmentasi, kurangi fine-tune layer |
| Kelas sangat tidak seimbang (> 1:5) | Recall kelas minor → 0% | Kombinasi class weight + oversampling |
| Kualitas foto lapangan rendah | Fitur tidak bisa diekstrak | Tambah tahap denoise dan normalisasi kontras |
| Koordinat GPS tidak akurat | Marker peta meleset | Validasi manual koordinat sebelum import |

---

### 6. Insight tentang Evaluasi yang Jujur

Satu pelajaran yang tidak tertulis di mana pun tetapi kritis: **akurasi tinggi pada data training bukan indikator keberhasilan model**. Sistem ini sengaja dirancang untuk:

1. Evaluasi (`HasilEvaluasi`) hanya mengukur **val fold** — data yang tidak pernah dilihat selama training
2. `predict_all` yang berjalan pada semua 280 foto sengaja dibedakan akurasinya dari `HasilEvaluasi`, bukan dicampur
3. Confusion matrix per kelas ditampilkan secara eksplisit, bukan hanya angka akurasi tunggal — karena akurasi tunggal pada dataset tidak seimbang bisa menyesatkan

Model yang menghasilkan akurasi 73.21% di sini artinya: dari 56 foto yang belum pernah dilihat, 41 diklasifikasikan dengan benar. Ini lebih bermakna daripada akurasi 95% pada data training.

---

*Dokumen ini merekam pengetahuan yang diperoleh selama pengembangan sistem CNN-Jalan per 25 Mei 2026.*
*NIM: 210170072 — Universitas Malikussaleh*
