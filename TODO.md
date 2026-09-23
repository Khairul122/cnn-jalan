# TODO â€” Evaluasi & Perbaikan CNN-Jalan

Diperbarui: 2026-09-23. Ukuran usaha: **S** < 30 menit Â· **M** 1â€“3 jam Â· **L** > 3 jam.
Status hasil terakhir (SDI, data lama): 5-fold CV MobileNetV2 = 48,9% Â± 4,5 (baseline mayoritas 42,9%); backbone beku + regresi logistik = Â±56â€“61%.
**Status hasil CV pertama yang valid (2026-09-23, split & data terbaru, setting lama sebelum perbaikan fine-tuning hari ini):** 45,4% Â± 6,7 (baseline mayoritas 50,4%, model masih **di bawah** baseline). Target 70% belum tercapai (lihat bagian C).

---

## âœ… Sudah selesai
- [x] Perbaiki `.venv` (Python 3.12, TensorFlow 2.21) â€” `.venv_lama` sudah dihapus pada P2
- [x] Ganti data model dengan `DATA JALAN REVISI.xlsx` (280 lokasi + foto), backup di `D:\flask\cnn_jalan_backup_20260922`
- [x] `panjang`/`lebar` â†’ DECIMAL meter, kolom baru `keterangan` (`migrate_revisi_lokasi.sql`)
- [x] `seed_data.py` ditulis ulang (validasi Excel sebelum hapus, `--reset`)
- [x] Bug `datetime` belum di-import di `lokasi_controller.py`
- [x] Hapus kode mati: `parse_meter`, `models/kecamatan.py`, rujukan kecamatan di `klasifikasi/upload.html`
- [x] Auto-label: baris `Estimasi (X)` memakai kelas surveyor; kode `auto_label` tidak lagi duplikat
- [x] Early stopping memakai inner-val (15% data training), fold uji tidak dipakai memilih epoch, seed tetap, tanpa file sementara
- [x] SDI, preprocessing, split, training diulang; `CLAUDE.md`/`README.md` bagian import, label, dan training diperbarui
- [x] (2026-09-22) `load_dataset` train pakai semua tahap non-acak (resize/crop/normalisasi/denoise) sebagai sampel terpisah per foto (~4x data). Inner-val di-split di level foto (`_group_aware_split`) supaya varian tahap dari foto yang sama tidak bocor antara fit dan inner-val.
- [x] (2026-09-22, revisi keputusan di atas) Val/fold uji IKUT diperbanyak sama seperti train (bukan lagi 1 gambar/foto denoise) â€” `total_data_val`/metrik CV (`evaluate()`) sekarang dihitung dari sampel yang diperbanyak. `predict_all`/`predict_cv` (GIS) & klasifikasi foto baru TIDAK ikut berubah, tetap 1 gambar/foto. **Perlu training + evaluasi CV ulang** untuk lihat dampaknya ke akurasi yang dilaporkan â€” angka akurasi CV lama (48,9% Â± 4,5) tidak lagi apple-to-apple dengan hasil setelah perubahan ini karena basis penghitungan val berubah.
- [x] (2026-09-22) Bug: tahap 'crop' identik byte-per-byte dgn 'resize' saat `crop_enabled=False` (preprocessing cuma menyalin, tanpa transformasi) â€” dihitung 2x sbg sampel terpisah. Fix: dedup berbasis hash MD5 konten file (`distinct_stage_paths`), dipakai `load_dataset` maupun statistik UI split (`effective_sample_count`). Total sampel efektif turun dari 1.120 â†’ 796 di data produksi (bukan lagi ada duplikat tersembunyi).
- [x] (2026-09-22) Root-cause dari log training: kriteria pemilihan checkpoint lama (val_loss inner terendah) kadang pilih epoch yang val_loss-nya rendah tapi akurasi fold ujinya JELEK (val_loss turun tanpa akurasi ikut membaik). Fix: `_is_better_checkpoint` sekarang utamakan **balanced accuracy** inner-val (rata-rata recall antar kelas, bukan akurasi mentah yang bias ke Sedang/mayoritas), val_loss cuma tiebreaker. **Dipertahankan** â€” tidak terbukti jadi penyebab regresi berikutnya.
- [x] (2026-09-22, **dibatalkan 2026-09-23**) Class_weight Ringan sempat di-boost 1.5x tambahan di atas `balanced` (`RINGAN_WEIGHT_BOOST`/`_boost_minority_class_weight`) karena recall-nya pernah cuma 8,3% di 1 fold. **Hasil run berikutnya (split=257, fold=1, reproducible via seed) membuktikan ini overcorrect**: rasio Ringan:Sedang jadi 3,5x â†’ model ganti bias ke Ringan/Berat, recall Sedang anjlok ke 23%, macro-F1 turun ke 37,98 (lebih jelek dari 2 run sebelumnya TANPA boost: 43,07 dan 41,67). Kode boost dicabut sepenuhnya (bukan cuma diturunkan angkanya) karena tidak ada bukti kuat untuk nilai pengganti mana pun â€” kembali ke `compute_class_weight('balanced')` polos.
- [x] **(2026-09-23) AUDIT PENUH: preprocessing, split, training, metrik evaluasi.** Preprocessing & split: tidak ditemukan bug (pipeline 5 tahap, StratifiedKFold, `_group_aware_split`, deteksi split basi semua benar; `label_basi=0` dikonfirmasi di split aktif). class_weight/confusion_matrix/precision/recall/f1 di `evaluate()` dan `metrics_service.cv_summary()`: rumus benar, urutan label (`labels=[0,1,2]` vs `target_names=['berat','sedang','ringan']`) konsisten. **Temuan kritis:** `ArsitekturConfig.pred_type` belum pernah bernilai `'cv'` sekali pun di seluruh riwayat project â€” fitur "Prediksi CV K-Fold" belum pernah dijalankan sampai selesai. Semua angka akurasi yang dilaporkan sejauh ini (33/45/53/38/36%) berasal dari `HasilEvaluasi` (1 fold saja), BUKAN `cv_summary()` (rata-rata 5 fold) yang menjadi standar pelaporan resmi. **Fix kedua:** val/fold uji di `load_dataset` dikembalikan ke 1 gambar/foto (dibatalkan dari ekspansi 4-tahap yang sempat diaktifkan 2026-09-22) â€” ekspansi val membuat `evaluate()` mengukur sampel berkorelasi, tidak sebanding dengan `cv_summary()`/`predict_cv` yang selalu 1 gambar/foto. **Tindakan wajib Anda:** jalankan "Prediksi CV K-Fold" sampai selesai (5 training run) untuk dapat `cv_summary()` yang valid â€” itu satu-satunya angka yang boleh dibandingkan dengan baseline 48,9% Â± 4,5 atau dilaporkan di skripsi.
- [x] **(2026-09-23) BUG UTAMA ditemukan & diperbaiki: `predict_cv()` selalu crash `NameError` (`SimpleNamespace` tidak di-import di scope fungsi itu) sejak awal project.** Errornya senyap karena `_cv_progress[config_id]` langsung di-`pop()` di blok `finally` sebelum sempat dibaca frontend â€” diperbaiki juga (error sekarang tetap tersimpan sampai dibaca, `predict-cv` route boleh dicoba ulang kalau attempt sebelumnya error, JS `gis.html` tampilkan `alert()` kalau gagal). **Hasil CV pertama yang valid di seluruh riwayat project:** akurasi 45,4% Â± 6,7, macro-F1 44,6%, baseline mayoritas 50,4% (model masih di bawah baseline; recall Berat/Sedang/Ringan = 50,6/43,3/43,5%, sudah tidak collapse ke 1 kelas).
- [x] **(2026-09-23) Kurangi overfitting fine-tuning** (bukti: train acc konsisten 70%+ sementara val macet 35-45% di semua log). `_apply_fine_tuning`: layer di-unfreeze MobileNetV2 15â†’8, EfficientNetB0 25â†’12; learning rate fine-tuning lr/5â†’lr/10. **Perlu training + CV ulang untuk lihat dampaknya** â€” run CV 45,4%Â±6,7 di atas masih pakai setting LAMA.
- [x] **(2026-09-23) Ensemble model fold CV + Test-Time Augmentation (TTA).** `predict_cv()` sekarang menyimpan model tiap fold (`model_{id}_fold{k}.keras`) alih-alih dibuang setelah dipakai. `predict_image()`/`predict_all()` (lewat `_resolve_prediction_models`) otomatis pakai ensemble (rata-rata probabilitas 5 model) kalau tersedia, fallback 1 model kalau belum pernah CV. Semua prediksi (termasuk `predict_cv` sendiri) pakai TTA sederhana (`_predict_with_tta`: rata-rata gambar asli + flip horizontal). `best_model()` diutamakan dari `cv_summary().macro_f1` (bukan `HasilEvaluasi` 1 fold) kalau sudah ada config yang di-CV. Model fold lama dihapus otomatis saat re-train/hapus config (`_remove_fold_models`) supaya ensemble tidak diam-diam pakai model basi.
- [x] **(2026-09-23) Clean-up struktur folder:** `app/services/cnn_service.py` (~925 baris, 1 file) dipecah jadi package `app/services/cnn_service/` (`dataset.py`, `model.py`, `training.py`, `evaluation.py`, `prediction.py` + `__init__.py` yang re-export semua nama publik) — murni reorganisasi, tanpa mengubah perilaku. Semua pemanggil (`from app.services import cnn_service`) tidak perlu berubah; 2 test yang `mock.patch.object` konstanta/helper (`MIN_TRAIN_SAMPLES`, `_load_cached`) diupdate untuk patch di submodule tempat didefinisikan. Test suite tetap 34/36 lulus (2 gagal pre-existing tidak terkait).

