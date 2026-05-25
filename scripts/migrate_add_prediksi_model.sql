CREATE TABLE IF NOT EXISTS prediksi_model (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    arsitektur_id   INT NOT NULL,
    dokumentasi_id  INT NOT NULL,
    prediksi        TINYINT NOT NULL,
    aktual          TINYINT,
    confidence      FLOAT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (arsitektur_id) REFERENCES arsitektur_config(id) ON DELETE CASCADE,
    FOREIGN KEY (dokumentasi_id) REFERENCES dokumentasi_foto(id) ON DELETE CASCADE,
    UNIQUE KEY uk_arsitektur_dok (arsitektur_id, dokumentasi_id)
);
