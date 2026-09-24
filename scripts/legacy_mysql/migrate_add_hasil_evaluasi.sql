-- Migration: tambah tabel hasil_evaluasi
-- Evaluasi otomatis dari model terlatih terhadap data validasi fold

CREATE TABLE IF NOT EXISTS hasil_evaluasi (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    arsitektur_id    INT NOT NULL,
    total_data_val   INT NOT NULL,
    akurasi          FLOAT NOT NULL,
    confusion_matrix TEXT NOT NULL,
    precision_berat  FLOAT NOT NULL,
    recall_berat     FLOAT NOT NULL,
    f1_berat         FLOAT NOT NULL,
    precision_sedang FLOAT NOT NULL,
    recall_sedang    FLOAT NOT NULL,
    f1_sedang        FLOAT NOT NULL,
    precision_ringan FLOAT NOT NULL,
    recall_ringan    FLOAT NOT NULL,
    f1_ringan        FLOAT NOT NULL,
    macro_precision  FLOAT NOT NULL,
    macro_recall     FLOAT NOT NULL,
    macro_f1         FLOAT NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (arsitektur_id) REFERENCES arsitektur_config(id) ON DELETE CASCADE
);
