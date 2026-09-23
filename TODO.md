# TODO — Rewrite CNN-Jalan Berdasarkan Audit Menyeluruh

Disusun: 23 September 2026. Dasar: audit kode aktual (`app/services/cnn_service/`, `app/models/label_kerusakan.py`, `app/controllers/arsitektur_controller.py`, template `arsitektur/`) dibandingkan dengan `studi.md`, `CLAUDE.md`, dan `TODO.md` proyek yang sudah ada, plus tinjauan metodologi machine learning umum.

Ukuran usaha: **S** kurang dari 30 menit · **M** 1–3 jam · **L** lebih dari 3 jam · **XL** butuh beberapa sesi kerja.

Status ringkas sebelum perbaikan: akurasi CV resmi pertama yang valid = 45,4% ± 6,7, di bawah baseline kelas mayoritas 50,4%. Target skripsi 70% belum tercapai dan kemungkinan besar tidak tercapai murni dari jalur foto saja, kecuali akar masalah label diperbaiki.

---

## P0 — Perbaikan Kritis (Kerjakan Dulu, Sebelum Eksperimen Apa Pun)

Bagian ini harus selesai dulu supaya semua eksperimen berikutnya diukur dengan angka yang benar dan konsisten.

- [ ] **Perbaiki inkonsistensi pemilihan "model terbaik" di UI.** `arsitektur_controller.py::index()` masih memilih `best_id` berdasarkan `HasilEvaluasi.akurasi` (metrik 1 fold), bukan `cv_summary().macro_f1`. Ini bertentangan dengan `prediction.py::best_model()` yang sudah benar memprioritaskan metrik CV. Ganti logika di `index()` supaya konsisten pakai `cv_summary().macro_f1` untuk config yang sudah punya `pred_type='cv'`, fallback ke `HasilEvaluasi.akurasi` hanya kalau belum ada CV sama sekali. Update juga label kolom "Akurasi" di `arsitektur/index.html` (baris 54, 98) supaya jelas menyebut sumber angkanya (CV atau 1 fold). **(M)**
- [ ] **Buat split baru (jangan reuse split lama) sebelum baseline CV berikutnya.** `split_service.py` sekarang group-aware terhadap foto near-duplicate (`dedup_service.py`, average-hash + union-find, baru ditambahkan) — di 280 foto saat ini terdeteksi 31 foto near-duplicate yang split lama (`StratifiedKFold` polos) bisa taruh di fold train dan val berbeda sekaligus (leakage). Split lama yang dibuat sebelum perubahan ini **tidak otomatis diperbaiki** — harus dibuat split baru dari `/split/new` supaya baseline CV di bawah ini bersih dari leakage duplikat sejak awal. **(S)**
- [x] **Jalankan ulang "Prediksi CV K-Fold" dengan setting fine-tuning terbaru** (MobileNetV2 8 layer, EfficientNetB0 12 layer, LR fine-tune dibagi 10). **Selesai 2026-09-24** (`scripts/run_pipeline.py --skip-preprocessing --lr 0.0001 --epochs 80 --k 5 --model mobilenetv2`, split baru near-dup-aware `split_config_id=483`, `arsitektur_id=279`). Hasil:
  **akurasi 47,1% ± 6,1, macro-F1 45,8%, baseline 50,4% (selisih −3,2 poin) — masih di BAWAH baseline.**
  Perbaikan kecil dari 45,4%/44,6% sebelumnya, kesimpulan tidak berubah. Mesin CPU-only — total waktu ~7,7 jam
  (training tunggal 405 menit, CV 5-fold 46 menit, model final 13 menit). Detail riwayat angka di `CLAUDE.md`
  "Status Akurasi CNN". **(L, selesai — jauh lebih lama dari estimasi karena CPU-only)**
- [ ] **Audit ulang semua tempat yang menampilkan atau membandingkan angka akurasi** (dashboard, halaman detail arsitektur, landing page publik) untuk memastikan tidak ada lagi tempat yang diam-diam memakai `HasilEvaluasi.akurasi` sebagai klaim akurasi akhir. Beri label eksplisit "1 fold, bukan metrik resmi" di setiap tempat yang menampilkannya. **(M)**
- [ ] **Perbaiki dan sinkronkan dokumentasi (`studi.md`, `CLAUDE.md`, `README.md`)** supaya mencerminkan kode yang benar-benar berjalan, bukan snapshot 29 Mei 2026. Setiap kali skema training/preprocessing/arsitektur berubah setelah ini, update dokumentasi di commit yang sama. **(M)**

