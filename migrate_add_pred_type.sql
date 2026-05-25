ALTER TABLE arsitektur_config
  ADD COLUMN pred_type VARCHAR(10) NOT NULL DEFAULT 'none'
  AFTER model_path;
