"""rewrite labeling schema for visual k-means

Revision ID: 20260926_labeling_visual_kmeans
Revises:
"""
from alembic import op
import sqlalchemy as sa


revision = '20260926_labeling_visual_kmeans'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'labeling_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
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
    )
    op.create_table(
        'hasil_labeling',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('config_id', sa.Integer(), nullable=False),
        sa.Column('jumlah_lokasi', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('jumlah_dilewati', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('variansi_pca', sa.Numeric(5, 4), nullable=True),
        sa.Column('distribusi_kelas', sa.Text(), nullable=True),
        sa.Column('status', sa.Enum('selesai', 'gagal', name='hasil_labeling_status'), nullable=False, server_default='selesai'),
        sa.Column('catatan', sa.Text(), nullable=True),
        sa.Column('is_diterapkan', sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column('diterapkan_at', sa.DateTime(), nullable=True),
        sa.Column('pengguna_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['config_id'], ['labeling_config.id']),
        sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id']),
    )
    op.create_table(
        'hasil_labeling_item',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('run_id', sa.Integer(), nullable=False),
        sa.Column('lokasi_id', sa.Integer(), nullable=False),
        sa.Column('klaster', sa.Integer(), nullable=False),
        sa.Column('kepadatan_tepi', sa.Numeric(6, 4), nullable=False),
        sa.Column('jarak_centroid', sa.Numeric(10, 4), nullable=True),
        sa.Column('tingkat_kerusakan_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['run_id'], ['hasil_labeling.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['lokasi_id'], ['lokasi_kerusakan.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tingkat_kerusakan_id'], ['tingkat_kerusakan.id']),
    )

    with op.batch_alter_table('label_kerusakan') as batch:
        batch.add_column(sa.Column('metode', sa.Enum('klasterisasi', 'manual', name='label_metode'), nullable=True))
        batch.add_column(sa.Column('cluster_id', sa.Integer(), nullable=True))
        batch.add_column(sa.Column('kepadatan_tepi', sa.Numeric(6, 4), nullable=True))
        batch.add_column(sa.Column('jarak_centroid', sa.Numeric(10, 4), nullable=True))
        batch.add_column(sa.Column('hasil_labeling_id', sa.Integer(), nullable=True))
        batch.create_foreign_key('fk_label_hasil_labeling', 'hasil_labeling', ['hasil_labeling_id'], ['id'], ondelete='SET NULL')
        batch.drop_column('persen_retak')
        batch.drop_column('jenis_retak')
        batch.drop_column('jumlah_lubang')
        batch.drop_column('kedalaman_rutting')
        batch.drop_column('sdi_score')


def downgrade():
    with op.batch_alter_table('label_kerusakan') as batch:
        batch.drop_constraint('fk_label_hasil_labeling', type_='foreignkey')
        batch.drop_column('hasil_labeling_id')
        batch.drop_column('jarak_centroid')
        batch.drop_column('kepadatan_tepi')
        batch.drop_column('cluster_id')
        batch.drop_column('metode')
        batch.add_column(sa.Column('persen_retak', sa.Numeric(5, 2), nullable=False, server_default='0'))
        batch.add_column(sa.Column('jenis_retak', sa.Enum('halus', 'lebar', name='jenis_retak'), nullable=False, server_default='halus'))
        batch.add_column(sa.Column('jumlah_lubang', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('kedalaman_rutting', sa.Numeric(5, 2), nullable=False, server_default='0'))
        batch.add_column(sa.Column('sdi_score', sa.Numeric(6, 2), nullable=False, server_default='0'))

    op.drop_table('hasil_labeling_item')
    op.drop_table('hasil_labeling')
    op.drop_table('labeling_config')