---

## P1 — Pelabelan (SDI)

- [ ] **Pertahankan `hitung_sdi()` apa adanya.** Sudah 100% sesuai standar Bina Marga (F_retak, F_lubang, F_rutting, threshold Ringan/Sedang/Berat). Tidak perlu diubah.
- [x] **Perbaiki `estimasi_dari_dimensi()`.** Opsi A dipilih (2026-09-23, keputusan pemilik) — diganti ke formula kontinu
  (`persen_retak = min(luas/REF_RETAK,100)`, `jumlah_lubang = luas/0,1` dipotong di 999, `kedalaman_rutting =
  min(luas/REF_RUTTING,5)`, `jenis_retak` = 'lebar' kalau luas>2m²). Konstanta kalibrasi (REF_RETAK=1.0,
  REF_RUTTING=4.0, AMBANG_LEBAR=2.0) didokumentasikan di `CLAUDE.md` dan `label_kerusakan.py`. Test regresi di
  `tests/test_p2.py`. **Belum di-apply ke DB** — `label_kerusakan` masih berisi nilai lama sampai `/label/auto`
  dijalankan ulang; sengaja ditunda supaya tidak balapan dengan baseline CV P0 yang masih training (lihat item split
  baru di atas — split & CV P0 pakai snapshot label LAMA, itu memang disengaja untuk isolasi variabel). **(M, selesai)**
- [x] **Audit label yang berada dekat ambang batas SDI** (mendekati 50 dan 150). `scripts/audit_sdi_borderline.py`
  dibuat dan dijalankan pada label lama (tabel diskrit): **0 dari 280 label dekat ambang batas** — bukan karena
  datanya tidak ambigu, tapi karena tabel diskrit lama cuma menghasilkan 5 nilai SDI tetap (20/25/75/135/195) yang
  semuanya jauh dari 50/150. Ini bukti tambahan kenapa Opsi A perlu — tabel lama secara struktural tidak bisa
  merepresentasikan kasus borderline. Jalankan ulang script ini setelah `/label/auto` dijalankan dengan formula baru
  untuk audit borderline yang sebenarnya. **(M, selesai — perlu rerun setelah relabel)**
- [ ] **Latih model kedua dengan label surveyor** (kolom `keterangan` pada baris Estimasi) sebagai target, untuk subset data yang punya kedua sumber label. Bandingkan macro-F1 dengan model label SDI. Catatan proyek menunjukkan label surveyor memberi macro-F1 lebih tinggi (~56–61%) dibanding SDI dari P×L (~46–52%).
  **Script siap** (`scripts/run_surveyor_cv.py`, 2026-09-23) — subset 147 foto berkeratangan `Estimasi (Ringan|Sedang|Berat)`
  (133 foto `Ukur` dikecualikan, tidak punya penilaian kelas surveyor independen), split terpisah + near-dup-aware,
  reuse penuh `_run_training`/`_run_cv_predict`. **Belum dijalankan** — antre setelah pipeline CV P0 selesai (CPU-only,
  jalan paralel cuma akan memperlambat keduanya berebut core yang sama). **(L, tertunda)**
- [ ] **Laporkan kedua sumber label secara berdampingan di bab pembahasan skripsi**, jangan cuma pilih satu yang hasilnya lebih baik. Jelaskan kenapa SDI dari P×L secara struktural tidak sepenuhnya tampak di foto tanpa skala. **(S, penulisan)**

---

## P2 — Preprocessing

- [x] **Ganti default denoise dari Gaussian/Median ke Bilateral Filter**, kernel kecil (3 atau 5). Config yang aktif dipakai
  training sudah `bilateral` k=3 sebelum item ini dikerjakan; yang diubah 2026-09-23: default SKEMA (`preprocessing_config.denoise_method`)
  dari `none` → `bilateral` supaya config baru mulai dari rekomendasi ini, bukan "tanpa denoise". **Ablation tanpa
  denoise sama sekali BELUM dijalankan** — perlu preprocessing ulang + split + CV baru, antre di belakang P0/P1 item 4
  (CPU-only, satu training pipeline dalam satu waktu). **(M, default selesai — ablation tertunda)**
- [x] **Tambahkan opsi CLAHE** di `norm_method` (`preprocessing_service.py` — CLAHE di kanal L LAB, `clipLimit=2.0`,
  `tileGridSize=(8,8)`), migration `migrate_add_clahe_norm.sql` sudah diterapkan. Belum dibandingkan lewat CV terhadap
  minmax/zscore — sama seperti item denoise, ablation perlu run baru. **(M, opsi selesai — ablation tertunda)**
