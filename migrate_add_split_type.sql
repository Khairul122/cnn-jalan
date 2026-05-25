-- Tambah kolom split_type ke split_config (kfold | holdout)
ALTER TABLE split_config
  ADD COLUMN split_type VARCHAR(10) NOT NULL DEFAULT 'kfold'
  AFTER nama;
