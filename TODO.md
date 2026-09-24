# TODO — Rewrite CNN-Jalan Sesuai Standar (Rinci per Proses)

Disusun: 24 September 2026. Dasar: audit menyeluruh kode aktual dibandingkan dengan standar SDI Bina Marga (4 sumber jurnal independen) dan praktik resmi TensorFlow/Keras untuk transfer learning. Tiap proses dipisah jadi bagian sendiri (P0–P8) supaya bisa dikerjakan dan diverifikasi satu per satu lewat CV penuh, bukan digabung sekaligus.

Ukuran usaha: **S** kurang dari 30 menit · **M** 1–3 jam · **L** lebih dari 3 jam · **XL** butuh beberapa sesi kerja.

**Urutan wajib**: P0 harus selesai dulu sebelum P1–P8, karena semua proses lain memakai `label_kerusakan.tingkat_kerusakan_id` sebagai target. Split, model, dan hasil evaluasi yang ada sekarang dibangun dari label lama dan perlu dibuat ulang setelah P0 selesai.

---

## P0 — Pelabelan (SDI)

**Status 2026-09-24: selesai kecuali perbandingan label surveyor (L, antre di belakang baseline CV).** Catatan: `run_surveyor_cv.py` memakai 3 tingkat surveyor (Ringan/Sedang/Berat) yang tidak sama dengan 4 kelas SDI; perbandingannya perlu disesuaikan dulu (mis. petakan Ringan→Baik).

**Asumsi kalibrasi yang wajib ditulis di bab metodologi:** `SEGMEN_M2=700`, `LUBANG_M2=0,5`, `REF_RUTTING=4,0`, `AMBANG_LEBAR=2,0` (`label_kerusakan.py`) adalah asumsi, bukan hasil ukur. Jumlah lubang dan kedalaman rutting tidak diukur; keduanya proksi dari luas. Rusak Ringan/Rusak Berat hanya bisa dicapai lewat F_lubang, sehingga kelas ditentukan luas kerusakan.

Akar masalah paling besar. Formula ini menentukan target yang dipelajari model, jadi kesalahan di sini mencemari semua proses di bawahnya.

- [x] **Perbaiki F_rutting di `label_kerusakan.py::hitung_sdi()` baris 54-62.** Nilai saat ini 5/20/40, standar Bina Marga (dicek silang ke 4 jurnal: UNILA, UNUD, japendi, FT UMI) adalah 2,5/10/20 (rumus dasarnya `5 × faktor kedalaman`, faktor 0,5/2/4). Kode saat ini persis 2× lipat standar di ketiga bucket.
  ```python
  # Sebelum
  elif r <= 1: f_rutting = 5
  elif r <= 3: f_rutting = 20
  else: f_rutting = 40
  # Sesudah
  elif r <= 1: f_rutting = 2.5
  elif r <= 3: f_rutting = 10
  else: f_rutting = 20
  ```
  **(S)**
  **Selesai 2026-09-24.** Nilai jadi 2,5/10/20.

- [x] **Perbaiki breakpoint F_retak di `hitung_sdi()` baris 33-40.** Ambang tengah saat ini 20%, standar adalah 30%. Retak dengan luas 21-30% saat ini salah dianggap kategori tertinggi (nilai 40), seharusnya kategori tengah (nilai 20).
  ```python
  # Sebelum
  elif p <= 20: f_retak = 20
  else: f_retak = 40
  # Sesudah
  elif p <= 30: f_retak = 20
  else: f_retak = 40
  ```
  **(S)**
  **Selesai 2026-09-24.** Breakpoint tengah jadi 30%.

- [x] **Update `tests/test_p2.py::test_hitung_sdi` setelah dua perbaikan di atas.** Assertion baris 17 `hitung_sdi(15, 'lebar', 12, 2) == 135` akan berubah jadi **125** (F_retak tetap 20×2=40 karena p=15 masih di bucket ≤30 sama seperti sebelumnya, tapi F_rutting untuk r=2 turun dari 20 ke 10, jadi total 40+75+10=125). Tambahkan juga kasus uji baru untuk p=25 (sebelum: masuk bucket >20 → 40×pengali; sesudah: masuk bucket ≤30 → 20×pengali) supaya regresi breakpoint ini tidak lolos lagi di masa depan. **(S)**
  **Selesai 2026-09-24.** Assertion jadi 125, ditambah kasus retak 25/30/30,01% dan rutting 1/3/3,01 cm.