- [ ] **Ganti center crop generik dengan ROI-aware crop.** **Diskip (keputusan pemilik, 2026-09-23)** — butuh anotasi
  bounding box manual 280 foto yang belum tersedia. Revisit kalau anotasi sudah ada. **(L, kerja anotasi manual — diskip)**
- [x] **Tambahkan tahap koreksi iluminasi** — gray-world white balance (`PreprocessingService._gray_world_white_balance`),
  toggle `illum_correction` di preprocessing_config, diterapkan SEBELUM resize (Step 1). Migration
  `migrate_add_illum_correction.sql` sudah diterapkan. Diuji manual: color cast [80,100,180] → [119,119,119] rata kanal
  setelah koreksi. **(M, selesai)**
- [x] **Perbaiki urutan pipeline supaya konsisten dengan dokumentasi.** Ditemukan: `CLAUDE.md` menulis bullet Step 5
  (Augmentasi) SEBELUM Step 4 (Denoise), padahal kode & penomoran sama-sama Denoise dulu. Urutan bullet di `CLAUDE.md`
  diperbaiki mengikuti kode (kode adalah yang benar). **(S, selesai)**
- [ ] **(Eksperimen opsional) Tambahkan edge map (Canny/Sobel) sebagai kanal ke-4 input.** **Diskip (keputusan pemilik,
  2026-09-23)** — akan mengorbankan kompatibilitas transfer learning ImageNet (backbone pretrained perlu input 3-kanal)
  untuk dataset yang sudah sangat bergantung padanya karena kecil. **(L, perlu ubah arsitektur input — diskip)**

---

## P3 — Augmentasi

- [ ] **Pertahankan pembatasan yang sudah benar**: flip vertikal tetap dihapus, rotasi tetap dibatasi kecil (sekitar ±18 derajat). Jangan diubah, karena jalan terbalik atau miring ekstrem tidak realistis.
- [x] **Tambahkan color jitter** (hue & saturasi ringan) di layer augmentasi model. `model.py::build_model` — `RandomHue(0.05)` +
  `RandomSaturation((0.4,0.6))` (Keras 3.15 native layers, value_range=(0,255) konsisten dgn layer lain). **(S, selesai)**
- [x] **Implementasikan Mixup** di level batch lewat `tf.data` (bukan layer Keras preprocessing — TODO.md sendiri
  menyebut "Mixup ATAU CutMix", Mixup dipilih karena CutMix menambah kompleksitas spatial-box yang sama tanpa manfaat
  tambahan untuk tujuan ini). `training.py::_mixup_dataset` + `_fit_phase(..., mixup_alpha=)`. **Opt-in murni**
  (`ArsitekturConfig.mixup_alpha`, default 0 = TIDAK ada perubahan perilaku sama sekali dari sebelumnya). Saat aktif:
  loss otomatis `CategoricalCrossentropy` (`model.py::_make_loss`), `class_weight` dibaurkan jadi `sample_weight`
  per-batch (bukan dibuang) supaya penanganan imbalance kelas tetap jalan meski label sudah soft. Diuji smoke-test
  end-to-end (dataset shapes, `model.fit()`, `_fit_phase` penuh dgn callback checkpoint) — **belum divalidasi lewat CV
  sungguhan** (antre di belakang eksperimen lain, CPU-only). Field baru di form `/arsitektur/new`. **(M→sedikit lebih,
  selesai — validasi CV tertunda)**
- [x] **Tambahkan Cutout / Random Erasing** — `RandomErasing(factor=0.5, scale=(0.02,0.08))` (Keras 3.15 native,
  patch 2-8% luas, di bawah 10% sesuai TODO). **(M, selesai)**
- [x] **Tambahkan noise sintetis ringan** setelah augmentasi lain saat training. `GaussianNoise` bawaan Keras
  ternyata membatasi stddev ke [0,1] (asumsi input ternormalisasi) — tidak cocok dengan pipeline [0,255] ini, jadi
  dibuat `_pixel_gaussian_noise_layer` kecil (logika sama, tanpa batasan itu), stddev=3.0. **(S, selesai)**
