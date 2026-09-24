ALTER TABLE preprocessing_config
  MODIFY COLUMN norm_method ENUM('minmax', 'zscore', 'none', 'clahe') NOT NULL DEFAULT 'minmax';