- [x] **Putuskan skema kategorisasi: pertahankan 3 kelas dengan dokumentasi eksplisit, atau pindah ke 4 kelas sesuai standar.** `tingkat_dari_sdi()` baris 66-75 cuma punya 3 level (Ringan ≤50 / Sedang 51-150 / Berat >150). Standar SDI punya 4 level (Baik <50 / Sedang 50-100 / Rusak Ringan 100-150 / Rusak Berat >150). Dua masalah: kelas "Ringan" di kode ini sebenarnya "Baik" (bukan tingkat kerusakan) di standar, dan kelas "Sedang" menggabung dua kategori standar yang berbeda tingkat keparahannya.
  - Kalau tetap 3 kelas: tulis di bab metodologi bahwa ini penyederhanaan sengaja dari skema 4-kategori standar, jelaskan alasannya (kebutuhan jumlah kelas untuk klasifikasi CNN, ukuran dataset per kelas).
  - Kalau pindah ke 4 kelas: update `TingkatKerusakan` (tambah 1 baris kelas baru), update `N_CLASSES` di `model.py` baris 3, update `tingkat_dari_sdi()`, dan sadari ini akan memecah kelas Sedang yang sekarang jadi dua kelas lebih kecil — distribusi kelas berubah total, split dan training harus dibuat ulang.
  **(M, keputusan + dokumentasi, atau L kalau pindah ke 4 kelas)**
  **Selesai 2026-09-24.** **Keputusan pemilik: 4 kelas** (Rusak Berat / Rusak Ringan / Sedang / Baik, id 1–4, `app/kelas.py`). Ambang SDI <50 / 50–100 / 100–150 / >150. `N_CLASSES`=4, `HasilEvaluasi` pakai kolom JSON `per_class`, semua template memakai `KELAS`. Data turunan lama dicadangkan ke `backup_3kelas_20260924/` lalu dikosongkan (`scripts/migrate_4_kelas.sql`).

- [x] **Jalankan ulang `/label/auto` setelah dua perbaikan formula di atas diterapkan**, supaya `label_kerusakan` di database konsisten dengan formula yang benar. Cek dulu berapa banyak baris yang label-nya berubah dibanding sebelumnya (bandingkan `tingkat_kerusakan_id` lama vs baru) — ini indikasi seberapa besar dampak perbaikan ini ke distribusi kelas. **(S, eksekusi)**
  **Selesai 2026-09-24.** Ternyata DB sudah berisi label formula kontinu (Berat 153/Sedang 97/Ringan 30), dan perbaikan rumus saja tidak mengubah satu baris pun karena F_lubang jenuh di 225 untuk luas > 5 m². Formula estimasi lalu diganti (keputusan pemilik: asumsi 1 lubang per 0,1 m² bukan dari pemilik): retak dihitung per segmen 100 m × 7 m, 1 lubang per 0,5 m². Relabel sudah diterapkan: Rusak Berat 40 / Rusak Ringan 37 / Sedang 74 / Baik 129. Validasi silang dengan `keterangan` surveyor: Estimasi (Ringan) 76/76 → Baik, Estimasi (Berat) 2/2 → Rusak Berat.

- [x] **Audit ulang label yang mendekati ambang batas SDI (50, 100, 150)** dengan `scripts/audit_sdi_borderline.py` setelah relabel. Audit lama (0 dari 280 label dekat ambang) dilakukan pada tabel diskrit lama yang secara struktural tidak bisa mendekati ambang — hasil itu tidak berlaku lagi setelah formula kontinu dan breakpoint diperbaiki. **(S)**
  **Selesai 2026-09-24.** `audit_sdi_borderline.py` diperbarui untuk ambang 50/100/150. Hasil: 111 dari 280 label dalam ±10 poin dari ambang (banyak SDI bernilai 95 dan 80-an karena F_lubang diskret), jadi label dekat ambang sensitif terhadap konstanta kalibrasi.

- [ ] **Bandingkan formal label SDI vs label surveyor lewat CV**, pakai `scripts/run_surveyor_cv.py` yang sudah disiapkan tapi belum pernah dijalankan. Eksperimen awal menunjukkan label surveyor mencapai macro-F1 56-61% vs SDI 46-52% — kalau pola ini konsisten setelah formula SDI diperbaiki, ini bukti kuat untuk bab pembahasan soal keterbatasan label berbasis dimensi fisik. **(L, CPU-only, antre di belakang baseline CV baru)**

---

## P1 — Preprocessing

**Status 2026-09-24 (ditulis ulang dari nol): kode selesai; dua ablation CV menunggu baseline 4 kelas.**

