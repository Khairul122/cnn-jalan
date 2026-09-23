ALTER TABLE preprocessing_config
  ADD COLUMN resize_mode ENUM('stretch', 'letterbox') NOT NULL DEFAULT 'stretch'
  AFTER resize_method;
