"""rewrite labeling schema for visual k-means

Ganti label SDI (formula P x L) dengan label klasterisasi K-Means atas fitur visual.

Catatan penting soal migrasi ini:
- Tabel di bawah diasumsikan SUDAH ada (basis data aplikasi yang berjalan). Jadi
  `down_revision = None` di sini bukan "baseline dari nol", melainkan revisi pertama
  yang di-deploy ke atas schema lama. Jalankan `flask db upgrade` hanya setelah
  `flask db current` mengonfirmasi basis data sudah kosong dari tabel labeling.
- Kolom SDI dihapus tanpa dip-backup. Old labels memang tidak valid secara
  metodologis (lihat TODO.md bagian 1.1) dan `label_kerusakan.lokasi_id` sudah
  ada sejak sebelum rewrite, jadi tidak ada data yang hilang secara tidak sengaja.
- Baris label lama mendapat `metode='manual'`, bukan `'klasterisasi'`, karena
  nilainya berasal dari formula SDI. Menandainya `'klasterisasi'` akan berbohong
  soal asal-usulnya dan membingungkan saat audit.

Revision ID: 20260926_labeling_visual_kmeans
Revises:
Create Date: 2026-09-26
"""
from alembic import op
import sqlalchemy as sa

revision = '20260926_labeling_visual_kmeans'
down_revision = None
branch_labels = None
depends_on = None

FK_LABEL_HASIL = 'fk_label_kerusakan_hasil_labeling'


def upgrade():
    op.create_table(
        'labeling_config',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('nama_config', sa.String(length=100), nullable=False),
        sa.Column('n_cluster', sa.Integer(), nullable=False, server_default='4'),
        sa.Column('pca_komponen', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('random_state', sa.Integer(), nullable=False, server_default='42'),
        sa.Column('canny_low', sa.Integer(), nullable=False, server_default='50'),
        sa.Column('canny_high', sa.Integer(), nullable=False, server_default='150'),
        sa.Column('is_default', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('pengguna_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'hasil_labeling',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('config_id', sa.Integer(), nullable=False),
        sa.Column('jumlah_lokasi', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('jumlah_dilewati', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('variansi_pca', sa.Numeric(precision=5, scale=4), nullable=True),
        sa.Column('distribusi_kelas', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('selesai', 'gagal', name='hasil_labeling_status'),
                  nullable=False, server_default='selesai'),
        sa.Column('catatan', sa.Text(), nullable=True),
        sa.Column('is_diterapkan', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('diterapkan_at', sa.DateTime(), nullable=True),
        sa.Column('pengguna_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['config_id'], ['labeling_config.id']),
        sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_table(
        'hasil_labeling_item',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('lokasi_id', sa.Integer(), nullable=False),
        sa.Column('klaster', sa.Integer(), nullable=False),
        sa.Column('kepadatan_tepi', sa.Numeric(precision=6, scale=4), nullable=False),
        sa.Column('jarak_centroid', sa.Numeric(precision=10, scale=4), nullable=True),
        sa.Column('tingkat_kerusakan_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['lokasi_id'], ['lokasi_kerusakan.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['run_id'], ['hasil_labeling.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tingkat_kerusakan_id'], ['tingkat_kerusakan.id']),
        sa.PrimaryKeyConstraint('id'),
    )

    with op.batch_alter_table('label_kerusakan', schema=None) as batch:
        # server_default dipakai supaya baris label lama yang sudah ada tidak
        # melanggar NOT NULL saat kolom ditambahkan.
        batch.add_column(sa.Column(
            'metode', sa.Enum('klasterisasi', 'manual', name='label_metode'),
            nullable=False, server_default='manual',
        ))
        batch.add_column(sa.Column('cluster_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('kepadatan_tepi', sa.Numeric(precision=6, scale=4), nullable=True))
        batch.add_column(sa.Column('jarak_centroid', sa.Numeric(precision=10, scale=4), nullable=True))
        batch.add_column(sa.Column('hasil_labeling_id', sa.Integer(), nullable=True))
        batch.create_foreign_key(
            FK_LABEL_HASIL, 'hasil_labeling', ['hasil_labeling_id'], ['id'], ondelete='SET NULL'
        )
        batch.drop_column('persen_retak')
        batch.drop_column('jenis_retak')
        batch.drop_column('jumlah_lubang')
        batch.drop_column('kedalaman_rutting')
        batch.drop_column('sdi_score')

    # Label lama berasal dari formula SDI, bukan klasterisasi.
    op.execute("UPDATE label_kerusakan SET metode = 'manual' WHERE metode IS NULL")


def downgrade():
    with op.batch_alter_table('label_kerusakan', schema=None) as batch:
        batch.drop_constraint(FK_LABEL_HASIL, type_='foreignkey')
        batch.drop_column('hasil_labeling_id')
        batch.drop_column('jarak_centroid')
        batch.drop_column('kepadatan_tepi')
        batch.drop_column('cluster_id')
        batch.add_column(sa.Column('persen_retak', sa.Numeric(precision=5, scale=2),
                                   nullable=False, server_default='0'))
        batch.add_column(sa.Column('jenis_retak', sa.String(length=5),
                                   nullable=False, server_default='halus'))
        batch.add_column(sa.Column('jumlah_lubang', sa.Integer(),
                                   nullable=False, server_default='0'))
        batch.add_column(sa.Column('kedalaman_rutting', sa.Numeric(precision=5, scale=2),
                                   nullable=False, server_default='0'))
        batch.add_column(sa.Column('sdi_score', sa.Numeric(precision=6, scale=2),
                                   nullable=False, server_default='0'))
        batch.drop_column('metode')

    op.drop_table('hasil_labeling_item')
    op.drop_table('hasil_labeling')
    op.drop_table('labeling_config')
