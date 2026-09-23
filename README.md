# CNN-Jalan â€” GIS Pemetaan Kerusakan Jalan Kota Lhokseumawe

Sistem informasi geografis (GIS) berbasis web untuk pemetaan kerusakan jalan menggunakan metode **Convolutional Neural Network (CNN)**. Dibangun dengan **Flask** (Python) menggunakan arsitektur **MVC**. Dikembangkan sebagai bagian dari skripsi (NIM 210170072).

---

## Fitur

- Manajemen data lokasi kerusakan jalan (CRUD + upload foto + mini-map Leaflet)
- Klasifikasi tingkat kerusakan (Berat / Sedang / Ringan) via CNN
- Labeling SDI (Surface Distress Index) sesuai standar Bina Marga, dengan auto-estimasi dari dimensi kerusakan
- Pipeline preprocessing gambar: Resize → Center Crop → Normalisasi → Denoise (OpenCV + Pillow); augmentasi hanya aktif saat training model
- Split dataset Stratified K-Fold (scikit-learn) untuk persiapan training CNN, dengan distribusi kelas & export CSV
- Konfigurasi & training arsitektur CNN (MobileNetV2 / EfficientNetB0, transfer learning) dengan progress live
- Evaluasi model otomatis: confusion matrix 3Ã—3, precision/recall/F1 per kelas, macro avg
- Prediksi GIS â€” mode Single (`predict_all`) dan K-Fold Cross-Validation (`predict_cv`)
- Visualisasi peta interaktif dengan **Leaflet.js** + filter status pemetaan
- Evaluasi model CNN secara manual (input metrik, tabel perbandingan)
- Autentikasi pengguna (Admin & Viewer) â€” Flask-Login, password bcrypt (Werkzeug)

---

## Teknologi

| Komponen | Teknologi |
|----------|-----------|
| Backend | Python 3.12, Flask 3.0 |
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

- Python 3.12
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

Pastikan MySQL sudah berjalan dan database kosong `db_cnn_jalan` sudah dibuat. Dump lengkap `database/dump SQL lama` sudah dihapus karena berisi skema/data lama; gunakan migration SQL di `scripts/` sesuai urutan pada bagian Migrasi Database.

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
â”œâ”€â”€ .venv/                          # Virtual environment (tidak di-commit)
â”œâ”€â”€ app/
â”‚   â”œâ”€â”€ __init__.py                 # App factory (create_app, registrasi blueprint)
â”‚   â”œâ”€â”€ models/                     # Model SQLAlchemy (M)
â”‚   â”‚   â”œâ”€â”€ pengguna.py
â”‚   â”‚   â”œâ”€â”€ jenis_kerusakan.py
â”‚   â”‚   â”œâ”€â”€ tingkat_kerusakan.py
â”‚   â”‚   â”œâ”€â”€ lokasi_kerusakan.py
â”‚   â”‚   â”œâ”€â”€ dokumentasi_foto.py
â”‚   â”‚   â”œâ”€â”€ hasil_klasifikasi_cnn.py
â”‚   â”‚   â”œâ”€â”€ peta_kerusakan.py
â”‚   â”‚   â”œâ”€â”€ label_kerusakan.py
â”‚   â”‚   â”œâ”€â”€ preprocessing_config.py
â”‚   â”‚   â”œâ”€â”€ hasil_preprocessing.py
â”‚   â”‚   â”œâ”€â”€ split_config.py / split_item.py
â”‚   â”‚   â”œâ”€â”€ arsitektur_config.py / hasil_training.py
â”‚   â”‚   â”œâ”€â”€ hasil_evaluasi.py / prediksi_model.py
â”‚   â”‚   â””â”€â”€ evaluasi_model.py
â”‚   â”œâ”€â”€ controllers/                # Blueprint / Controller (C)
â”‚   â”‚   â”œâ”€â”€ auth_controller.py
â”‚   â”‚   â”œâ”€â”€ dashboard_controller.py
â”‚   â”‚   â”œâ”€â”€ lokasi_controller.py
â”‚   â”‚   â”œâ”€â”€ klasifikasi_controller.py
â”‚   â”‚   â”œâ”€â”€ label_controller.py
â”‚   â”‚   â”œâ”€â”€ preprocessing_controller.py
â”‚   â”‚   â”œâ”€â”€ split_controller.py
â”‚   â”‚   â”œâ”€â”€ arsitektur_controller.py
â”‚   â”‚   â”œâ”€â”€ peta_controller.py
â”‚   â”‚   â””â”€â”€ evaluasi_controller.py
â”‚   â”œâ”€â”€ services/                   # Business logic / pipeline
â”‚   â”‚   â”œâ”€â”€ preprocessing_service.py
â”‚   â”‚   â”œâ”€â”€ split_service.py
â”‚   â”‚   â””â”€â”€ cnn_service.py
â”‚   â”œâ”€â”€ templates/                  # Template Jinja2 / View (V)
â”‚   â”‚   â”œâ”€â”€ base.html, components/
â”‚   â”‚   â”œâ”€â”€ auth/, dashboard/, lokasi/, klasifikasi/, label/
â”‚   â”‚   â”œâ”€â”€ preprocessing/, split/, arsitektur/, peta/, evaluasi/
â”‚   â””â”€â”€ static/
â”‚       â”œâ”€â”€ css/style.css
â”‚       â”œâ”€â”€ js/peta.js, js/toast.js
â”‚       â”œâ”€â”€ models/                 # Model CNN terlatih (model_{id}.keras)
â”‚       â””â”€â”€ uploads/
â”‚           â”œâ”€â”€ foto/               # Foto lapangan asli
â”‚           â””â”€â”€ preprocessed/       # Hasil preprocessing
â”œâ”€â”€ config.py                       # Konfigurasi aplikasi
â”œâ”€â”€ dump SQL lama                # Skema lengkap (fresh install)
â”œâ”€â”€ migrate_*.sql                   # Migration tambahan (lihat tabel di bawah)
â”œâ”€â”€ seed_data.py                    # Reset data model + import Excel revisi + foto (--reset)
â”œâ”€â”€ restore_foto.py                 # Utility pemulihan foto yang terhapus
â”œâ”€â”€ requirements.txt
â”œâ”€â”€ run.py                          # Entry point
â””â”€â”€ README.md
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

Jalankan migration yang diperlukan secara berurutan pada database Anda. Tidak ada lagi `database/dump SQL lama`; migration adalah sumber perubahan schema yang dipertahankan.

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
| `migrate_revisi_lokasi.sql` | P/L jadi DECIMAL meter + kolom `keterangan` di `lokasi_kerusakan` |

```powershell
Get-Content scripts/migrate_add_preprocessing.sql | & mysql -u root db_cnn_jalan
```

### Import data model

Siapkan Excel revisi dengan kolom `Citra`, `x`, `y`, `P`, `L`, `Ket`, lalu jalankan validasi dan reset/import:

```powershell
.\.venv\Scripts\python.exe scripts\seed_data.py --excel "DATA JALAN REVISI.xlsx" --reset
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
| **Arsitektur** | MVC (Modelâ€“Viewâ€“Controller dengan Blueprints) |