**Keputusan pemilik:** (1) geometri: resize 256×256 lalu center crop 224×224 (bukan letterbox); (2) tanpa kolom `preprocessing_config_id` di `arsitektur_config`, melainkan **satu config aktif global**: `hasil_preprocessing` hanya boleh berisi satu config, dan menjalankan preprocessing menggantikan semua hasil sebelumnya (file + record). Konsekuensi: satu ablation = satu siklus (jalankan config → split/training/CV → catat `cv_summary()` → ganti config), tidak bisa paralel.

- [x] **Default `norm_method` jadi `none`** (model, form, controller; DB via `migrate_p1_preprocessing.sql`). `preprocess_input` di dalam model sudah menormalisasi; minmax per-channel menghapus kontras absolut antar foto.
- [x] **Default geometri resize 256 → crop 224**: `target_width/height=256`, `crop_enabled=True`, `crop_width/height=224`, `resize_mode='stretch'`. Catatan: semua 280 foto berasio 4:3 sehingga stretch ke 256×256 masih menekan lebar ±25% (dipertahankan sesuai keputusan pemilik; letterbox tetap tersedia di form).
- [x] **Cegah train/serve skew.** Invarian satu config aktif membuat `_preprocessed_subquery()`/`_stage_map_for()` (`MAX(path_output)` per foto) tidak mungkin lagi mencampur config. Pengaman tambahan: `PreprocessingConfig.aktif()` = config dari hasil preprocessing terbaru; `klasifikasi_controller.upload()` memakainya (bukan `is_default` yang bisa berbeda dari data training); edit parameter config yang sudah punya hasil ditolak (harus reset dulu); hapus config ikut menghapus file hasilnya; training ditolak bila ada foto di split tanpa hasil denoise (`foto_tanpa_preprocessing`, sebelumnya diam-diam jatuh ke gambar asli).
- [ ] **Ablation denoise vs tanpa-denoise.** Config `P1 ablation A: tanpa denoise` sudah dibuat (belum dijalankan). Siklus: klik Jalankan pada config itu → split baru → arsitektur (hiperparameter sama dengan baseline) → Prediksi CV → bandingkan `cv_summary()` dengan baseline.
- [ ] **Bandingkan CLAHE vs minmax/zscore/none.** Config `P1 ablation B: CLAHE` sudah dibuat; pembanding `none` = baseline. Config norm `minmax` dan `zscore` belum dibuat.

Temuan sampingan yang ikut diperbaiki: `train_final` tidak meneruskan `mixup_alpha`, `label_smoothing`, `dense_units`, `dense_l2`, `skip_fine_tuning` ke model final (model final memakai default, bukan hiperparameter CV).

---

## P2 — Augmentasi

**Status 2026-09-24: kode selesai; ablation CV menunggu baseline 4 kelas (dijalankan lewat UI).**

- [x] Urutan augmentasi → `preprocess_input` → base model sesuai standar (tutorial TensorFlow). Tidak perlu diubah.
- [x] Parameter tiap layer augmentasi Keras diverifikasi ke dokumentasi Keras 3. Tidak perlu diubah.
- [x] **Dua sistem augmentasi dijernihkan dengan menghapus salah satunya (keputusan pemilik).** Tahap Augmentasi dihapus dari preprocessing: service (pipeline kini 4 tahap: resize, crop, normalisasi, denoise), kolom `preprocessing_config.aug_*` (5 kolom), form, tabel, tab hasil, dan 280 file/baris hasil `augmentasi`. Satu-satunya augmentasi kini ada di dalam model (`model.py`, 10 layer, acak ulang tiap epoch, mati saat prediksi). Migrasi: `scripts/migrate_p2_augmentasi.sql`. Draf kalimat bab metodologi: "Augmentasi data dilakukan di dalam model (layer preprocessing Keras: flip horizontal, rotasi ±18°, zoom ±20%, translasi ±10%, brightness ±30%, contrast ±30%, hue, saturasi, noise Gaussian piksel, dan random erasing), diacak ulang setiap epoch dan dinonaktifkan saat inferensi."
- [x] **Augmentasi per layer bisa dimatikan** untuk ablation: kolom `arsitektur_config.aug_off` (kunci dipisah koma), checkbox di form Arsitektur (semua aktif = default), chip "tanpa aug: ..." di halaman detail. Kunci: flip, rotasi, zoom, translasi, brightness, contrast, hue, saturasi, noise, erasing.
- [x] **Bug kritis ditemukan dan diperbaiki: `predict_cv` mengabaikan `mixup_alpha`, `label_smoothing`, `dense_units`, `dense_l2`, `skip_fine_tuning`.** Fold CV dilatih dengan default untuk field itu (config disalin manual dan lupa field baru), jadi CV apa pun untuk P2/P4 (Mixup, smoothing, Dense head, Jalur A) sebenarnya identik dengan baseline. Kini satu sumber `cnn_service.hyperparams()` dipakai snapshot controller, `predict_cv`, dan `train_final` (juga menutup bug `train_final` yang serupa). **Semua angka CV lama yang memakai opsi itu tidak valid**, meski tampaknya belum ada karena CV 4 kelas belum pernah dijalankan.
- [x] **Mixup dan label smoothing diverifikasi untuk 4 kelas** (tes `_mixup_dataset`, pemilihan loss, smoke-run MobileNetV2). Mixup dengan data fit < `batch_size` kini `ValueError` yang jelas, bukan crash di `fit()`.
- [ ] **Jalankan ablation lewat UI (satu per satu, hiperparameter lain sama dengan baseline):** baseline vs `mixup_alpha=0.2` vs `label_smoothing=0.1`; lalu baseline vs tanpa `zoom` vs tanpa `erasing` vs tanpa `translasi`. Hipotesis ablation augmentasi: zoom/translasi/erasing mengubah luas kerusakan yang tampak padahal label SDI berbasis luas.

