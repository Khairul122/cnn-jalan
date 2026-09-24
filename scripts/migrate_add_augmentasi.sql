-- Tahap Augmentasi terpisah (sebelum split): konfigurasi dan hasil salinan. Salinan mewarisi kelas/fold foto asal (dokumentasi_id).
CREATE TABLE IF NOT EXISTS augmentasi_config (
  id INT NOT NULL AUTO_INCREMENT,
  nama_config VARCHAR(100) NOT NULL,
  n_salinan INT NOT NULL DEFAULT 3,
  seed INT NOT NULL DEFAULT 42,
  parameter TEXT NOT NULL,
  is_default TINYINT(1) NOT NULL DEFAULT 0,
  pengguna_id INT NOT NULL,
  created_at DATETIME NULL,
  PRIMARY KEY (id),
  CONSTRAINT fk_augcfg_pengguna FOREIGN KEY (pengguna_id) REFERENCES pengguna (id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

CREATE TABLE IF NOT EXISTS hasil_augmentasi (
  id INT NOT NULL AUTO_INCREMENT,
  dokumentasi_id INT NOT NULL,
  config_id INT NOT NULL,
  salinan_ke INT NOT NULL,
  path_output VARCHAR(500) NOT NULL,
  status ENUM('selesai','gagal') NOT NULL DEFAULT 'selesai',
  catatan TEXT NULL,
  created_at DATETIME NULL,
  PRIMARY KEY (id),
  KEY idx_hasilaug_dok (dokumentasi_id),
  KEY idx_hasilaug_cfg (config_id),
  CONSTRAINT fk_hasilaug_dok FOREIGN KEY (dokumentasi_id) REFERENCES dokumentasi_foto (id) ON DELETE CASCADE,
  CONSTRAINT fk_hasilaug_cfg FOREIGN KEY (config_id) REFERENCES augmentasi_config (id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
