-- ============================================================
--  MIGRATION: Tambah Fitur Split Data (Stratified K-Fold)
-- ============================================================
USE db_cnn_jalan;

CREATE TABLE IF NOT EXISTS split_config (
    id            INT PRIMARY KEY AUTO_INCREMENT,
    nama          VARCHAR(100) NOT NULL,
    n_splits      INT NOT NULL DEFAULT 5,
    random_state  INT NOT NULL DEFAULT 42,
    label_sumber  ENUM('tingkat','jenis') NOT NULL DEFAULT 'tingkat',
    total_data    INT NOT NULL DEFAULT 0,
    pengguna_id   INT NOT NULL,
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pengguna_id) REFERENCES pengguna(id)
);

CREATE TABLE IF NOT EXISTS split_item (
    id                   INT PRIMARY KEY AUTO_INCREMENT,
    config_id            INT NOT NULL,
    dokumentasi_id       INT NOT NULL,
    tingkat_kerusakan_id INT NOT NULL,
    fold_index           TINYINT NOT NULL,
    created_at           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (config_id)            REFERENCES split_config(id) ON DELETE CASCADE,
    FOREIGN KEY (dokumentasi_id)       REFERENCES dokumentasi_foto(id) ON DELETE CASCADE,
    FOREIGN KEY (tingkat_kerusakan_id) REFERENCES tingkat_kerusakan(id)
);

CREATE INDEX idx_split_config ON split_item(config_id);
CREATE INDEX idx_split_fold   ON split_item(config_id, fold_index);
