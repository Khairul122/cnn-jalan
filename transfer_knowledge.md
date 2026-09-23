# Transfer Knowledge
## Sistem GIS Pemetaan Kerusakan Jalan â€” CNN Lhokseumawe

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
| F_retak | 0% retak | 0 | â€” |
| | â‰¤ 10% | 5 | Ã—2 jika retak lebar |
| | â‰¤ 20% | 20 | Ã—2 jika retak lebar |
| | > 20% | 40 | Ã—2 jika retak lebar |
| F_lubang | 0 lubang | 0 | â€” |
| | â‰¤ 10 lubang | 15 | â€” |
| | â‰¤ 50 lubang | 75 | â€” |
| | > 50 lubang | 225 | â€” |
| F_rutting | 0 cm | 0 | â€” |
| | â‰¤ 1 cm | 5 | â€” |
| | â‰¤ 3 cm | 20 | â€” |
| | > 3 cm | 40 | â€” |

**Klasifikasi tingkat kerusakan berdasarkan SDI:**

| SDI | Tingkat | Label Kelas CNN |
|---|---|---|
| â‰¤ 50 | Ringan | 2 |
| 51 â€“ 150 | Sedang | 1 |
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
| Input | 224 Ã— 224 Ã— 3 px, float32 |
| Normalisasi input | `(x / 127.5) âˆ’ 1.0` â†’ [-1, 1] (di dalam model, bukan offline) |
| Head | GAP â†’ Dropout(0.3) â†’ Dense(64, relu, L2) â†’ Dropout(0.15) â†’ Dense(3, softmax) |
| Output | Probabilitas 3 kelas: Berat / Sedang / Ringan |

#### 2.2 Konfigurasi Training Terbaik (arsitektur_id=102)

