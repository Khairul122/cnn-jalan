# Rewrite Labeling K-Means Berbasis Fitur Visual

## Status
Proposed for implementation after user approval.

## Goal
Mengganti subsistem labeling otomatis berbasis formula SDI dari dimensi panjang x lebar menjadi klasterisasi K-Means atas fitur visual foto jalan, tanpa mengubah pipeline CNN dan subsistem lain yang dinyatakan stabil di `TODO.md`.

## Context
Label lama memakai panjang x lebar sebagai proksi untuk retak, lubang, dan rutting. Proksi tersebut tidak merepresentasikan kondisi visual foto secara langsung. Metode pengganti mereplikasi parameter notebook yang sudah divalidasi: embedding MobileNetV2 1280 dimensi, edge density Canny, StandardScaler, PCA, dan K-Means empat klaster.

Data aplikasi lama telah disetujui untuk dihapus oleh user. File gambar dipertahankan. Database belum dapat dibersihkan dari working copy karena `.env` dan `DATABASE_URL` tidak tersedia; implementasi tidak akan menebak target database.

## Scope

### In scope
- Rewrite `LabelKerusakan` agar menyimpan asal-usul dan hasil labeling klasterisasi.
- Tambah model `LabelingConfig`, `HasilLabeling`, dan `HasilLabelingItem`.
- Tambah service ekstraksi fitur, agregasi level lokasi, klasterisasi, pemetaan kelas, penerapan, dan pembuangan run.
- Rewrite controller labeling menjadi alur Config → Run → Review → Terapkan/Buang.
- Rewrite halaman daftar dan edit label serta tambah halaman konfigurasi dan review.
- Tambah migrasi Flask-Migrate/Alembic bila mekanisme migrasi tersedia.
- Hapus test lama yang khusus formula SDI dan tambah test labeling service.
- Verifikasi grep untuk memastikan referensi formula dan route lama hilang.
- Bersihkan file data non-gambar yang telah disetujui, sambil mempertahankan gambar dan source code.

### Out of scope
Modul berikut tidak diubah kecuali ditemukan kegagalan langsung yang menghalangi integrasi:
- `app/services/cnn_service/*`
- `app/services/preprocessing_service.py`
- `app/services/augmentation_service.py`
- `app/services/split_service.py`
- `app/services/dedup_service.py`
- `app/services/metrics_service.py`
- controller arsitektur, preprocessing, augmentasi, split, klasifikasi, peta, evaluasi, dashboard, auth, dan lokasi
- `app/kelas.py`
- model selain `LabelKerusakan.py` dan tiga model labeling baru
- test yang tidak secara langsung menguji formula SDI lama
- nice-to-have cache embedding, override granular, metrik Sobel/Laplacian, ekspor CSV, dan threading

## Data Model

### `LabelKerusakan`
Pertahankan identitas lokasi dan foreign key tingkat kerusakan. Hapus field serta method SDI lama. Tambahkan:
- `metode`: enum `klasterisasi` atau `manual`
- `cluster_id`
- `kepadatan_tepi`
- `jarak_centroid`
- `hasil_labeling_id`
- `catatan`, `pengguna_id`, dan timestamp yang tetap diperlukan

`tingkat_kerusakan_id` tetap bermakna: 1 Rusak Berat, 2 Rusak Ringan, 3 Sedang, 4 Baik. Lookup nama kelas dilakukan melalui tabel `TingkatKerusakan`, bukan hardcode ID di service.

### `LabelingConfig`
Menyimpan konfigurasi run:
- `nama_config`
- `n_cluster=4`
- `pca_komponen=50`
- `random_state=42`
- `canny_low=50`
- `canny_high=150`
- `is_default`
- `pengguna_id` dan `created_at`

### `HasilLabeling`
Menyimpan satu eksekusi sementara:
- config, jumlah lokasi berhasil, jumlah dilewati
- variansi PCA
- distribusi kelas sebagai JSON string
- status `selesai` atau `gagal`
- catatan, `is_diterapkan`, waktu penerapan, pengguna, timestamp

### `HasilLabelingItem`
Menyimpan hasil satu lokasi dalam satu run:
- `run_id`, `lokasi_id`
- ID klaster
- edge density
- jarak ke centroid
- tingkat kerusakan hasil pemetaan

Relationship item menggunakan cascade delete agar membuang run tidak meninggalkan item yatim.

## Algorithm Contract

1. Setiap foto valid dibaca dengan OpenCV, BGR ke RGB, resize 224x224 memakai `INTER_LANCZOS4`.
2. Embedding menggunakan MobileNetV2 `input_shape=(224,224,3)`, `include_top=False`, `pooling='avg'`, `weights='imagenet'`, dengan `preprocess_input`.
3. Edge density dihitung dari grayscale dan `cv2.Canny(low, high).mean() / 255`.
4. Embedding dan edge density dirata-ratakan per lokasi. Lokasi tanpa foto valid dilewati dan dicatat.
5. Seluruh embedding lokasi diproses bersama dengan StandardScaler lalu PCA.
6. K-Means memakai `n_clusters=4`, `random_state=42`, `n_init=10` secara default.
7. Klaster diurutkan berdasarkan rata-rata edge density ascending dan dipetakan ke Baik, Sedang, Rusak Ringan, Rusak Berat.
8. Jarak centroid adalah jarak Euclidean titik PCA ke centroid klasternya sendiri.
9. Run selalu disimpan sementara dan belum mengubah `LabelKerusakan`.
10. Penerapan melakukan upsert per lokasi dan menandai run diterapkan dalam transaksi yang sama.

