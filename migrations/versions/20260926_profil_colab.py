"""Profil training Colab: kolom arsitektur_config.profil dan denoise 'nlmeans'."""
from alembic import op
import sqlalchemy as sa

revision = '20260926_profil_colab'
down_revision = '20260926_labeling_visual_kmeans'
branch_labels = None
depends_on = None

DENOISE_LAMA = ('none', 'gaussian', 'median', 'bilateral')
DENOISE_BARU = DENOISE_LAMA + ('nlmeans',)


def upgrade():
    op.add_column('arsitektur_config', sa.Column(
        'profil', sa.Enum('standar', 'colab', name='arsitektur_profil'),
        nullable=False, server_default='standar'))
    op.alter_column('preprocessing_config', 'denoise_method',
                    existing_type=sa.Enum(*DENOISE_LAMA), type_=sa.Enum(*DENOISE_BARU),
                    existing_nullable=False, existing_server_default='bilateral')


def downgrade():
    op.execute("UPDATE preprocessing_config SET denoise_method='bilateral' WHERE denoise_method='nlmeans'")
    op.alter_column('preprocessing_config', 'denoise_method',
                    existing_type=sa.Enum(*DENOISE_BARU), type_=sa.Enum(*DENOISE_LAMA),
                    existing_nullable=False, existing_server_default='bilateral')
    op.drop_column('arsitektur_config', 'profil')
