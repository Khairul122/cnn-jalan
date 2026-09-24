ALTER TABLE preprocessing_config
  ADD COLUMN illum_correction TINYINT(1) NOT NULL DEFAULT 0
  AFTER resize_mode;
