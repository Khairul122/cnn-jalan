-- Model final: dilatih pada seluruh data setelah K-Fold CV (dipakai untuk klasifikasi foto baru).
ALTER TABLE arsitektur_config
  ADD COLUMN final_model_path VARCHAR(500) NULL
  AFTER model_path;
