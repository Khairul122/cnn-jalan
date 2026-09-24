-- TODO.md P1 (ditulis ulang 2026-09-24): satu config preprocessing aktif global (hasil_preprocessing hanya berisi
-- satu config), jadi arsitektur_config TIDAK menyimpan config-nya. Default config baru: resize 256 -> center crop 224,
-- tanpa normalisasi tambahan (preprocess_input di dalam model sudah menormalisasi), denoise bilateral k=3.
-- Baris pertama membatalkan kolom dari versi P1 sebelumnya (aman dijalankan bila kolomnya tidak ada: abaikan error).
ALTER TABLE arsitektur_config DROP FOREIGN KEY fk_arsitektur_prep_config;
ALTER TABLE arsitektur_config DROP COLUMN preprocessing_config_id;

ALTER TABLE preprocessing_config
  ALTER COLUMN target_width SET DEFAULT 256,
  ALTER COLUMN target_height SET DEFAULT 256,
  ALTER COLUMN crop_enabled SET DEFAULT 1,
  ALTER COLUMN resize_mode SET DEFAULT 'stretch',
  ALTER COLUMN norm_method SET DEFAULT 'none';
