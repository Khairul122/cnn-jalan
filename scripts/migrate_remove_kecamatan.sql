-- ============================================================
--  MIGRASI: Hapus kolom kecamatan_id dari lokasi_kerusakan
--           dan drop tabel kecamatan
--
--  Cara pakai:
--    mysql -u root -p db_cnn_jalan < migrate_remove_kecamatan.sql
-- ============================================================

USE db_cnn_jalan;

SET FOREIGN_KEY_CHECKS = 0;

ALTER TABLE lokasi_kerusakan DROP COLUMN kecamatan_id;

DROP TABLE IF EXISTS kecamatan;

SET FOREIGN_KEY_CHECKS = 1;

SELECT 'Migrasi selesai: kecamatan_id dihapus dari lokasi_kerusakan, tabel kecamatan dihapus.' AS status;
