-- Revisi data lokasi: P/L jadi numerik (meter) + kolom keterangan dari Excel (Ket).
-- Jalankan setelah tabel lokasi_kerusakan dikosongkan (scripts/seed_data.py --reset),
-- karena nilai lama bertipe teks ('1,5 M', '70 CM') tidak bisa dikonversi otomatis.
ALTER TABLE lokasi_kerusakan
  MODIFY COLUMN panjang DECIMAL(8,2) NULL,
  MODIFY COLUMN lebar   DECIMAL(8,2) NULL,
  ADD COLUMN keterangan VARCHAR(50) NULL AFTER lebar;