- [x] **Perluas Test-Time Augmentation** ke 5-crop (tengah + 4 sudut, 87,5% lalu di-resize balik) × flip horizontal
  = 10 view, dari sebelumnya cuma 2 view (asli+flip). `prediction.py::_five_crop_flip_views` + `_predict_with_tta`
  diupdate. Test regresi di `tests/test_p2.py` (shape, flip correctness, averaging). **Konsekuensi:** prediksi jadi
  ~5x lebih lambat (10 forward pass vs 2) — untuk 280 foto di CPU-only ini AKAN memperlambat `predict_all`/`predict_cv`
  secara nyata; belum diukur end-to-end. **(M, selesai — dampak kecepatan belum diukur)**

---

## P4 — Arsitektur Model

- [x] **Uji Jalur A (foto saja, backbone beku penuh).** `ArsitekturConfig.skip_fine_tuning` (opt-in, default False = perilaku
  lama tidak berubah) — kalau True, `train()` melewati Phase 2 sepenuhnya dan pakai bobot Phase 1 apa adanya. Field
  baru di form `/arsitektur/new`. Diuji smoke-test (`train()` penuh dgn `load_dataset` di-mock, 2 epoch, tanpa Phase 2
  terpanggil). **Belum dibandingkan lewat CV sungguhan** — antre di belakang eksperimen lain. **(M, kode selesai — CV tertunda)**
- [x] **Sederhanakan kepala klasifikasi.** Dibuat CONFIGURABLE (`dense_units` default 64, `dense_l2` default 1e-4 di
  `ArsitekturConfig`), bukan hardcode salah satu opsi — bisa uji `Dense(32)` ATAU `L2=1e-3` (atau kombinasi) langsung
  dari UI tanpa ubah kode. Default tetap 64/1e-4, perilaku lama tidak berubah. **(S, kode selesai — ablation tertunda)**
- [ ] **(Eksperimen, dilaporkan sebagai pembanding) Bangun Jalur B: model hybrid foto + tabular.** **Belum dikerjakan**
  — perlu keputusan pemilik dulu (lihat pertanyaan terpisah), effort besar (L): cabang input tabular baru, dataset
  loader baru yang ikut kembalikan panjang/lebar/jenis per sampel, training/prediction path terpisah. **(L, tertunda)**
- [ ] **Cari bobot pretrained yang lebih dekat ke domain jalan** (CRACK500/GAPs). **Belum dikerjakan** — perlu keputusan
  pemilik dulu (riset dataset publik, kemungkinan besar bukan format Keras siap-pakai untuk MobileNetV2/EfficientNetB0,
  bisa berarti retrain dari awal di dataset itu — proyek terpisah, bukan cuma "ganti weights='imagenet'"). **(L, tertunda)**
- [x] **Tambahkan label smoothing.** `ArsitekturConfig.label_smoothing` (opt-in, default 0). Aktif tanpa Mixup → label
  di-onehot (tanpa dicampur antar sampel, beda dari Mixup), `CategoricalCrossentropy(label_smoothing=X)`, class_weight
  tetap jalan lewat `sample_weight`. Field baru di form. **Belum divalidasi lewat CV.** **(S, kode selesai — validasi tertunda)**

---

## P5 — Training

- [ ] **Jalankan CV dengan setting fine-tuning terbaru sebagai baseline baru** sebelum menambahkan perubahan lain (lihat P0). **(L)**
- [ ] **Pertimbangkan ulang strategi ekspansi data training.** `dataset.py::load_dataset` memakai output tiap tahap preprocessing (resize/crop/normalisasi/denoise) sebagai sampel terpisah untuk foto yang sama. Sampel-sampel ini sangat berkorelasi (bukan variasi independen), berisiko memberi ilusi dataset lebih besar tanpa menambah informasi baru. Uji ablation: bandingkan performa dengan dan tanpa ekspansi ini. **(M, eksperimen)**
- [ ] **Perbesar proporsi atau perbanyak inner-validation** jika memungkinkan. Saat ini cuma 15% dari sekitar 224 foto (~34 foto), terlalu kecil untuk keputusan EarlyStopping/ReduceLROnPlateau yang stabil. Pertimbangkan naikkan `INNER_VAL_FRAC` atau pakai nested CV untuk estimasi yang lebih stabil. **(M)**
- [ ] **Jalankan CV berulang (repeated stratified k-fold)**, misalnya 3 pengulangan dengan `random_state` berbeda, untuk mengurangi noise pada estimasi akurasi. Standar deviasi 6,7 poin pada satu putaran CV terlalu besar untuk disimpulkan dengan percaya diri. **(XL, butuh banyak training run)**
- [ ] **Setiap perubahan (preprocessing, augmentasi, arsitektur) diuji satu per satu lewat CV penuh**, bukan digabung sekaligus. Catat hasil `cv_summary()` setiap eksperimen di tabel terpisah supaya kontribusi tiap perubahan jelas. **(Aturan kerja, bukan tugas satu kali)**

