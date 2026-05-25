-- ============================================================
--  DATABASE: GIS Pemetaan Kerusakan Jalan Kota Lhokseumawe
--  Metode   : Convolutional Neural Network (CNN)
--  Penulis  : Imay Syafitri (NIM 210170072)
--  Versi    : 2.0
-- ============================================================

CREATE DATABASE IF NOT EXISTS db_cnn_jalan
  CHARACTER SET utf8mb4
  COLLATE utf8mb4_unicode_ci;

USE db_cnn_jalan;

-- ------------------------------------------------------------
-- 1. jenis_kerusakan
-- ------------------------------------------------------------
CREATE TABLE jenis_kerusakan (
    id           INT PRIMARY KEY AUTO_INCREMENT,
    nama_jenis   VARCHAR(50)  NOT NULL,
    kode         VARCHAR(10)  NOT NULL UNIQUE,
    deskripsi    TEXT
);

INSERT INTO jenis_kerusakan (nama_jenis, kode, deskripsi) VALUES
    ('Retakan',   'CRACK',   'Retak halus, memanjang, melintang, atau retak buaya pada permukaan jalan'),
    ('Berlubang', 'POTHOLE', 'Kerusakan struktural membentuk cekungan akibat pengelupasan lapisan aspal'),
    ('Gelombang', 'RUTTING', 'Deformasi permukaan jalan yang tidak rata akibat pergeseran material');

-- ------------------------------------------------------------
-- 3. tingkat_kerusakan
-- ------------------------------------------------------------
CREATE TABLE tingkat_kerusakan (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    nama_tingkat    VARCHAR(20)  NOT NULL,
    warna_peta      VARCHAR(7)   NOT NULL,
    skor_prioritas  INT          NOT NULL
);

INSERT INTO tingkat_kerusakan (nama_tingkat, warna_peta, skor_prioritas) VALUES
    ('Berat',   '#E53E3E', 1),
    ('Sedang',  '#F6AD55', 2),
    ('Ringan',  '#68D391', 3);

