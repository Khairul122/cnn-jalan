# CNN-Jalan — GIS Pemetaan Kerusakan Jalan Kota Lhokseumawe

Sistem informasi geografis (GIS) berbasis web untuk pemetaan kerusakan jalan menggunakan metode **Convolutional Neural Network (CNN)**. Dibangun dengan **Flask** (Python) menggunakan arsitektur **MVC**.

---

## Fitur

- Manajemen data lokasi kerusakan jalan (CRUD + upload foto)
- Klasifikasi jenis & tingkat kerusakan via CNN
- Visualisasi peta interaktif dengan **Leaflet.js**
- Filter peta berdasarkan kecamatan dan status pemetaan
- Evaluasi model CNN (Akurasi, Presisi, Recall, F1, Confusion Matrix)
- Autentikasi pengguna (Admin & Viewer)

---

## Teknologi

| Komponen | Teknologi |
|----------|-----------|
| Backend | Python 3.10+, Flask 3.0 |
| ORM | Flask-SQLAlchemy |
| Database | MySQL |
| Auth | Flask-Login |
| Migrasi DB | Flask-Migrate |
| Frontend | Bootstrap 5, Leaflet.js |
| Connector | PyMySQL |

---

## Persyaratan

- Python 3.10 atau lebih baru
- MySQL Server (XAMPP / standalone)
- Git (opsional)

---

## Instalasi

### 1. Clone / salin proyek

```bash
cd "D:\Project Python"
# Jika menggunakan git:
# git clone <repo-url> cnn-jalan
```

### 2. Buat dan aktifkan virtual environment

```bash
cd "D:\Project Python\cnn-jalan"

# Buat .venv
python -m venv .venv

# Aktifkan (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Aktifkan (Windows CMD)
.\.venv\Scripts\activate.bat
```

> Jika PowerShell menampilkan error _"execution policy"_, jalankan dulu:
> ```powershell
> Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
> ```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Buat database MySQL

Pastikan MySQL sudah berjalan, lalu import file SQL:

```bash
mysql -u root -p < db_cnn_jalan.sql
```

Atau buka file `db_cnn_jalan.sql` secara manual di **phpMyAdmin** → Import.

### 5. Konfigurasi koneksi database

Edit file `config.py` sesuaikan `SQLALCHEMY_DATABASE_URI`:

```python
SQLALCHEMY_DATABASE_URI = 'mysql+pymysql://root:PASSWORD@localhost/db_cnn_jalan'
```

Ganti `PASSWORD` dengan password MySQL Anda (kosongkan jika tidak ada).

### 6. Jalankan aplikasi

```bash
python run.py
```

Buka browser: [http://127.0.0.1:5000](http://127.0.0.1:5000)

---

## Struktur Proyek

```
cnn-jalan/
├── .venv/                          # Virtual environment (tidak di-commit)
├── app/
│   ├── __init__.py                 # App factory
│   ├── models/                     # Model SQLAlchemy (M)
│   │   ├── kecamatan.py
│   │   ├── jenis_kerusakan.py
│   │   ├── tingkat_kerusakan.py
│   │   ├── pengguna.py
│   │   ├── lokasi_kerusakan.py
│   │   ├── dokumentasi_foto.py
│   │   ├── hasil_klasifikasi_cnn.py
│   │   ├── peta_kerusakan.py
│   │   └── evaluasi_model.py
│   ├── controllers/                # Blueprint / Controller (C)
│   │   ├── auth_controller.py
│   │   ├── dashboard_controller.py
│   │   ├── lokasi_controller.py
│   │   ├── peta_controller.py
│   │   ├── klasifikasi_controller.py
│   │   └── evaluasi_controller.py
│   ├── templates/                  # Template Jinja2 / View (V)
│   │   ├── base.html
│   │   ├── auth/
│   │   ├── dashboard/
│   │   ├── lokasi/
│   │   ├── peta/
│   │   ├── klasifikasi/
│   │   └── evaluasi/
│   └── static/
│       ├── css/style.css
│       ├── js/peta.js
│       └── uploads/foto/           # Foto lapangan tersimpan di sini
├── config.py                       # Konfigurasi aplikasi
├── db_cnn_jalan.sql                # Skrip SQL (CREATE + seed data)
├── requirements.txt
├── run.py                          # Entry point
└── README.md
```

---

## URL Halaman

| URL | Deskripsi |
|-----|-----------|
| `/` | Dashboard |
| `/auth/login` | Login |
| `/auth/register` | Daftar akun |
| `/lokasi` | Daftar lokasi kerusakan |
| `/lokasi/create` | Tambah lokasi + upload foto |
| `/klasifikasi/upload` | Upload foto & proses CNN |
| `/peta` | Peta GIS interaktif |
| `/evaluasi` | Evaluasi model CNN |

---

## Mengintegrasikan Model CNN

Saat ini klasifikasi menggunakan **prediksi simulasi**. Untuk menghubungkan model CNN nyata, edit fungsi `_mock_predict()` di `app/controllers/klasifikasi_controller.py`:

```python
# Contoh menggunakan TensorFlow/Keras
import numpy as np
from tensorflow.keras.models import load_model
from PIL import Image

model = load_model('path/ke/model.h5')

def _mock_predict(path_foto):
    img = Image.open(path_foto).resize((224, 224))
    arr = np.expand_dims(np.array(img) / 255.0, axis=0)
    pred = model.predict(arr)
    # sesuaikan mapping output ke jenis & tingkat kerusakan
    ...
```

---

## Nonaktifkan Virtual Environment

```bash
deactivate
```

---

## Informasi Proyek

| | |
|-|-|
| **Judul** | Sistem GIS Pemetaan Kerusakan Jalan Kota Lhokseumawe Menggunakan CNN |
| **Penulis** | Imay Syafitri (NIM 210170072) |
| **Database** | `db_cnn_jalan` |
| **Framework** | Flask (Python) |
| **Arsitektur** | MVC |
