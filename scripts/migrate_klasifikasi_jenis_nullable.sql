-- Model CNN saat ini hanya memprediksi tingkat kerusakan (Berat/Sedang/Ringan), bukan jenis.
-- Jenis kerusakan dibiarkan kosong daripada diisi acak.
ALTER TABLE hasil_klasifikasi_cnn
  MODIFY COLUMN jenis_kerusakan_id INT NULL;