---

## P3 — Split Data

**Status 2026-09-24: kode selesai; tinggal membuat split lewat UI. Repeated K-Fold menunggu keputusan pemilik.**

- [ ] **Buat split baru dari nol setelah P0 selesai.** Split dan model yang ada sekarang dibangun dari label SDI lama (formula salah). Split lama tidak otomatis terupdate meski label berubah — harus dibuat ulang lewat `/split/new`. **(S, eksekusi — tergantung P0)**
  **Belum dieksekusi (dilakukan lewat UI).** DB belum berisi split. Pakai K=5, `random_state=42` untuk baseline dan semua ablation supaya sebanding.
- [x] **Hapus atau selesaikan field `split_type='holdout'`.** `split_config.py` baris 10 dan `split_controller.py::export()` baris 329-330 punya logika untuk mode holdout (label "Train"/"Test"), tapi tidak ada route `/split/new` yang bisa membuatnya — cuma `'kfold'` yang bisa dibuat dari UI. Dead code yang berisiko membingungkan siapapun yang audit kode Anda (termasuk dosen penguji). Kalau tidak berencana dipakai, hapus field dan logikanya. **(S)**
  **Selesai 2026-09-24.** Dihapus: field model, logika holdout di `export()`, argumen di tes dan skrip, kolom DB (`scripts/migrate_drop_split_type.sql`, sudah dijalankan), dan teks "holdout" di landing page.
- [x] **Tulis pengakuan di bab keterbatasan** bahwa skema pure K-Fold berarti tidak ada data yang benar-benar independen dari seluruh proses pengembangan — tiap foto pernah berperan sebagai data uji di satu titik sepanjang siklus eksperimen. Ini trade-off yang tepat untuk ukuran data 280 foto (held-out test terpisah akan mengecilkan data latih lebih jauh), tapi konsekuensinya perlu diakui eksplisit, bukan diklaim sebagai estimasi generalisasi murni. **(S, dokumentasi)**
  **Draf selesai 2026-09-24 (tinggal disalin ke bab keterbatasan):** "Evaluasi memakai Stratified Group K-Fold pada 280 foto tanpa himpunan uji terpisah. Setiap foto berperan sebagai data uji pada satu fold, dan hasil fold terlihat selama iterasi eksperimen (pemilihan arsitektur dan hiperparameter). Karena itu akurasi yang dilaporkan bukan estimasi generalisasi murni satu kali coba, melainkan estimasi internal dengan potensi optimisme kecil. Pilihan ini diambil karena himpunan uji terpisah akan mengecilkan data latih yang sudah kecil. Foto near-duplicate (jarak Hamming average-hash ≤ 5 bit, parameter kalibrasi; 31 foto pada dataset ini) dikelompokkan ke fold yang sama untuk mencegah kebocoran. Autokorelasi spasial (lokasi berdekatan pada ruas jalan yang sama) tidak dikendalikan." Autokorelasi spasial adalah keterbatasan tambahan yang belum ada di TODO awal: split tidak mengelompokkan foto berdasarkan kedekatan koordinat GPS.
