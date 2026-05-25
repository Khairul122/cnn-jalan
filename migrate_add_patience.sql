ALTER TABLE arsitektur_config
  ADD COLUMN patience SMALLINT NOT NULL DEFAULT 5
  AFTER epochs;