| Hyperparameter | Phase 1 | Phase 2 |
|---|---|---|
| Learning rate | 0.001 | 0.0002 (LR_P1 / 5) |
| Optimizer | Adam | Adam |
| Batch size | 32 | 32 |
| Max epoch | 80 | 40 (`max(20, epochs//2)`) |
| Dropout | 0.3 | 0.3 |
| Frozen layers | Semua base | 15 layer teratas dibuka |
| Loss | SparseCategoricalCrossentropy | SparseCategoricalCrossentropy |
| EarlyStopping monitor | val_loss, patience=20 | val_accuracy, patience=max(10, p//2) |
| ReduceLROnPlateau | val_loss, patience=10, factor=0.5 | val_accuracy, patience=max(5, p//4) |

#### 2.3 Formula Class Weight

Untuk menangani ketidakseimbangan kelas:
```python
class_weight = sklearn.utils.compute_class_weight(
    class_weight='balanced',
    classes=[0, 1, 2],
    y=y_train
)
# Hasil (fold_val=3, split_config=12): Berat=1.114, Sedang=0.704, Ringan=1.464
# Nilai ini berubah per fold karena distribusi training berubah
```

#### 2.4 Fungsi Loss: SparseCategoricalCrossentropy

```python
loss = tf.keras.losses.SparseCategoricalCrossentropy()
# dikombinasikan dengan class_weight saat model.fit()
```

- Label integer langsung (0/1/2), tidak perlu one-hot encoding
- `class_weight` diterapkan saat `model.fit(..., class_weight={0:1.114, 1:0.704, 2:1.464})`
- Lebih stabil dari Focal Loss pada dataset kecil â€” Focal Loss Î³=2.0 terbukti menekan gradient kelas Ringan terlalu agresif sehingga recall Ringan jatuh

---

### 3. Pengetahuan Metrik Evaluasi

#### 3.1 Definisi Metrik

| Metrik | Formula |
|---|---|
| Precision | `TP / (TP + FP)` |
| Recall | `TP / (TP + FN)` |
| F1-Score | `2 Ã— (Precision Ã— Recall) / (Precision + Recall)` |
| Akurasi | `(TPâ‚ + TPâ‚‚ + TPâ‚ƒ) / Total` |
| Macro Avg | Rata-rata aritmetika metrik per kelas (tanpa pembobotan) |

#### 3.2 Distribusi Data Validasi (fold_val=3)

| Kelas | Support |
|---|---|
| Berat | 17 foto |
| Sedang | 27 foto |
| Ringan | 12 foto |
| **Total** | **56 foto** |

Confusion matrix detail tersedia di halaman Evaluasi sistem (tabel `hasil_evaluasi`, arsitektur_id=102).

#### 3.3 Hasil Akurasi

| Ukuran | Nilai | Data |
|---|---|---|
| **Akurasi 5-fold CV MobileNetV2** | **48,9% ± 4,5** | 280 foto, 5 fold |
| Baseline kelas mayoritas | 42,9% | pembanding wajib |

#### 3.4 Perbedaan Akurasi Val vs Akurasi Seluruh Data

| Ukuran | Nilai | Data |
|---|---|---|
| Akurasi 5-fold CV | 48,9% ± 4,5 | metrik utama generalisasi |
| Akurasi predict_all | Lihat sistem | 280 foto (semua data) |

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
# Jika tersedia gambar preprocessed â†’ gunakan
# Jika tidak â†’ fallback ke foto asli
LEFT JOIN hasil_preprocessing ON (dokumentasi_id, config_id)
```

Ini memastikan model dilatih dengan gambar yang sudah bersih dan seragam.

---

### 5. Pengetahuan Teknis GIS

#### 5.1 Koordinat Sistem

- **Sistem koordinat**: WGS84 (EPSG:4326)
- **Format GeoJSON**: `[longitude, latitude]` (X, Y)
- **Format Leaflet**: `[latitude, longitude]` (Y, X) â†’ **urutan terbalik dari GeoJSON**
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
Berat  â†’ #E53E3E (merah)
Sedang â†’ #F59E0B (oranye)
Ringan â†’ #10B981 (hijau)
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
    â† dokumentasi_foto (path foto)
        â† prediksi_model (hasil CNN: prediksi, aktual, confidence)
        â† hasil_preprocessing (gambar yang diproses)
        â† split_item (penugasan ke fold)
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

Dataset hanya berisi 280 foto â€” jauh di bawah ribuan yang biasanya diperlukan ResNet. MobileNetV2 dirancang untuk dataset ringan dan inferensi cepat; kompleksitas parameternya lebih kecil sehingga risiko overfitting pada 224 sampel training lebih rendah. VGG terlalu berat untuk dataset sekecil ini.

#### 1.2 Mengapa Menambah Dense(64) di Antara Head?

Versi awal head langsung dari GAP â†’ Dense(3). Ini menghasilkan head yang terlalu dangkal; model tidak memiliki kapasitas untuk mempelajari representasi intermediate antara 1280 fitur MobileNetV2 dan 3 kelas output. Menambah Dense(64) + L2 regularisasi memberi model "ruang berpikir" tanpa menambah risiko overfitting secara signifikan. Dense(64) dipilih karena dataset hanya 224 sampel dan membantu memperkecil risiko overfitting.

#### 1.3 Mengapa Fine-tune Hanya 15 Layer Teratas?

Percobaan dengan membuka 30 layer (awal) mengakibatkan overfitting karena jumlah parameter yang di-fine-tune terlalu besar untuk 224 sampel. Membuka 15 layer teratas adalah kompromi: cukup untuk mengadaptasi fitur level tinggi (tekstur permukaan jalan) tanpa merusak fitur level rendah (tepi, warna) yang sudah dipelajari dari ImageNet.

---

### 2. Kesalahan Kritis dan Pelajarannya

#### 2.1 Learning Rate Phase 1 yang Salah

**Kesalahan**: Training kedua menggunakan `LR = 0.0001` untuk Phase 1 â†’ akurasi stagnan di 53.57% meski training berjalan 112 epoch.

**Pelajaran**: Phase 1 melatih head yang baru diinisialisasi secara acak. Head ini membutuhkan LR yang cukup besar (0.001) agar gradien bisa mendorong bobot jauh dari nilai random. LR 0.0001 membuat head belajar sangat lambat dan terjebak di local minimum.

**Aturan praktis**: LR Phase 1 = 10Ã— LR Phase 2. Jangan turunkan LR Phase 1 hanya karena Phase 2 butuh LR rendah â€” kedua fase memiliki kebutuhan yang sangat berbeda.

#### 2.2 Focal Loss yang Menekan Kelas Ringan

**Kesalahan**: Versi awal menggunakan Focal Loss dengan gamma=2.0 â†’ recall Ringan di bawah 40%.

**Pelajaran**: Focal Loss gamma=2 secara agresif mengurangi gradient dari contoh yang sudah diprediksi dengan confidence tinggi. Pada kelas Ringan yang sedikit (51 training), mayoritas sampel Ringan mendapat gradient kecil karena model cepat "yakin" Ringan adalah Sedang. Solusinya: ganti ke SparseCategoricalCrossentropy + class_weight â€” lebih stabil dan terbukti memberikan hasil lebih baik.

#### 2.3 Normalisasi Min-Max Menghancurkan Sinyal Kontras

**Kesalahan**: Preprocessing config awal menggunakan `norm_method=minmax` per-channel â†’ akurasi stagnan di sekitar 62â€“67.86% meski hyperparameter sudah dioptimalkan.

**Pelajaran**: Normalisasi min-max per-channel melakukan `stretch` setiap channel ke [0, 255] secara independen per gambar. Ini menghilangkan perbedaan kecerahan absolut antar foto â€” gambar aspal rusak berat dengan area gelap luas terlihat mirip dengan kerusakan ringan setelah stretch. Transfer learning MobileNetV2 mengandalkan sinyal absolut ini karena fitur ImageNet-nya dilatih dengan gambar yang mempertahankan kontras asli. Solusinya: nonaktifkan normalisasi offline (`norm_method=none`) dan biarkan `preprocess_input` model yang normalize ke `[-1, 1]` di dalam pipeline.

**Catatan historis**: Eksperimen norm=none pernah menghasilkan angka lebih tinggi pada satu fold, tetapi tidak boleh menggantikan metrik utama 5-fold CV. Status terbaru tetap 48,9% ± 4,5 dan belum mencapai target 70%.

#### 2.4 Preprocessing Tidak Konsisten antara Training dan Inferensi

**Kesalahan**: `predict_all()` versi awal menggunakan foto asli, bukan foto preprocessed. Model dilatih dengan gambar preprocessed, namun diprediksi dengan gambar asli â†’ distribusi input berbeda.

**Pelajaran**: Preprocessing bukan hanya "peningkatan kualitas" tetapi bagian dari **distribusi input yang dipelajari model**. Jika training menggunakan gambar preprocessed, inferensi harus menggunakan preprocessing yang identik.

#### 2.5 EarlyStopping Terlalu Agresif

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

#### 3.2 Mengapa Hasil CV Belum Cukup untuk Klaim 70%

Pada dataset 280 foto dengan 3 kelas tidak seimbang, baseline kelas mayoritas adalah 42,9%. Hasil 48,9% ± 4,5 hanya sedikit di atas baseline dan belum cukup untuk klaim kesiapan produksi atau target 70%.

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

#### 4.4 Pilihan fold_val=3 vs K-Fold Penuh

Meski sistem mendukung K-Fold penuh via `predict_cv`, penelitian ini menggunakan satu fold sebagai validasi (fold_val=3) karena:
- Dataset hanya 280 foto; evaluasi K-Fold penuh membutuhkan training 5Ã— model yang berbeda
- Satu fold validasi dengan stratifikasi sudah cukup representatif untuk menunjukkan kemampuan generalisasi
- Fold 3 dipilih karena distribusi kelas-nya seimbang (Berat=17, Sedang=27, Ringan=12) dibanding fold lain
- Skema ini memungkinkan sistem `predict_cv` diperluas ke full K-Fold di masa depan tanpa mengubah skema data

---

### 5. Pelajaran Transfer untuk Proyek Serupa

#### 5.1 Yang Bisa Langsung Direplikasi

- Formula SDI Bina Marga dan skema 3-kelas (Berat/Sedang/Ringan) berlaku untuk semua jalan di Indonesia
- Arsitektur head CNN (GAP â†’ Dropout â†’ Dense(64) â†’ Dropout(d/2) â†’ Dense(3)) terbukti efektif untuk dataset kecil < 500 foto
- Konfigurasi training (LR=0.001, batch=32, patience=20, class_weight) dapat menjadi titik awal yang baik

#### 5.2 Yang Perlu Disesuaikan

- **Class weight** harus dihitung ulang dari distribusi data baru; jangan pakai nilai `1.114 / 0.704 / 1.464` secara literal â€” nilai ini berubah per fold
- **Jumlah layer fine-tune** (15 untuk MobileNetV2) bisa perlu dikurangi jika dataset lebih kecil atau ditingkatkan jika lebih besar
- **Koordinat peta** harus diperbarui sesuai kota/wilayah penelitian baru

#### 5.3 Hambatan Terbesar yang Diantisipasi

| Hambatan | Dampak | Mitigasi |
|---|---|---|
| Dataset terlalu kecil (< 200 foto) | Model tidak konvergen | Tambah augmentasi, kurangi fine-tune layer |
| Kelas sangat tidak seimbang (> 1:5) | Recall kelas minor â†’ 0% | Kombinasi class weight + oversampling |
| Kualitas foto lapangan rendah | Fitur tidak bisa diekstrak | Tambah tahap denoise dan normalisasi kontras |
| Koordinat GPS tidak akurat | Marker peta meleset | Validasi manual koordinat sebelum import |

---

### 6. Insight tentang Evaluasi yang Jujur

Satu pelajaran yang tidak tertulis di mana pun tetapi kritis: **akurasi tinggi pada data training bukan indikator keberhasilan model**. Sistem ini sengaja dirancang untuk:

1. Evaluasi (`HasilEvaluasi`) hanya mengukur **val fold** â€” data yang tidak pernah dilihat selama training
2. `predict_all` yang berjalan pada semua 280 foto sengaja dibedakan akurasinya dari `HasilEvaluasi`, bukan dicampur
3. Confusion matrix per kelas ditampilkan secara eksplisit, bukan hanya angka akurasi tunggal â€” karena akurasi tunggal pada dataset tidak seimbang bisa menyesatkan

Model harus dinilai dari prediksi out-of-fold. Untuk status terakhir, angka utama adalah 5-fold CV 48,9% ± 4,5; akurasi tinggi pada data training atau mode Single tidak boleh dipakai sebagai klaim generalisasi.

---

*Dokumen ini merekam pengetahuan yang diperoleh selama pengembangan sistem CNN-Jalan per 29 Mei 2026.*
*NIM: 210170072 â€” Universitas Malikussaleh*





