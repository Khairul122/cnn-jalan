# TODO — Rewrite CNN-Jalan Berdasarkan Audit Menyeluruh

Disusun: 23 September 2026. Dasar: audit kode aktual (`app/services/cnn_service/`, `app/models/label_kerusakan.py`, `app/controllers/arsitektur_controller.py`, template `arsitektur/`) dibandingkan dengan `studi.md`, `CLAUDE.md`, dan `TODO.md` proyek yang sudah ada, plus tinjauan metodologi machine learning umum.

Ukuran usaha: **S** kurang dari 30 menit · **M** 1–3 jam · **L** lebih dari 3 jam · **XL** butuh beberapa sesi kerja.

Status ringkas sebelum perbaikan: akurasi CV resmi pertama yang valid = 45,4% ± 6,7, di bawah baseline kelas mayoritas 50,4%. Target skripsi 70% belum tercapai dan kemungkinan besar tidak tercapai murni dari jalur foto saja, kecuali akar masalah label diperbaiki.

---

## P0 — Perbaikan Kritis (Kerjakan Dulu, Sebelum Eksperimen Apa Pun)

Bagian ini harus selesai dulu supaya semua eksperimen berikutnya diukur dengan angka yang benar dan konsisten.

- [ ] **Perbaiki inkonsistensi pemilihan "model terbaik" di UI.** `arsitektur_controller.py::index()` masih memilih `best_id` berdasarkan `HasilEvaluasi.akurasi` (metrik 1 fold), bukan `cv_summary().macro_f1`. Ini bertentangan dengan `prediction.py::best_model()` yang sudah benar memprioritaskan metrik CV. Ganti logika di `index()` supaya konsisten pakai `cv_summary().macro_f1` untuk config yang sudah punya `pred_type='cv'`, fallback ke `HasilEvaluasi.akurasi` hanya kalau belum ada CV sama sekali. Update juga label kolom "Akurasi" di `arsitektur/index.html` (baris 54, 98) supaya jelas menyebut sumber angkanya (CV atau 1 fold). **(M)**
- [ ] **Buat split baru (jangan reuse split lama) sebelum baseline CV berikutnya.** `split_service.py` sekarang group-aware terhadap foto near-duplicate (`dedup_service.py`, average-hash + union-find, baru ditambahkan) — di 280 foto saat ini terdeteksi 31 foto near-duplicate yang split lama (`StratifiedKFold` polos) bisa taruh di fold train dan val berbeda sekaligus (leakage). Split lama yang dibuat sebelum perubahan ini **tidak otomatis diperbaiki** — harus dibuat split baru dari `/split/new` supaya baseline CV di bawah ini bersih dari leakage duplikat sejak awal. **(S)**
- [ ] **Jalankan ulang "Prediksi CV K-Fold" dengan setting fine-tuning terbaru** (MobileNetV2 8 layer, EfficientNetB0 12 layer, LR fine-tune dibagi 10) sebelum mengubah apa pun lagi. Angka 45,4% ± 6,7 yang ada sekarang masih pakai setting fine-tuning lama, jadi belum mencerminkan perbaikan overfitting yang sudah diterapkan hari ini. **Pastikan pakai split baru (lihat item di atas), bukan split lama.** **(L, butuh 5 training run penuh)**
- [ ] **Audit ulang semua tempat yang menampilkan atau membandingkan angka akurasi** (dashboard, halaman detail arsitektur, landing page publik) untuk memastikan tidak ada lagi tempat yang diam-diam memakai `HasilEvaluasi.akurasi` sebagai klaim akurasi akhir. Beri label eksplisit "1 fold, bukan metrik resmi" di setiap tempat yang menampilkannya. **(M)**
- [ ] **Perbaiki dan sinkronkan dokumentasi (`studi.md`, `CLAUDE.md`, `README.md`)** supaya mencerminkan kode yang benar-benar berjalan, bukan snapshot 29 Mei 2026. Setiap kali skema training/preprocessing/arsitektur berubah setelah ini, update dokumentasi di commit yang sama. **(M)**

---

## P1 — Pelabelan (SDI)

- [ ] **Pertahankan `hitung_sdi()` apa adanya.** Sudah 100% sesuai standar Bina Marga (F_retak, F_lubang, F_rutting, threshold Ringan/Sedang/Berat). Tidak perlu diubah.
- [ ] **Perbaiki `estimasi_dari_dimensi()`.** Implementasi saat ini pakai tabel lookup diskrit 5 kelompok luas (≤0,5 / ≤2 / ≤6 / ≤12 / >12 m²) dengan nilai hardcoded, menyimpang dari formula kontinu yang didokumentasikan di `studi.md` (`persen_retak = min(luas/referensi, 100)`, `jumlah_lubang = luas/0,1`). Pilih salah satu:
  - **Opsi A:** ganti ke formula kontinu sesuai draft asli di `studi.md`, tentukan nilai `referensi` yang masuk akal dan didokumentasikan alasannya.
  - **Opsi B:** tetap pakai tabel diskrit, tapi tuliskan justifikasi ambang batas dan nilai parameter di `CLAUDE.md`, idealnya dirujuk ke observasi lapangan atau literatur Bina Marga.
  
  **(M)**