-- ------------------------------------------------------------
-- 4. pengguna
-- ------------------------------------------------------------
CREATE TABLE pengguna (
    id             INT PRIMARY KEY AUTO_INCREMENT,
    nama           VARCHAR(100) NOT NULL,
    email          VARCHAR(150) NOT NULL UNIQUE,
    password_hash  VARCHAR(255) NOT NULL,
    role           ENUM('admin', 'viewer') NOT NULL DEFAULT 'viewer',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 5. lokasi_kerusakan
-- ------------------------------------------------------------
CREATE TABLE lokasi_kerusakan (
    id              INT PRIMARY KEY AUTO_INCREMENT,
    nama_citra      VARCHAR(50)   NOT NULL,
    latitude        DECIMAL(10,7) NOT NULL,
    longitude       DECIMAL(10,7) NOT NULL,
    panjang         VARCHAR(20)   DEFAULT NULL,
    lebar           VARCHAR(20)   DEFAULT NULL,
    sumber_data     ENUM('primer', 'sekunder') NOT NULL DEFAULT 'primer',
    pengguna_id     INT           NOT NULL,
    created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (pengguna_id)  REFERENCES pengguna(id)
);

-- ------------------------------------------------------------
-- 6. dokumentasi_foto
-- ------------------------------------------------------------
CREATE TABLE dokumentasi_foto (
    id           INT PRIMARY KEY AUTO_INCREMENT,
    lokasi_id    INT          NOT NULL,
    nama_file    VARCHAR(255) NOT NULL,
    path_file    VARCHAR(500) NOT NULL,
    ukuran_kb    INT          DEFAULT NULL,
    created_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (lokasi_id) REFERENCES lokasi_kerusakan(id) ON DELETE CASCADE
);

-- ------------------------------------------------------------
-- 7. hasil_klasifikasi_cnn
-- ------------------------------------------------------------
CREATE TABLE hasil_klasifikasi_cnn (
    id                    INT PRIMARY KEY AUTO_INCREMENT,
    dokumentasi_id        INT           NOT NULL UNIQUE,
    jenis_kerusakan_id    INT           NOT NULL,
    tingkat_kerusakan_id  INT           NOT NULL,
    confidence_score      FLOAT(5,4)    NOT NULL,
    is_valid              TINYINT(1)    NOT NULL DEFAULT 1,
    catatan               TEXT          DEFAULT NULL,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (dokumentasi_id)       REFERENCES dokumentasi_foto(id) ON DELETE CASCADE,
    FOREIGN KEY (jenis_kerusakan_id)   REFERENCES jenis_kerusakan(id),
    FOREIGN KEY (tingkat_kerusakan_id) REFERENCES tingkat_kerusakan(id)
);

-- ------------------------------------------------------------
-- 8. peta_kerusakan
-- ------------------------------------------------------------
CREATE TABLE peta_kerusakan (
    id                    INT PRIMARY KEY AUTO_INCREMENT,
    lokasi_id             INT  NOT NULL UNIQUE,
    hasil_klasifikasi_id  INT  NOT NULL,
    status_pemetaan       ENUM('draft', 'terverifikasi', 'diperbaiki') NOT NULL DEFAULT 'draft',
    prioritas_perbaikan   INT  NOT NULL,
    tanggal_pemetaan      DATE NOT NULL,
    pengguna_id           INT  NOT NULL,
    FOREIGN KEY (lokasi_id)            REFERENCES lokasi_kerusakan(id),
    FOREIGN KEY (hasil_klasifikasi_id) REFERENCES hasil_klasifikasi_cnn(id),
    FOREIGN KEY (pengguna_id)          REFERENCES pengguna(id)
);

-- ------------------------------------------------------------
-- 9. evaluasi_model
-- ------------------------------------------------------------
CREATE TABLE evaluasi_model (
    id                  INT PRIMARY KEY AUTO_INCREMENT,
    nama_model          VARCHAR(100) NOT NULL,
    versi               VARCHAR(20)  NOT NULL,
    total_data_uji      INT          NOT NULL,
    akurasi             FLOAT(6,4)   NOT NULL,
    presisi             FLOAT(6,4)   NOT NULL,
    recall              FLOAT(6,4)   NOT NULL,
    f1_score            FLOAT(6,4)   NOT NULL,
    cross_entropy_loss  FLOAT(8,6)   NOT NULL,
    tp                  INT          NOT NULL,
    fp                  INT          NOT NULL,
    tn                  INT          NOT NULL,
    fn                  INT          NOT NULL,
    catatan             TEXT         DEFAULT NULL,
    created_at          TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- ------------------------------------------------------------
-- 9. label_kerusakan  (SDI — Surface Distress Index)
-- ------------------------------------------------------------
CREATE TABLE label_kerusakan (
    id                    INT PRIMARY KEY AUTO_INCREMENT,
    lokasi_id             INT           NOT NULL UNIQUE,
    persen_retak          DECIMAL(5,2)  NOT NULL DEFAULT 0,
    jenis_retak           ENUM('halus','lebar') NOT NULL DEFAULT 'halus',
    jumlah_lubang         INT           NOT NULL DEFAULT 0,
    kedalaman_rutting     DECIMAL(5,2)  NOT NULL DEFAULT 0,
    sdi_score             DECIMAL(6,2)  NOT NULL DEFAULT 0,
    tingkat_kerusakan_id  INT           NOT NULL,
    catatan               TEXT,
    pengguna_id           INT           NOT NULL,
    created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    FOREIGN KEY (lokasi_id)            REFERENCES lokasi_kerusakan(id) ON DELETE CASCADE,
    FOREIGN KEY (tingkat_kerusakan_id) REFERENCES tingkat_kerusakan(id),
    FOREIGN KEY (pengguna_id)          REFERENCES pengguna(id)
);

-- ============================================================
--  INDEKS
-- ============================================================
CREATE INDEX idx_lokasi_koordinat  ON lokasi_kerusakan(latitude, longitude);
CREATE INDEX idx_lokasi_sumber     ON lokasi_kerusakan(sumber_data);
CREATE INDEX idx_peta_status       ON peta_kerusakan(status_pemetaan);
CREATE INDEX idx_peta_prioritas    ON peta_kerusakan(prioritas_perbaikan);
CREATE INDEX idx_cnn_valid         ON hasil_klasifikasi_cnn(is_valid);
CREATE INDEX idx_cnn_jenis         ON hasil_klasifikasi_cnn(jenis_kerusakan_id);