---

## P0 â€” Keamanan (selesai 2026-09-22, kecuali 2 item yang butuh tindakan Anda)
- [x] `/auth/register`: field `role` diabaikan, akun baru selalu `viewer`; password minimal 8 karakter (server + form); pilihan role dihapus dari form
- [x] `admin_required` (`app/auth_utils.py`) di semua route yang mengubah data; viewer hanya bisa membaca (403 â†’ pesan + redirect ke dashboard)
- [x] CSRF: Flask-WTF `CSRFProtect` + token di semua 30 form POST (tidak ada AJAX POST yang perlu header)
- [x] Login: parameter `next` hanya menerima path internal
- [x] Logout via POST (form + token)
- [x] `SECRET_KEY` dan `DATABASE_URL` wajib dari `.env` (tanpa default hard-coded); `.env.example` disediakan; cookie sesi `HttpOnly` + `SameSite=Lax`
- [x] `debug` hanya jika `FLASK_DEBUG=1` (di `.env` lokal Anda sudah 1)
- [x] Tes regresi: `tests/test_security.py` (8 tes; jalankan `python -m unittest discover -s tests -t . -v`)
- [ ] **Tindakan Anda:** ganti password akun default `admin@gmail.com` (masih `12345678`): `python scripts/create_admin.py --email admin@gmail.com`
- [ ] **Tindakan Anda:** beri password pada user MySQL `root` lalu isi `DATABASE_URL` di `.env` (sekarang masih `root:` tanpa password, sama seperti sebelumnya)
- [ ] (opsional, S) Sembunyikan tombol aksi untuk viewer di template; sekarang tombol tetap tampil tetapi ditolak server

