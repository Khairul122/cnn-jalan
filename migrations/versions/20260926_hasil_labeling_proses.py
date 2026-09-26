"""Tambah status 'proses' pada hasil_labeling.

Run klasterisasi sekarang berjalan di thread background, jadi barisnya dibuat
lebih dulu dengan status 'proses' dan baru diubah ke 'selesai'/'gagal' saat
thread selesai. Tanpa nilai enum ini MySQL memotong nilainya jadi '' dan
INSERT ditolak.
"""
from alembic import op
import sqlalchemy as sa

revision = '20260926_hasil_labeling_proses'
down_revision = '20260926_resize_lanczos_cv'
branch_labels = None
depends_on = None

ENUM_LAMA = sa.Enum('selesai', 'gagal', name='hasil_labeling_status')
ENUM_BARU = sa.Enum('proses', 'selesai', 'gagal', name='hasil_labeling_status')


def upgrade():
    op.alter_column('hasil_labeling', 'status',
                    existing_type=ENUM_LAMA, existing_nullable=False,
                    existing_server_default='selesai',
                    type_=ENUM_BARU, server_default='selesai')


def downgrade():
    # Baris berstatus 'proses' akan kehilangan statusnya saat enum menyempit.
    op.execute("UPDATE hasil_labeling SET status = 'gagal' WHERE status = 'proses'")
    op.alter_column('hasil_labeling', 'status',
                    existing_type=ENUM_BARU, existing_nullable=False,
                    existing_server_default='selesai',
                    type_=ENUM_LAMA, server_default='selesai')
