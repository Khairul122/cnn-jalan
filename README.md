# CNN-Jalan — GIS Pemetaan Kerusakan Jalan Kota Lhokseumawe

Sistem informasi geografis (GIS) berbasis web untuk pemetaan kerusakan jalan menggunakan metode **Convolutional Neural Network (CNN)**. Dibangun dengan **Flask** (Python) menggunakan arsitektur **MVC**. Dikembangkan sebagai bagian dari skripsi (NIM 210170072).

---

## Fitur

- Manajemen data lokasi kerusakan jalan (CRUD + upload foto + mini-map Leaflet)
- Klasifikasi jenis (CRACK / POTHOLE / RUTTING) & tingkat kerusakan (Berat / Sedang / Ringan) via CNN
- Labeling SDI (Surface Distress Index) sesuai standar Bina Marga, dengan auto-estimasi dari dimensi kerusakan
- Pipeline preprocessing gambar 5 tahap: Resize → Center Crop → Normalisasi → Augmentasi → Denoise (OpenCV + Pillow)
- Split dataset Stratified K-Fold (scikit-learn) untuk persiapan training CNN, dengan distribusi kelas & export CSV
- Konfigurasi & training arsitektur CNN (MobileNetV2 / EfficientNetB0, transfer learning) dengan progress live
- Evaluasi model otomatis: confusion matrix 3×3, precision/recall/F1 per kelas, macro avg
- Prediksi GIS — mode Single (`predict_all`) dan K-Fold Cross-Validation (`predict_cv`)
- Visualisasi peta interaktif dengan **Leaflet.js** + filter status pemetaan
- Evaluasi model CNN secara manual (input metrik, tabel perbandingan)
- Autentikasi pengguna (Admin & Viewer) — Flask-Login, password bcrypt (Werkzeug)

---

## Teknologi

| Komponen | Teknologi |
|----------|-----------|
| Backend | Python 3.10+, Flask 3.0 |
| ORM | Flask-SQLAlchemy |
| Database | MySQL (utf8mb4) |
| Auth | Flask-Login |
| Migrasi DB | Flask-Migrate |
| Frontend | Bootstrap 5.3 + Tailwind CSS (Play CDN), Leaflet.js, Chart.js |
| Image processing | OpenCV, Pillow, NumPy |
| Machine Learning | TensorFlow / Keras, scikit-learn |
| Connector | PyMySQL |

---

## Persyaratan

- Python 3.10 atau lebih baru
- MySQL Server (XAMPP / standalone)
- Git (opsional)

---

## Instalasi

### 1. Clone / salin proyek

```powershell
cd "D:\Project Flask"
# Jika menggunakan git:
# git clone <repo-url> cnn-jalan
```

### 2. Buat dan aktifkan virtual environment

```powershell
cd "D:\Project Flask\cnn-jalan"

# Buat .venv
python -m venv .venv

# Aktifkan (Windows PowerShell)
.\.venv\Scripts\Activate.ps1
```

> Jika PowerShell menampilkan error _"execution policy"_, jalankan dulu:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. Install dependencies

```powershell
pip install -r requirements.txt
```

### 4. Buat database MySQL

Pastikan MySQL sudah berjalan, lalu import skema lengkap:

```powershell
mysql -u root -p < db_cnn_jalan.sql
```

Jika sudah punya database dari versi sebelumnya, jalankan migration tambahan **secara berurutan** (lihat tabel di bagian Migrasi Database).

### 5. Konfigurasi koneksi database

Edit file `config.py`, sesuaikan `SQLALCHEMY_DATABASE_URI`:

```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:PASSWORD@localhost/db_cnn_jalan'
```

Ganti `PASSWORD` dengan password MySQL Anda (kosongkan jika tidak ada).

### 6. Jalankan aplikasi

```powershell
.\.venv\Scripts\python.exe run.py
```