- [x] **`StratifiedGroupKFold`, dedup near-duplicate (average hash 64-bit + jarak Hamming + union-find), dan validasi K terhadap ukuran kelas terkecil sudah sesuai standar.** Tidak perlu diubah. Ambang jarak Hamming 5-bit boleh didokumentasikan di bab metodologi sebagai parameter kalibrasi, bukan nilai baku.
  **Diverifikasi ulang pada label 4 kelas (K=5, seed 42 dan 7, 31 foto dikelompokkan):** tiap fold 55–57 foto, kelas per fold berselisih paling banyak 1 foto (Rusak Berat 8/8/8/8/8, Sedang 14–15, Baik 25–26). Tidak perlu diubah.
- [x] **Validasi input form `/split/new`** (temuan baru): K atau random state non-numerik (atau `random_state` kosong) sebelumnya menyebabkan HTTP 500 karena `int()` tanpa penanganan; kini flash peringatan dan tidak membuat split. Ada tes.
- [x] **Grup spasial (keputusan pemilik: perlu).** `radius_grup_m` di form split (default 50 m, 0 = nonaktif): foto yang berjarak ≤ radius (GPS, haversine, single linkage) digabung dengan grup near-duplicate dan dipaksa satu fold (`dedup_service.find_spatial_groups`/`merge_group_maps`, kolom `split_config.radius_grup_m`, `migrate_add_split_radius.sql`). Pada dataset ini: tetangga terdekat median 77 m; radius 50 m menggabungkan 79 foto ke grup ≤ 5 foto; 100 m mulai membentuk grup raksasa (47); 200 m menghasilkan grup 66 foto. Radius yang membuat grup lebih besar dari satu fold ditolak. Konsekuensi: akurasi CV bisa turun dibanding split tanpa grup spasial, dan itu lebih jujur. Hasil dengan/tanpa grup spasial tidak sebanding; pilih satu untuk semua ablation.
- [x] **Pertimbangkan repeated stratified group K-Fold** (beberapa `random_state` berbeda) untuk memperkuat kepercayaan pada angka CV. Berkaitan langsung dengan item di P5 soal variansi antar-fold. **(XL, lihat P5)**
  **Selesai 2026-09-24.** Form `/split/new` punya "Jumlah ulangan" (1–5): membuat beberapa split dengan seed berurutan (seed, seed+1, ...). Halaman `Arsitektur CNN → Ringkasan Repeated CV` menggabungkan run CV terpilih: rata-rata, std antar-run, min, maks untuk akurasi, macro-F1, baseline, selisih baseline, dan recall per kelas; memperingatkan bila hiperparameter run berbeda. Biaya tetap di training (satu CV 5-fold per ulangan, CPU-only) dan dijalankan lewat UI.

---

## P4 — Arsitektur Model

- [x] **Struktur head klasifikasi sudah dibuat configurable** (`dense_units` default 64, `dense_l2` default 1e-4 di `ArsitekturConfig`), memudahkan ablation `Dense(32)` atau `L2=1e-3` langsung dari UI. Tidak perlu diubah, tapi:
- [ ] **Jalankan ablation `dense_units`/`dense_l2` lewat CV sungguhan.** Kode sudah siap tapi belum pernah divalidasi lewat CV penuh — cuma default 64/1e-4 yang pernah diuji. **(M per kombinasi, antre di belakang baseline P0 baru)**
- [ ] **Validasi Jalur A (`skip_fine_tuning=True`, backbone beku penuh) lewat CV sungguhan.** Sudah diimplementasikan dan diuji smoke-test, belum pernah dibandingkan lewat CV terhadap Jalur dengan fine-tuning. **(M, antre di belakang baseline P0 baru)**
- [ ] **Kalau ada waktu dan sumber daya**, cari bobot pretrained yang lebih dekat ke domain jalan (CRACK500/GAPs) sebagai pengganti ImageNet. Ini proyek riset terpisah — format bobot kemungkinan besar tidak langsung kompatibel dengan `keras.applications.MobileNetV2`/`EfficientNetB0`, mungkin perlu retrain dari awal di dataset publik itu. **(XL, eksperimen besar, opsional)**
- [ ] **Pertimbangkan Jalur B (model hybrid foto + tabular)** kalau butuh akurasi di atas 70% dan siap mengubah scope penelitian dari "klasifikasi dari foto murni" jadi "klasifikasi dari foto + metadata pengukuran". Perlu keputusan pembimbing dulu — effort besar: cabang input tabular baru, dataset loader baru yang ikut kembalikan panjang/lebar/jenis per sampel, training/prediction path terpisah. **(XL, perlu persetujuan pembimbing dulu)**

