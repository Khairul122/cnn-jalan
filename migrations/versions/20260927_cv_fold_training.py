"""CV K-Fold training: tambahkan kolom fold_index pada hasil_training."""
from alembic import op
import sqlalchemy as sa

revision = '20260927_cv_fold_training'
down_revision = '20260926_hasil_labeling_proses'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('hasil_training', sa.Column(
        'fold_index', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('hasil_training', 'fold_index')
