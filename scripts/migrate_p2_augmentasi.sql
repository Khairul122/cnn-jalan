-- TODO.md P2: (1) tahap Augmentasi dihapus dari preprocessing (hanya pratinjau, tidak dipakai training);
-- (2) augmentasi training bisa dimatikan per layer untuk ablation (arsitektur_config.aug_off).
-- File hasil 'augmentasi' dihapus terpisah oleh skrip Python yang menjalankan migrasi ini.
DELETE FROM hasil_preprocessing WHERE step_name = 'augmentasi';

ALTER TABLE preprocessing_config
  DROP COLUMN aug_flip_h, DROP COLUMN aug_flip_v, DROP COLUMN aug_rotate_deg,
  DROP COLUMN aug_brightness, DROP COLUMN aug_contrast;

ALTER TABLE arsitektur_config
  ADD COLUMN aug_off VARCHAR(100) NOT NULL DEFAULT '' AFTER skip_fine_tuning;