---

## P5 — Training

- [x] **Nested validation (fit/inner-val/fold-uji), checkpoint berbasis balanced accuracy, BatchNorm beku saat fine-tuning, dan `class_weight='balanced'` semua sudah sesuai standar**, beberapa di atas rata-rata skripsi CNN pada umumnya. Tidak perlu diubah — bisa dijelaskan sebagai kekuatan metodologi di bab metodologi.
- [ ] **Tulis pengakuan metodologis di bab keterbatasan soal kebocoran tidak langsung lewat iterasi eksperimen.** Fold-uji terlihat di log training tiap epoch (`training.py` baris 253, kolom `uji_loss uji_acc`). Meski tidak dipakai kode untuk keputusan otomatis, angka ini memengaruhi keputusan arsitektur lewat observasi manual Anda antar-run (misal keputusan 23 September memperketat unfreeze layer dari 15/25 ke 8/12, alasannya eksplisit mengutip pola di log ini). Artinya angka CV yang dilaporkan bukan estimasi generalisasi sekali-coba murni. **(S, dokumentasi, tapi penting untuk kejujuran akademik)**
  **Draf (tinggal disalin):** "Fold uji terlihat pada log training setiap epoch (kolom uji_loss dan uji_acc). Meskipun tidak dipakai kode untuk keputusan otomatis (early stopping, pemilihan bobot, dan penurunan learning rate memakai inner-validation), angka tersebut ikut memengaruhi keputusan desain melalui pengamatan manual antar-run, misalnya pengetatan unfreeze layer dari 15/25 menjadi 8/12. Akurasi yang dilaporkan karena itu adalah estimasi internal, bukan estimasi generalisasi satu kali coba."
- [ ] **Jalankan repeated stratified K-Fold** (3+ putaran dengan `random_state` berbeda) setelah baseline P0 baru selesai. Std 6,1–6,7 poin dari satu putaran terlalu besar untuk disimpulkan dengan percaya diri sebagai angka tunggal. Laporkan rata-rata dan rentang dari beberapa putaran, bukan cuma satu. **(XL, butuh banyak training run, CPU-only — realistis cuma kalau waktu skripsi masih longgar)**
  **Dukungan kode selesai (lihat P3).** Menjalankan 3+ putaran adalah pekerjaan training Anda lewat UI: buat split dengan ulangan=3, latih satu config per split (hiperparameter identik), jalankan "Prediksi CV K-Fold" pada tiap config, lalu buka Ringkasan Repeated CV.
- [ ] **Setiap perubahan (preprocessing, augmentasi, arsitektur) diuji satu per satu lewat CV penuh**, bukan digabung sekaligus, supaya kontribusi tiap perubahan ke akurasi bisa diatribusikan dengan jelas. Catat tiap hasil `cv_summary()` di tabel terpisah. **(Aturan kerja berkelanjutan, bukan tugas satu kali)**
  Urutan run yang disarankan ada di bagian "Protokol eksperimen" di akhir file ini.

---

## P6 — Evaluasi dan Metrik

- [x] **Prioritas `cv_summary().macro_f1` di atas `HasilEvaluasi` (1 fold) sudah konsisten** di `arsitektur_controller.py::index()`, `dashboard_controller.py::_headline_accuracy()`, dan `peta_controller.py::index()`, dengan label sumber `cv`/`1fold` yang tampil sampai ke landing page publik (`landing/index.html` baris 300). Tidak perlu diubah.
- [x] **Audit isi tabel `evaluasi_model`.** `evaluasi_controller.py::create()` menerima `akurasi`/`presisi`/`recall`/`f1_score`/`tp`/`fp`/`tn`/`fn`/`cross_entropy_loss` langsung dari form HTML, disimpan tanpa dihitung dari prediksi model manapun dan tanpa validasi konsistensi antar angka. Cek apakah ada baris tersimpan di database sekarang. Kalau ada, pastikan tidak pernah dikutip di skripsi sebagai "hasil sistem" tanpa penjelasan bahwa itu entri manual. Tambahkan kolom penanda sumber (`sumber_eksternal` boolean atau sejenisnya), atau hapus fitur ini kalau memang tidak dipakai untuk apapun. **(M)**
  **Selesai 2026-09-24.** Tabel kosong (0 baris). Fitur dipertahankan dan halamannya kini memberi peringatan bahwa isinya input manual, bukan hasil sistem; kolom penanda tidak ditambahkan karena semua entri memang manual.
