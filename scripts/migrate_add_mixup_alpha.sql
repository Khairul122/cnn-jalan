ALTER TABLE arsitektur_config
  ADD COLUMN mixup_alpha FLOAT NOT NULL DEFAULT 0
  AFTER optimizer;
