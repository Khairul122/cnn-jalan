"""preprocessing_config.resize_method: tambah 'LANCZOS_CV' (cv2.INTER_LANCZOS4, dipakai notebook Colab)."""
from alembic import op
import sqlalchemy as sa

revision = '20260926_resize_lanczos_cv'
down_revision = '20260926_profil_colab'
branch_labels = None
depends_on = None

LAMA = ('LANCZOS', 'BILINEAR', 'BICUBIC', 'NEAREST')
BARU = LAMA + ('LANCZOS_CV',)


def upgrade():
    op.alter_column('preprocessing_config', 'resize_method', existing_type=sa.Enum(*LAMA),
                    type_=sa.Enum(*BARU), existing_nullable=False, existing_server_default='LANCZOS')


def downgrade():
    op.execute("UPDATE preprocessing_config SET resize_method='LANCZOS' WHERE resize_method='LANCZOS_CV'")
    op.alter_column('preprocessing_config', 'resize_method', existing_type=sa.Enum(*BARU),
                    type_=sa.Enum(*LAMA), existing_nullable=False, existing_server_default='LANCZOS')