## P1 â€” Bug fungsional (selesai 2026-09-22)
- [x] `arsitektur.train`: klaim status atomik, permintaan kedua ditolak; model lama dihapus saat training ulang
- [x] Status `training` menggantung â†’ `tandai_training_terputus()` dipanggil di `run.py` saat start
- [x] Progress bar: total epoch dihitung ulang setelah fase 1 berhenti lebih awal
- [x] `klasifikasi`: inferensi nyata dengan model terbaik; tanpa model â†’ ditolak (tidak ada data acak); jenis dikosongkan
- [x] `klasifikasi.upload`: validasi lokasi, isi file harus gambar, folder upload dibuat otomatis (`app/uploads.py`, dipakai juga oleh `lokasi`)
- [x] `split.export`: nama file disanitasi (`secure_filename`)
- [x] Halaman detail: "Akurasi Model Final" (dari evaluasi) menggantikan "Best Val Accuracy"; label kolom fold uji diperjelas
- [x] Mode Single: peringatan di halaman GIS; ringkasan CV ditampilkan bila tersedia

## P1 â€” Metodologi (selesai 2026-09-22; keputusan pemilik tercatat)
- [x] **Keputusan:** label semua dari SDI (PÃ—L). Kolom `keterangan` hanya informasi. Konsekuensi (catat di pembahasan): akurasi CNN cenderung mendekati baseline kelas mayoritas (~46â€“52%)
- [x] **Keputusan:** sistem = klasifikasi **tingkat** kerusakan saja (jenis tidak diklasifikasi; teks login/register/landing/README/CLAUDE.md disesuaikan; tabel `jenis_kerusakan` dibiarkan)
- [x] **Keputusan:** evaluasi = 5-fold CV (angka utama) + model final pada semua data (`train_final`, tombol di halaman detail, langkah terakhir `run_pipeline.py`)
- [x] **Keputusan:** preprocessing tetap 5 tahap, 5 file/foto (augmentasi = tahap terakhir, hanya visualisasi)
- [x] 5-fold CV sebagai metrik utama di UI (`cv_summary`)
- [x] Augmentasi tidak memengaruhi data training
- [x] `split_item` basi terdeteksi (banner + training ditolak)
- [x] Skrip pipeline ulang sekali jalan: `scripts/run_pipeline.py`
- [ ] **(L, opsional)** Opsi model "backbone beku + regresi logistik" (EfficientNetB0 + ConvNeXtTiny, Â±56â€“61% dengan label surveyor; dengan label SDI Â±46â€“52%)

