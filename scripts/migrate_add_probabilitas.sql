-- Probabilitas per kelas (JSON) di prediksi_model, untuk cross-entropy CV. NULL = prediksi lama.
ALTER TABLE prediksi_model ADD COLUMN probabilitas TEXT NULL AFTER confidence;
