-- ============================================================
--  MIGRATION: Tambah Fitur Arsitektur CNN
-- ============================================================
USE db_cnn_jalan;

CREATE TABLE IF NOT EXISTS arsitektur_config (
    id               INT PRIMARY KEY AUTO_INCREMENT,
    nama             VARCHAR(100) NOT NULL,
    model_type       ENUM('mobilenetv2','efficientnetb0') NOT NULL DEFAULT 'mobilenetv2',
    input_size       INT NOT NULL DEFAULT 224,
    learning_rate    FLOAT NOT NULL DEFAULT 0.0001,
    batch_size       INT NOT NULL DEFAULT 16,
    epochs           INT NOT NULL DEFAULT 30,
    dropout_rate     FLOAT NOT NULL DEFAULT 0.3,
    optimizer        ENUM('adam','sgd','rmsprop') NOT NULL DEFAULT 'adam',
    split_config_id  INT NOT NULL,
    fold_val         SMALLINT NOT NULL DEFAULT 0,
    status           ENUM('draft','training','selesai','gagal') NOT NULL DEFAULT 'draft',
    model_path       VARCHAR(500) NULL,
    pengguna_id      INT NOT NULL,
    created_at       TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (split_config_id) REFERENCES split_config(id),
    FOREIGN KEY (pengguna_id)     REFERENCES pengguna(id)
);

CREATE TABLE IF NOT EXISTS hasil_training (
    id             INT PRIMARY KEY AUTO_INCREMENT,
    arsitektur_id  INT NOT NULL,
    epoch          INT NOT NULL,
    loss           FLOAT NOT NULL,
    accuracy       FLOAT NOT NULL,
    val_loss       FLOAT NOT NULL,
    val_accuracy   FLOAT NOT NULL,
    FOREIGN KEY (arsitektur_id) REFERENCES arsitektur_config(id) ON DELETE CASCADE
);

CREATE INDEX idx_ht_arsitektur ON hasil_training(arsitektur_id);