Buka browser: [http://127.0.0.1:5000](http://127.0.0.1:5000)

**Akun default:** `admin@gmail.com` / `12345678`

---

## Struktur Proyek

```
cnn-jalan/
├── .venv/                          # Virtual environment (tidak di-commit)
├── app/
│   ├── __init__.py                 # App factory (create_app, registrasi blueprint)
│   ├── models/                     # Model SQLAlchemy (M)
│   │   ├── pengguna.py
│   │   ├── jenis_kerusakan.py
│   │   ├── tingkat_kerusakan.py
│   │   ├── lokasi_kerusakan.py
│   │   ├── dokumentasi_foto.py
│   │   ├── hasil_klasifikasi_cnn.py
│   │   ├── peta_kerusakan.py
│   │   ├── label_kerusakan.py
│   │   ├── preprocessing_config.py
│   │   ├── hasil_preprocessing.py
│   │   ├── split_config.py / split_item.py
│   │   ├── arsitektur_config.py / hasil_training.py
│   │   ├── hasil_evaluasi.py / prediksi_model.py
│   │   └── evaluasi_model.py
│   ├── controllers/                # Blueprint / Controller (C)
│   │   ├── auth_controller.py
│   │   ├── dashboard_controller.py
│   │   ├── lokasi_controller.py
│   │   ├── klasifikasi_controller.py
│   │   ├── label_controller.py
│   │   ├── preprocessing_controller.py
│   │   ├── split_controller.py
│   │   ├── arsitektur_controller.py
│   │   ├── peta_controller.py
│   │   └── evaluasi_controller.py
│   ├── services/                   # Business logic / pipeline
│   │   ├── preprocessing_service.py
│   │   ├── split_service.py
│   │   └── cnn_service.py
│   ├── templates/                  # Template Jinja2 / View (V)
│   │   ├── base.html, components/
│   │   ├── auth/, dashboard/, lokasi/, klasifikasi/, label/
│   │   ├── preprocessing/, split/, arsitektur/, peta/, evaluasi/
│   └── static/
│       ├── css/style.css
│       ├── js/peta.js, js/toast.js
│       ├── models/                 # Model CNN terlatih (model_{id}.keras)
│       └── uploads/
│           ├── foto/               # Foto lapangan asli
│           └── preprocessed/       # Hasil preprocessing
├── config.py                       # Konfigurasi aplikasi
├── db_cnn_jalan.sql                # Skema lengkap (fresh install)
├── migrate_*.sql                   # Migration tambahan (lihat tabel di bawah)
├── seed_data.py                    # Import 280 data dari Excel + foto
├── restore_foto.py                 # Utility pemulihan foto yang terhapus
├── requirements.txt
├── run.py                          # Entry point
└── README.md
```

---

## Blueprint & URL Utama

| Blueprint | Prefix | Deskripsi |
|---|---|---|
| `auth` | `/auth` | Login, logout, register |
| `dashboard` | `/` | Dashboard, KPI & statistik realtime |
| `lokasi` | `/lokasi` | CRUD lokasi kerusakan + upload foto |
| `klasifikasi` | `/klasifikasi` | Upload foto & klasifikasi CNN |
| `label` | `/label` | Manajemen label SDI |
| `preprocessing` | `/preprocessing` | Pipeline preprocessing gambar |
| `split` | `/split` | Stratified K-Fold split dataset |
| `arsitektur` | `/arsitektur` | Konfigurasi, training, evaluasi & prediksi GIS model CNN |
| `peta` | `/peta` | Peta GIS interaktif (GeoJSON) |
| `evaluasi` | `/evaluasi` | Evaluasi model CNN manual |

---

## Mengintegrasikan Model CNN (Klasifikasi Manual)

Untuk fitur upload + klasifikasi tunggal, edit fungsi `_mock_predict()` di `app/controllers/klasifikasi_controller.py` agar memanggil model nyata:

```python
# Contoh menggunakan TensorFlow/Keras
import numpy as np
from tensorflow.keras.models import load_model
from PIL import Image

model = load_model('app/static/models/model_<id>.keras')

def _mock_predict(filepath):
    img = Image.open(filepath).resize((224, 224))
    arr = np.expand_dims(np.array(img), axis=0)
    pred = model.predict(arr)
    # kembalikan tuple: (JenisKerusakan, TingkatKerusakan, confidence_score)
    ...
```

Untuk pipeline training, evaluasi, dan prediksi GIS otomatis, lihat `app/services/cnn_service.py`
(`build_model`, `train`, `load_dataset`, `evaluate`, `predict_all`, `predict_cv`).

---

## Migrasi Database

Jalankan **berurutan** pada database yang sudah ada (setelah `db_cnn_jalan.sql`):

| File | Fungsi |
|---|---|
| `migrate_remove_kecamatan.sql` | Hapus tabel & kolom kecamatan |
| `migrate_add_preprocessing.sql` | Tambah tabel `preprocessing_config` & `hasil_preprocessing` |
| `migrate_add_split.sql` | Tambah tabel `split_config` & `split_item` + index |
| `migrate_add_arsitektur.sql` | Tambah tabel `arsitektur_config` & `hasil_training` |
| `migrate_add_hasil_evaluasi.sql` | Tambah tabel `hasil_evaluasi` |
| `migrate_add_patience.sql` | Tambah kolom `patience` di `arsitektur_config` |
| `migrate_add_prediksi_model.sql` | Tambah tabel `prediksi_model` |
| `migrate_add_pred_type.sql` | Tambah kolom `pred_type` di `arsitektur_config` |

```powershell
Get-Content migrate_add_preprocessing.sql | & mysql -u root db_cnn_jalan
```

---

## Nonaktifkan Virtual Environment

```powershell
deactivate
```

---

## Informasi Proyek

| | |
|-|-|
| **Judul** | Sistem GIS Pemetaan Kerusakan Jalan Kota Lhokseumawe Menggunakan CNN |
| **NIM** | 210170072 |
| **Database** | `db_cnn_jalan` |
| **Framework** | Flask (Python) |
| **Arsitektur** | MVC (Model–View–Controller dengan Blueprints) |
