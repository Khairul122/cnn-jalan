-- Pindah dari 3 kelas (Berat/Sedang/Ringan) ke 4 kategori SDI Bina Marga.
-- id = indeks kelas CNN + 1. Data turunan (split, training, prediksi, label) HARUS dibuat ulang
-- karena semantik id berubah; jalankan setelah data lama dicadangkan/dibersihkan.
DELETE FROM prediksi_model;
DELETE FROM hasil_evaluasi;
DELETE FROM hasil_training;
DELETE FROM arsitektur_config;
DELETE FROM split_item;
DELETE FROM split_config;
DELETE FROM hasil_klasifikasi_cnn;

UPDATE tingkat_kerusakan SET nama_tingkat='Rusak Berat',  warna_peta='#E53E3E', skor_prioritas=1 WHERE id=1;
UPDATE tingkat_kerusakan SET nama_tingkat='Rusak Ringan', warna_peta='#F97316', skor_prioritas=2 WHERE id=2;
UPDATE tingkat_kerusakan SET nama_tingkat='Sedang',       warna_peta='#F59E0B', skor_prioritas=3 WHERE id=3;
INSERT INTO tingkat_kerusakan (id, nama_tingkat, warna_peta, skor_prioritas) VALUES (4, 'Baik', '#10B981', 4);

ALTER TABLE hasil_evaluasi
  DROP COLUMN precision_berat,  DROP COLUMN recall_berat,  DROP COLUMN f1_berat,
  DROP COLUMN precision_sedang, DROP COLUMN recall_sedang, DROP COLUMN f1_sedang,
  DROP COLUMN precision_ringan, DROP COLUMN recall_ringan, DROP COLUMN f1_ringan,
  ADD COLUMN per_class TEXT NOT NULL AFTER confusion_matrix;
