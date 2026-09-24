-- ============================================================
--  MIGRATION: Tambah Fitur Preprocessing
--  Jalankan: mysql -u root -p db_cnn_jalan < migrate_add_preprocessing.sql
--  Atau copy-paste ke phpMyAdmin SQL tab
-- ============================================================

USE db_cnn_jalan;

-- ------------------------------------------------------------
-- Tabel konfigurasi pipeline preprocessing
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS preprocessing_config (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    nama_config     VARCHAR(100) NOT NULL,
    -- Resize
    target_width    INT NOT NULL DEFAULT 224,
    target_height   INT NOT NULL DEFAULT 224,
    resize_method   ENUM('LANCZOS','BILINEAR','BICUBIC','NEAREST') NOT NULL DEFAULT 'LANCZOS',
    -- Normalisasi
    norm_method     ENUM('minmax','zscore','none') NOT NULL DEFAULT 'minmax',
    -- Augmentasi
    aug_flip_h      TINYINT(1) NOT NULL DEFAULT 0,
    aug_flip_v      TINYINT(1) NOT NULL DEFAULT 0,
    aug_rotate_deg  DECIMAL(5,2) NOT NULL DEFAULT 0.00,
    aug_brightness  DECIMAL(4,2) NOT NULL DEFAULT 1.00,
    aug_contrast    DECIMAL(4,2) NOT NULL DEFAULT 1.00,
    -- Denoise
    denoise_method  ENUM('none','gaussian','median','bilateral') NOT NULL DEFAULT 'none',
    denoise_ksize   INT NOT NULL DEFAULT 3,
    -- Meta
    is_default      TINYINT(1) NOT NULL DEFAULT 0,
    pengguna_id     INT NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pengguna_id) REFERENCES pengguna(id)
);

-- Insert satu konfigurasi default
INSERT INTO preprocessing_config
    (nama_config, target_width, target_height, resize_method, norm_method,
     aug_flip_h, aug_rotate_deg, aug_brightness, aug_contrast,
     denoise_method, denoise_ksize, is_default, pengguna_id)
VALUES
    ('Default CNN 224x224', 224, 224, 'LANCZOS', 'minmax',
     1, 15.00, 1.00, 1.00,
     'gaussian', 3, 1, 1);

-- ------------------------------------------------------------
-- Tabel hasil preprocessing per gambar
-- ------------------------------------------------------------
CREATE TABLE IF NOT EXISTS hasil_preprocessing (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    dokumentasi_id  INT NOT NULL,
    config_id       INT NOT NULL,
    path_output     VARCHAR(500) NOT NULL,
    ukuran_kb_asal  INT DEFAULT NULL,
    ukuran_kb_hasil INT DEFAULT NULL,
    durasi_ms       INT DEFAULT NULL,
    status          ENUM('selesai','gagal') NOT NULL DEFAULT 'selesai',
    catatan         TEXT DEFAULT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dokumentasi_id) REFERENCES dokumentasi_foto(id) ON DELETE CASCADE,
    FOREIGN KEY (config_id) REFERENCES preprocessing_config(id)
);