## P2 â€” Kualitas kode
- [x] (M) `cnn_service.py`: subquery preprocessing disatukan menjadi `_preprocessed_subquery()`
- [x] (S) `arsitektur_controller`: logika POST evaluasi disatukan; `_Cfg` diganti `types.SimpleNamespace`
- [x] (S) Deprecation: API datetime dan `Query.get()` diganti API modern
- [x] (S) Tes tambahan P2 untuk SDI, `SplitService`, dan `seed_data.read_excel`
- [ ] **(S)** `git init` + commit awal (project belum berupa repo)
- [x] (S) Hapus dump SQL lama `database/db_cnn_jalan.sql`
- [x] (S) Hapus utilitas dan generator data lama yang sudah tidak dipakai

## P2 â€” Housekeeping (butuh izin Anda karena menghapus file)
- [x] Hapus data Excel/PDF/script lama
- [x] Hapus generator SQL/data lama
- [x] Hapus log training lama
- [x] Hapus `.venv_lama`
- [x] Hapus backup lama setelah verifikasi

## P2 â€” Dokumentasi
- [x] (S) `CLAUDE.md`: status akurasi diperbarui dengan hasil CV terbaru
- [x] (S) `README.md`: struktur folder dan setup diperbarui
- [x] (S) `studi.md` / `transfer_knowledge.md`: alur lama diperbarui

---

## Urutan yang disarankan
1. P0 keamanan (Â±1 hari kerja ringan) â†’ 2. Metodologi: CV sebagai metrik utama + augmentasi ke training + preprocessing ringkas â†’ 3. Bug P1 â†’ 4. Kualitas kode & tes â†’ 5. Housekeeping dan dokumentasi.