- [ ] **Audit label yang berada dekat ambang batas SDI** (mendekati 50 dan 150). Tandai baris ini di database untuk analisis kesalahan terpisah karena paling rawan salah klasifikasi. **(M)**
- [ ] **Latih model kedua dengan label surveyor** (kolom `keterangan` pada baris Estimasi) sebagai target, untuk subset data yang punya kedua sumber label. Bandingkan macro-F1 dengan model label SDI. Catatan proyek menunjukkan label surveyor memberi macro-F1 lebih tinggi (~56–61%) dibanding SDI dari P×L (~46–52%). **(L)**
- [ ] **Laporkan kedua sumber label secara berdampingan di bab pembahasan skripsi**, jangan cuma pilih satu yang hasilnya lebih baik. Jelaskan kenapa SDI dari P×L secara struktural tidak sepenuhnya tampak di foto tanpa skala. **(S, penulisan)**

---

## P2 — Preprocessing

- [ ] **Ganti default denoise dari Gaussian/Median ke Bilateral Filter**, kernel kecil (3 atau 5). Bilateral mempertahankan tepi retak sambil meredam noise di area datar. Uji juga varian tanpa denoise sama sekali sebagai pembanding ablation, karena blur berisiko menghilangkan retak halus yang jadi sinyal utama kelas. **(M)**
- [ ] **Tambahkan opsi CLAHE (Contrast Limited Adaptive Histogram Equalization)** di kanal luminance sebagai pilihan baru di `norm_method`, selain minmax/zscore/none. CLAHE menonjolkan kontras lokal tanpa merusak kontras absolut antar foto seperti minmax global. **(M)**
- [ ] **Ganti center crop generik dengan ROI-aware crop.** Anotasi bounding box area kerusakan untuk 280 foto (pakai LabelImg atau Roboflow, kerja satu kali), lalu crop ke area itu sebelum masuk pipeline. Sediakan fallback ke center crop kalau anotasi belum tersedia untuk foto tertentu. **(L, kerja anotasi manual)**
- [ ] **Tambahkan tahap koreksi iluminasi** (gray-world white balance atau histogram matching ke satu foto referensi), sebelum atau sesudah resize, untuk mengurangi variasi pencahayaan antar sesi pemotretan lapangan. **(M)**
- [ ] **Perbaiki urutan pipeline supaya konsisten dengan dokumentasi**, atau perbarui dokumentasi supaya sesuai urutan kode saat ini (Resize → Crop → Normalisasi → Denoise → Augmentasi). Pastikan `studi.md` dan `CLAUDE.md` menyebut urutan yang sama. **(S)**
- [ ] **(Eksperimen opsional) Tambahkan edge map (Canny/Sobel) sebagai kanal ke-4 input**, digabung dengan RGB, untuk memberi sinyal eksplisit lokasi tepi retak ke model. **(L, perlu ubah arsitektur input)**

---

## P3 — Augmentasi

- [ ] **Pertahankan pembatasan yang sudah benar**: flip vertikal tetap dihapus, rotasi tetap dibatasi kecil (sekitar ±18 derajat). Jangan diubah, karena jalan terbalik atau miring ekstrem tidak realistis.
- [ ] **Tambahkan color jitter** (variasi hue dan saturasi ringan) di layer augmentasi model, selain brightness dan contrast yang sudah ada. **(S)**
- [ ] **Implementasikan Mixup atau CutMix** di level batch lewat `tf.data`, bukan layer Keras preprocessing biasa (layer bawaan Keras tidak mendukung ini). Campur dua foto dan label secara proporsional untuk membuat sampel sintetis baru. **(M)**
- [ ] **Tambahkan Cutout / Random Erasing** dengan patch kecil (di bawah 10% luas gambar) saat training, supaya model tidak terlalu bergantung pada satu titik kerusakan paling mencolok. **(M)**
- [ ] **Tambahkan noise sintetis ringan** (Gaussian noise) setelah tahap denoise saat training, melatih model tahan terhadap variasi sensor kamera lapangan. **(S)**
- [ ] **Perluas Test-Time Augmentation** di `prediction.py::_predict_with_tta` dari sekadar flip horizontal menjadi kombinasi flip horizontal dan multi-crop (5-crop: tengah + 4 sudut), dirata-ratakan. **(M)**

---

## P4 — Arsitektur Model

- [ ] **Uji Jalur A (foto saja, backbone beku penuh).** Coba matikan Phase 2 fine-tuning sepenuhnya, bandingkan dengan Phase 1+2 seperti sekarang. Catatan proyek menyebut backbone beku + classifier sederhana sudah mengalahkan CNN fine-tuned pada eksperimen sebelumnya (~56–61% dengan label surveyor). **(M)**
- [ ] **Sederhanakan kepala klasifikasi.** Turunkan `Dense(64)` ke `Dense(32)`, atau naikkan L2 regularizer dari `1e-4` ke `1e-3` di `model.py::build_model`. Dataset kecil (224 foto per fold) rawan overfit pada kepala yang terlalu besar. **(S)**
- [ ] **(Eksperimen, dilaporkan sebagai pembanding) Bangun Jalur B: model hybrid foto + tabular.** Tambahkan cabang input numerik untuk panjang, lebar, dan jenis kerusakan, digabung dengan embedding CNN sebelum dense layer terakhir. Laporkan sebagai ablation study terpisah dengan catatan metodologis: jalur ini menunjukkan batas atas performa ketika model diberi akses langsung ke faktor penentu label, bukan murni belajar dari visual. **(L)**
- [ ] **Cari bobot pretrained yang lebih dekat ke domain jalan** (dataset publik seperti CRACK500 atau GAPs), pakai sebagai titik awal alih-alih ImageNet murni. **(L, riset + integrasi)**
- [ ] **Tambahkan label smoothing** pada loss function (`SparseCategoricalCrossentropy(label_smoothing=...)`), membantu mengurangi rasa percaya diri berlebih pada label yang berada dekat ambang batas SDI. **(S)**

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