Jika tidak ada lokasi dengan foto valid, service membuat run berstatus `gagal` dengan alasan yang dapat ditampilkan controller, bukan melempar exception mentah.

## HTTP/UI Contract

- `GET /label/`: daftar lokasi dan metadata label baru.
- `GET/POST /label/<lokasi_id>/edit`: override manual tingkat kerusakan dan catatan.
- `POST /label/<lokasi_id>/delete` dan `POST /label/hapus-semua`: dipertahankan.
- `GET/POST /label/config/new`: buat konfigurasi.
- `GET/POST /label/config/<id>/edit`: ubah konfigurasi.
- `POST /label/config/<id>/delete`: hapus konfigurasi.
- `POST /label/config/<id>/run`: jalankan run sinkron.
- `GET /label/review/<run_id>`: lihat ringkasan, distribusi, galeri sampel, dan item run.
- `POST /label/review/<run_id>/terapkan`: terapkan setelah konfirmasi browser.
- `POST /label/review/<run_id>/buang`: hapus hasil sementara tanpa mengubah label.

Semua route perubahan memakai `admin_required` dan CSRF protection yang sudah disediakan aplikasi. Route `auto_label` dan `hitung-sdi` dihapus.

UI akan mempertahankan bahasa visual aplikasi yang sudah ada, tetapi menerapkan mode antislop DURING:
- tidak ada kontrol tanpa aksi nyata;
- ada empty, loading, dan error state pada tampilan data yang relevan;
- fokus keyboard terlihat dan semua kontrol dapat dioperasikan keyboard;
- layout daftar, form, galeri, dan tabel reflow pada lebar mobile tanpa overflow;
- tidak menambah statistik, testimonial, ikon, atau klaim yang tidak bersumber;
- copy memakai istilah spesifik workflow labeling dan tidak memakai dekorasi yang tidak bermakna.

Design Read: halaman ini adalah dashboard admin untuk spot-check dan penerapan label foto jalan, dengan bahasa visual utilitarian-editorial yang mengikuti stylesheet aplikasi, dial ENERGY 1 / RHYTHM 2 / MOTION 1. Whitespace memisahkan tahap konfigurasi, hasil, dan tindakan berisiko; accent hanya untuk status tindakan; motion dibatasi transisi fokus/hover agar tidak mengganggu review visual.

## Migration and Data Safety

Jika folder `migrations/` tersedia, buat migration dan periksa operasi sebelum upgrade. Jika belum tersedia, inisialisasi Flask-Migrate lalu buat migration. Urutan tabel harus memungkinkan foreign key `label_kerusakan.hasil_labeling_id` dibuat setelah `hasil_labeling`.

Migrasi skema tidak boleh otomatis menghapus label lama, split, atau model training lama. Karena user sudah memerintahkan penghapusan semua data kecuali gambar, penghapusan database dilakukan terpisah hanya ketika `DATABASE_URL` tersedia dan targetnya dapat diverifikasi. Jika koneksi tidak tersedia, hanya source/schema yang disiapkan dan kondisi tersebut dilaporkan.

## Testing Strategy

- Unit test algorithm dengan fitur sintetis dan mock ekstraksi MobileNetV2.
- Uji determinisme K-Means untuk random state yang sama.
- Uji urutan edge density ke tingkat kerusakan melalui lookup database.
- Uji skip lokasi tanpa foto atau path yang hilang.
- Uji upsert penerapan dan flag `is_diterapkan`.
- Uji buang run dengan cascade dan tidak mengubah label existing.
- Pertahankan seluruh test lain dan jalankan `python -m unittest discover tests`.
- Jalankan grep akhir untuk seluruh simbol SDI lama yang ditentukan dalam `TODO.md`.
- Jika dependency/environment memungkinkan, jalankan migrasi dan smoke test Flask. Jika tidak, laporkan keterbatasan secara eksplisit.

## Acceptance Criteria

- Model baru dapat diimpor dan metadata tabel sesuai kontrak.
- Service default memakai 224x224, Canny 50/150, PCA 50, K-Means k=4, random state 42, n_init 10.
- Run tidak menulis label sebelum endpoint Terapkan.
- Terapkan dan Buang bekerja idempoten sesuai aturan controller.
- Edit manual tidak lagi menghitung SDI dan mempertahankan metadata asal klaster bila override.
- Semua test existing yang relevan dan test labeling baru lulus.
- Tidak ada referensi simbol atau route SDI lama di source/template/test yang tersisa.
- Tidak ada perubahan pada modul out-of-scope.
- File gambar tetap ada.
