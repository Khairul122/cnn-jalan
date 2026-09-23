ALTER TABLE preprocessing_config
  MODIFY COLUMN denoise_method ENUM('none', 'gaussian', 'median', 'bilateral') NOT NULL DEFAULT 'bilateral';