---

## P6 — Evaluasi dan Metrik

- [ ] **Tetapkan `cv_summary()` sebagai satu-satunya angka resmi** yang boleh dilaporkan di skripsi. `HasilEvaluasi` (1 fold) hanya untuk debugging internal, tidak untuk klaim akurasi akhir. **(Aturan kerja)**
- [ ] **Setiap laporan angka akurasi wajib menyertakan**: rata-rata, standar deviasi antar fold, baseline kelas mayoritas, macro-F1, dan confusion matrix. Tidak cukup cuma satu angka akurasi tunggal. **(S, template laporan)**
- [ ] **Tambahkan analisis pola kesalahan dari confusion matrix**, khususnya seberapa sering kesalahan terjadi antar kelas berdekatan (Berat–Sedang, Sedang–Ringan) dibanding antar kelas jauh (Berat–Ringan). Kelas kerusakan bersifat berjenjang (ordinal), jadi pola ini relevan untuk pembahasan. **(M, analisis)**
- [ ] **Tambahkan analisis tambahan klasifikasi 2 kelas** (perlu perbaikan segera vs tidak), sebagai pembanding granularitas kasar terhadap 3 kelas asli. **(M)**
- [ ] **(Opsional, eksperimen) Coba pendekatan ordinal** (ordinal loss atau regresi SDI langsung lalu threshold) alih-alih softmax 3-kelas nominal biasa, untuk memanfaatkan struktur berjenjang antar kelas. **(L)**

---

## P7 — Dokumentasi dan Kualitas Kode

- [ ] Perbarui `studi.md` seluruhnya supaya mencerminkan skema yang benar-benar dipakai setelah semua perbaikan di atas selesai, bukan snapshot lama. **(M)**
- [ ] Perbarui `CLAUDE.md` bagian "Status Akurasi CNN" setiap kali ada hasil CV baru yang valid. **(S, berulang)**
- [ ] Tambahkan test regresi untuk `LabelKerusakan.hitung_sdi()` dan `estimasi_dari_dimensi()` (setelah diperbaiki di P1) di `tests/`, supaya perubahan berikutnya tidak diam-diam menyimpang lagi dari skema yang didokumentasikan. **(M)**
- [ ] Tambahkan test regresi untuk `metrics_service.cv_summary()` memastikan urutan label (`labels=[0,1,2]` vs `KELAS = ('berat','sedang','ringan')`) tetap konsisten kalau ada refactor. **(S)**

---

## Rencana Eksekusi yang Disarankan

Kerjakan berurutan, jangan lompat, supaya setiap angka yang dihasilkan bisa dipercaya untuk dibandingkan dengan angka sebelumnya:

1. P0 seluruhnya (perbaikan kritis dan baseline CV baru yang valid dengan setting hari ini)
2. P1 (pelabelan) — ini akar masalah paling besar, kerjakan sebelum tuning model lebih jauh
3. P2 dan P3 (preprocessing dan augmentasi), diuji satu per satu lewat ablation
4. P4 dan P5 (arsitektur dan training), termasuk perbandingan Jalur A vs Jalur B
5. P6 (evaluasi) diterapkan di sepanjang proses, bukan cuma di akhir
6. P7 (dokumentasi) diperbarui berkelanjutan, bukan ditumpuk di akhir

## Catatan Kejujuran Akademik

Target akurasi di atas 70% kemungkinan besar tidak tercapai murni dari Jalur A (foto saja), berapa pun perbaikan preprocessing dan augmentasi yang dilakukan, karena akar masalahnya di ketersediaan informasi pada foto, bukan di kapasitas model. Jalur B (model hybrid dengan data tabular) berpotensi melewati 70%, tapi itu karena model diberi akses langsung ke faktor penentu label. Sampaikan ini secara eksplisit di bab pembahasan sebagai temuan, bukan disembunyikan. Ini kontribusi ilmiah yang valid: menunjukkan seberapa besar peran informasi non-visual dalam menentukan tingkat kerusakan jalan, dan seberapa jauh CNN murni bisa mendekati itu hanya dari foto.