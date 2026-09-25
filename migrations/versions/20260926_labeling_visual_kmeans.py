"""Ganti label SDI (formula P x L) dengan label K-Means atas fitur visual.

MySQL yang schema-nya sudah dibuat di luar Alembic harus di-stamp dulu
(`flask db stamp 0001_baseline_mysql`) sebelum upgrade, atau Alembic akan
mencoba membuat ulang tabel yang sudah ada. Kolom SDI dihapus tanpa backup:
nilainya memang tidak valid metodologis dan `lokasi_id` sudah ada sejak
sebelum rewrite, jadi tidak ada data yang hilang tak sengaja.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260926_labeling_visual_kmeans'
down_revision = '0001_baseline_mysql'
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
        # server_default menjaga baris label lama agar tidak melanggar NOT NULL.
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

    # server_default hanya alat bantu backfill. Membiarkannya membuat DB mengisi
    # 'manual' sementara model menyatakan default 'klasterisasi'.
    # SQLite tidak mendukung `ALTER COLUMN ... DROP DEFAULT`, dan tidak perlu.
    if op.get_bind().dialect.name != 'sqlite':
        op.alter_column(
            'label_kerusakan', 'metode',
            existing_type=sa.Enum('klasterisasi', 'manual', name='label_metode'),
            existing_nullable=False,
            server_default=None,
        )


def downgrade():
    with op.batch_alter_table('label_kerusakan', schema=None) as batch:
        batch.drop_constraint(FK_LABEL_HASIL, type_='foreignkey')
        batch.drop_column('hasil_labeling_id')
        batch.drop_column('jarak_centroid')
        batch.drop_column('kepadatan_tepi')
        batch.drop_column('cluster_id')
        batch.add_column(sa.Column('persen_retak', sa.Numeric(precision=5, scale=2),
                                   nullable=False, server_default='0'))
        batch.add_column(sa.Column('jenis_retak', sa.Enum('halus', 'lebar'),
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
