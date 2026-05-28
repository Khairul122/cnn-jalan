-- Tambah kolom step_name ke hasil_preprocessing
-- Menyimpan tahap pipeline mana yang menghasilkan gambar ini
-- Nilai: resize | crop | normalisasi | augmentasi | denoise

ALTER TABLE hasil_preprocessing
  ADD COLUMN step_name VARCHAR(20) NOT NULL DEFAULT 'denoise'
  AFTER config_id;

-- Record lama (sebelum fitur ini) dianggap output tahap akhir (denoise)
-- Tidak perlu update manual karena DEFAULT 'denoise' sudah menanganinya