- [x] **Tambahkan precision dan F1 per kelas ke `cv_summary()`.** `metrics_service.py` baris 40-47 cuma menghitung `recall` per kelas untuk metrik resmi, padahal `evaluate()` (1-fold, tidak resmi) justru punya ketiganya. Confusion matrix yang sudah dikembalikan `cv_summary()` cukup untuk hitung manual, tapi menambahkannya langsung ke fungsi ini memudahkan pelaporan tabel skripsi. **(S)**
  **Selesai 2026-09-24.** `cv_summary()` mengembalikan `precision` dan `f1` per kelas; tampil di komponen `cv_summary.html`.
- [x] **Pertimbangkan tambahkan metrik loss (cross-entropy) di data uji** ke `evaluate()` dan `cv_summary()`. Berguna untuk menilai kalibrasi confidence model, bukan cuma ketepatan argmax. Probabilitas sudah dihitung saat prediksi, tinggal dihitung negative log-likelihood-nya. **(S, nice-to-have)** **Ditunda:** `prediksi_model` hanya menyimpan confidence kelas yang diprediksi, bukan probabilitas kelas sebenarnya, jadi NLL tidak bisa dihitung tanpa menambah kolom probabilitas per kelas (perubahan skema + `predict_cv`).
  **Selesai 2026-09-24.** Probabilitas 4 kelas kini disimpan (`prediksi_model.probabilitas`, JSON; `migrate_add_probabilitas.sql`) oleh `predict_cv`, `predict_all`, dan alur training; `cv_summary()["cross_entropy"]` = rata-rata −log p(kelas sebenarnya) (acak 4 kelas ≈ 1,386). Prediksi lama tanpa probabilitas menghasilkan `None`. Metrik ini hanya ada di `cv_summary()`, tidak di `evaluate()` (1 fold, bukan metrik resmi).
- [x] **Tambahkan analisis pola kesalahan dari confusion matrix** di bab pembahasan skripsi: seberapa sering kesalahan terjadi antar kelas berdekatan (Berat-Sedang, Sedang-Ringan) dibanding antar kelas jauh (Berat-Ringan). Kelas kerusakan bersifat berjenjang (ordinal), jadi pola ini relevan dibahas. **(M, analisis untuk skripsi, bukan kode)**
  **Selesai 2026-09-24.** `cv_summary()["kesalahan"]` menghitung salah ke kelas bersebelahan vs melompat jauh (kelas berjenjang), tampil di ringkasan CV. Pembahasan di skripsi tetap tugas Anda.

---

## P7 — Klasifikasi (Inferensi Foto Baru)

- [x] **Tambahkan ambang confidence minimum di `klasifikasi_controller.py::upload()`.** Baris 73 selalu set `is_valid=True` apa pun nilai confidence-nya, dan argmax dipakai tanpa pengecualian. Mengingat akurasi resmi sistem ini ~47%, tandai prediksi confidence rendah (misal di bawah 50%) sebagai "perlu verifikasi manual" sebelum dipakai untuk keputusan prioritas perbaikan jalan oleh dinas PU. **(M)**
  **Selesai 2026-09-24.** `AMBANG_CONFIDENCE = 0.5` di `klasifikasi_controller.py`: di bawahnya `is_valid=False`, badge "Perlu verifikasi manual", dan flash peringatan. Nilai 0,5 adalah tebakan saya (chance 4 kelas 25%, akurasi CV sebelumnya ±45%); ubah konstanta bila perlu.
- [x] **Pastikan `predict_image()` memakai preprocessing config yang sama dengan yang melatih model aktif**, lihat item terkait di P1. Ini yang paling berdampak ke keandalan fitur klasifikasi foto baru di dunia nyata. **(Tergantung P1)**
  **Selesai 2026-09-24.** Klasifikasi memakai `PreprocessingConfig.aktif()` (satu config aktif global, lihat P1).
- [x] **Ensemble model fold CV + TTA 10-view (5-crop + flip) sudah diimplementasikan dengan benar** di `prediction.py::_resolve_prediction_models`/`_predict_with_tta`, teknik standar test-time augmentation. Tidak perlu diubah.

---

## P8 — Dokumentasi dan Kualitas Kode

