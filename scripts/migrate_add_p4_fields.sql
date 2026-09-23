ALTER TABLE arsitektur_config
  ADD COLUMN label_smoothing FLOAT NOT NULL DEFAULT 0 AFTER mixup_alpha,
  ADD COLUMN dense_units INT NOT NULL DEFAULT 64 AFTER label_smoothing,
  ADD COLUMN dense_l2 FLOAT NOT NULL DEFAULT 0.0001 AFTER dense_units,
  ADD COLUMN skip_fine_tuning TINYINT(1) NOT NULL DEFAULT 0 AFTER dense_l2;