- [ ] **Perbarui `studi.md` seluruhnya** supaya mencerminkan skema yang benar-benar dipakai setelah semua perbaikan P0-P7 selesai, bukan snapshot 29 Mei 2026 yang sudah sangat usang (masih menyebut LR Phase 1=0.001, fine-tune 15 layer, angka akurasi CV 48,9% yang sudah terbukti tidak valid karena bug `predict_cv()`). **(L)**
  **Tertunda:** `studi.md` sudah dihapus dari repo (commit `4ae2ac9`). Kalau masih dibutuhkan, tentukan apakah dibuat ulang sebagai dokumen baru; catatan keputusan saat ini ada di `CLAUDE.md` dan `TODO.md`.
- [ ] **Perbarui `CLAUDE.md` bagian "Status Akurasi CNN"** setiap kali ada hasil CV baru yang valid setelah rewrite. **(S, berulang)**
- [ ] **Update checklist P0 checkbox di file TODO ini setiap item selesai**, dan simpan riwayat keputusan (seperti pola `CLAUDE.md` lama: "Opsi A dipilih, keputusan pemilik, tanggal") supaya jejak keputusan metodologis tetap tercatat untuk bab metodologi skripsi. **(Aturan kerja berkelanjutan)**
- [x] **Tambahkan test regresi untuk perubahan `hitung_sdi()` dan `tingkat_dari_sdi()`** di `tests/test_p2.py` sesuai item P0, supaya perubahan berikutnya tidak diam-diam menyimpang lagi dari formula yang benar. **(S, terhubung ke P0)**
  **Selesai 2026-09-24.** `tests/test_p2.py::test_hitung_sdi` dan `test_tingkat_dari_sdi` mencakup breakpoint retak (10/30%), rutting (1/3 cm), dan 4 ambang kelas (50/100/150).

---

## Protokol eksperimen (dijalankan lewat UI)

Aturan: satu variabel berubah per run; split sama (K=5, `random_state=42`, radius grup spasial sama) untuk semua run yang dibandingkan; preprocessing aktif = baseline kecuali ablation preprocessing; catat `cv_summary()` tiap run.

| # | Tujuan | Yang diubah dari baseline |
|---|---|---|
| 0 | Baseline | Config preprocessing baseline (resize 256 → crop 224, norm none, bilateral k=3), MobileNetV2, lr 1e-4, batch 32, dropout 0,3, epoch 80, patience 20, augmentasi lengkap |
| 1 | P4 Jalur A | `skip_fine_tuning` aktif |
| 2 | P4 Dense head | `dense_units=32` (lalu `dense_l2=1e-3`, satu per satu) |
| 3 | P2 label smoothing | `label_smoothing=0.1` |
| 4 | P2 Mixup | `mixup_alpha=0.2` |
| 5 | P2 augmentasi | matikan `zoom`; lalu `translasi`; lalu `erasing` (satu per satu) |
| 6 | P1 denoise | Jalankan config "ablation A: tanpa denoise" (ganti config aktif, latih ulang) |
| 7 | P1 CLAHE | Jalankan config "ablation B: CLAHE" |
| 8 | P5 repeated | Ulangi run 0 (dan pemenang ablation) dengan split ulangan=3, gabungkan di Ringkasan Repeated CV |

Perbandingan yang sah hanya terhadap run 0 dengan split yang sama. Selisih di bawah simpangan baku antar-fold (±6 poin pada run lama) tidak boleh dilaporkan sebagai perbaikan; gunakan repeated K-Fold (run 8) untuk menyimpulkan.

---

## Catatan Kejujuran Akademik

Setelah P0-P8 selesai, target akurasi di atas 70% kemungkinan besar tetap tidak tercapai murni dari foto saja. Akar masalahnya tetap sama: SDI mengukur luas fisik kerusakan dalam meter persegi, informasi yang tidak bisa direkonstruksi dari foto tanpa objek referensi skala. Perbaikan di TODO ini akan menghilangkan noise label yang tidak seharusnya ada (breakpoint salah, F_rutting 2× lipat, kategori tercampur) dan merapikan metodologi training/evaluasi, tapi tidak menghilangkan batasan mendasar ini. Sampaikan sebagai temuan metodologis di bab pembahasan, bukan disembunyikan sebagai kegagalan — ini kontribusi ilmiah yang valid: menunjukkan seberapa besar peran informasi non-visual dalam menentukan tingkat kerusakan jalan.

---

## Augmentasi terpisah (2026-09-24)

- [x] Tahap Augmentasi sendiri sebelum split (`/augmentasi`, `HasilAugmentasi`, loader hanya fold-train). MySQL: `scripts/migrate_add_augmentasi.sql`.
