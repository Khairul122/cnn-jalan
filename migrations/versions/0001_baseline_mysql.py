"""Revisi pertama Alembic: 19 tabel dasar dalam bentuk PRA-labeling.

`label_kerusakan` di sini masih memakai kolom SDI, supaya revisi berikutnya
tetap jalan di MySQL baru maupun di MySQL lama yang schema-nya dibuat di luar
Alembic. Alembic repo ini sebelumnya hanya punya baseline Supabase yang sudah
dibatalkan, sehingga MySQL belum pernah punya revisi dasar.
"""
from alembic import op
import sqlalchemy as sa


revision = '0001_baseline_mysql'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    op.create_table('evaluasi_model',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nama_model', sa.String(length=100), nullable=False),
    sa.Column('versi', sa.String(length=20), nullable=False),
    sa.Column('total_data_uji', sa.Integer(), nullable=False),
    sa.Column('akurasi', sa.Float(), nullable=False),
    sa.Column('presisi', sa.Float(), nullable=False),
    sa.Column('recall', sa.Float(), nullable=False),
    sa.Column('f1_score', sa.Float(), nullable=False),
    sa.Column('cross_entropy_loss', sa.Float(), nullable=False),
    sa.Column('tp', sa.Integer(), nullable=False),
    sa.Column('fp', sa.Integer(), nullable=False),
    sa.Column('tn', sa.Integer(), nullable=False),
    sa.Column('fn', sa.Integer(), nullable=False),
    sa.Column('catatan', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('jenis_kerusakan',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nama_jenis', sa.String(length=50), nullable=False),
    sa.Column('kode', sa.String(length=10), nullable=False),
    sa.Column('deskripsi', sa.Text(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('kode')
    )
    op.create_table('pengguna',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nama', sa.String(length=100), nullable=False),
    sa.Column('email', sa.String(length=150), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('role', sa.Enum('admin', 'viewer'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('email')
    )
    op.create_table('tingkat_kerusakan',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nama_tingkat', sa.String(length=20), nullable=False),
    sa.Column('warna_peta', sa.String(length=7), nullable=False),
    sa.Column('skor_prioritas', sa.Integer(), nullable=False),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('augmentasi_config',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nama_config', sa.String(length=100), nullable=False),
    sa.Column('n_salinan', sa.Integer(), nullable=False),
    sa.Column('seed', sa.Integer(), nullable=False),
    sa.Column('parameter', sa.Text(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('pengguna_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('lokasi_kerusakan',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nama_citra', sa.String(length=50), nullable=False),
    sa.Column('latitude', sa.Numeric(precision=10, scale=7), nullable=False),
    sa.Column('longitude', sa.Numeric(precision=10, scale=7), nullable=False),
    sa.Column('panjang', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('lebar', sa.Numeric(precision=8, scale=2), nullable=True),
    sa.Column('keterangan', sa.String(length=50), nullable=True),
    sa.Column('sumber_data', sa.Enum('primer', 'sekunder'), nullable=False),
    sa.Column('pengguna_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('preprocessing_config',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nama_config', sa.String(length=100), nullable=False),
    sa.Column('target_width', sa.Integer(), nullable=False),
    sa.Column('target_height', sa.Integer(), nullable=False),
    sa.Column('resize_method', sa.Enum('LANCZOS', 'BILINEAR', 'BICUBIC', 'NEAREST'), nullable=False),
    sa.Column('resize_mode', sa.Enum('stretch', 'letterbox'), nullable=False),
    sa.Column('illum_correction', sa.Boolean(), nullable=False),
    sa.Column('crop_enabled', sa.Boolean(), nullable=False),
    sa.Column('crop_width', sa.Integer(), nullable=False),
    sa.Column('crop_height', sa.Integer(), nullable=False),
    sa.Column('norm_method', sa.Enum('minmax', 'zscore', 'none', 'clahe'), nullable=False),
    sa.Column('denoise_method', sa.Enum('none', 'gaussian', 'median', 'bilateral'), nullable=False),
    sa.Column('denoise_ksize', sa.Integer(), nullable=False),
    sa.Column('is_default', sa.Boolean(), nullable=False),
    sa.Column('pengguna_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('split_config',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nama', sa.String(length=100), nullable=False),
    sa.Column('n_splits', sa.Integer(), nullable=False),
    sa.Column('random_state', sa.Integer(), nullable=False),
    sa.Column('radius_grup_m', sa.Integer(), nullable=False),
    sa.Column('label_sumber', sa.Enum('tingkat', 'jenis'), nullable=False),
    sa.Column('total_data', sa.Integer(), nullable=False),
    sa.Column('pengguna_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('arsitektur_config',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('nama', sa.String(length=100), nullable=False),
    sa.Column('model_type', sa.Enum('mobilenetv2', 'efficientnetb0'), nullable=False),
    sa.Column('input_size', sa.Integer(), nullable=False),
    sa.Column('learning_rate', sa.Float(), nullable=False),
    sa.Column('batch_size', sa.Integer(), nullable=False),
    sa.Column('epochs', sa.Integer(), nullable=False),
    sa.Column('patience', sa.SmallInteger(), nullable=False),
    sa.Column('dropout_rate', sa.Float(), nullable=False),
    sa.Column('optimizer', sa.Enum('adam', 'sgd', 'rmsprop'), nullable=False),
    sa.Column('mixup_alpha', sa.Float(), nullable=False),
    sa.Column('label_smoothing', sa.Float(), nullable=False),
    sa.Column('dense_units', sa.Integer(), nullable=False),
    sa.Column('dense_l2', sa.Float(), nullable=False),
    sa.Column('skip_fine_tuning', sa.Boolean(), nullable=False),
    sa.Column('aug_off', sa.String(length=100), nullable=False),
    sa.Column('split_config_id', sa.Integer(), nullable=False),
    sa.Column('fold_val', sa.SmallInteger(), nullable=False),
    sa.Column('status', sa.Enum('draft', 'training', 'selesai', 'gagal'), nullable=False),
    sa.Column('model_path', sa.String(length=500), nullable=True),
    sa.Column('final_model_path', sa.String(length=500), nullable=True),
    sa.Column('pred_type', sa.String(length=10), nullable=False),
    sa.Column('pengguna_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id'], ),
    sa.ForeignKeyConstraint(['split_config_id'], ['split_config.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('dokumentasi_foto',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('lokasi_id', sa.Integer(), nullable=False),
    sa.Column('nama_file', sa.String(length=255), nullable=False),
    sa.Column('path_file', sa.String(length=500), nullable=False),
    sa.Column('ukuran_kb', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['lokasi_id'], ['lokasi_kerusakan.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('label_kerusakan',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('lokasi_id', sa.Integer(), nullable=False),
    sa.Column('persen_retak', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('jenis_retak', sa.Enum('halus', 'lebar'), nullable=False),
    sa.Column('jumlah_lubang', sa.Integer(), nullable=False),
    sa.Column('kedalaman_rutting', sa.Numeric(precision=5, scale=2), nullable=False),
    sa.Column('sdi_score', sa.Numeric(precision=6, scale=2), nullable=False),
    sa.Column('tingkat_kerusakan_id', sa.Integer(), nullable=False),
    sa.Column('catatan', sa.Text(), nullable=True),
    sa.Column('pengguna_id', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['lokasi_id'], ['lokasi_kerusakan.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id'], ),
    sa.ForeignKeyConstraint(['tingkat_kerusakan_id'], ['tingkat_kerusakan.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lokasi_id')
    )
    op.create_table('hasil_augmentasi',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('dokumentasi_id', sa.Integer(), nullable=False),
    sa.Column('config_id', sa.Integer(), nullable=False),
    sa.Column('salinan_ke', sa.Integer(), nullable=False),
    sa.Column('path_output', sa.String(length=500), nullable=False),
    sa.Column('status', sa.Enum('selesai', 'gagal'), nullable=False),
    sa.Column('catatan', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['config_id'], ['augmentasi_config.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['dokumentasi_id'], ['dokumentasi_foto.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('hasil_evaluasi',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('arsitektur_id', sa.Integer(), nullable=False),
    sa.Column('total_data_val', sa.Integer(), nullable=False),
    sa.Column('akurasi', sa.Float(), nullable=False),
    sa.Column('confusion_matrix', sa.Text(), nullable=False),
    sa.Column('per_class', sa.Text(), nullable=False),
    sa.Column('macro_precision', sa.Float(), nullable=False),
    sa.Column('macro_recall', sa.Float(), nullable=False),
    sa.Column('macro_f1', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['arsitektur_id'], ['arsitektur_config.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('hasil_klasifikasi_cnn',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('dokumentasi_id', sa.Integer(), nullable=False),
    sa.Column('jenis_kerusakan_id', sa.Integer(), nullable=True),
    sa.Column('tingkat_kerusakan_id', sa.Integer(), nullable=False),
    sa.Column('confidence_score', sa.Float(), nullable=False),
    sa.Column('is_valid', sa.Boolean(), nullable=False),
    sa.Column('catatan', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['dokumentasi_id'], ['dokumentasi_foto.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['jenis_kerusakan_id'], ['jenis_kerusakan.id'], ),
    sa.ForeignKeyConstraint(['tingkat_kerusakan_id'], ['tingkat_kerusakan.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('dokumentasi_id')
    )
    op.create_table('hasil_preprocessing',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('dokumentasi_id', sa.Integer(), nullable=False),
    sa.Column('config_id', sa.Integer(), nullable=False),
    sa.Column('step_name', sa.String(length=20), nullable=False),
    sa.Column('path_output', sa.String(length=500), nullable=False),
    sa.Column('ukuran_kb_asal', sa.Integer(), nullable=True),
    sa.Column('ukuran_kb_hasil', sa.Integer(), nullable=True),
    sa.Column('durasi_ms', sa.Integer(), nullable=True),
    sa.Column('status', sa.Enum('selesai', 'gagal'), nullable=False),
    sa.Column('catatan', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['config_id'], ['preprocessing_config.id'], ),
    sa.ForeignKeyConstraint(['dokumentasi_id'], ['dokumentasi_foto.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('hasil_training',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('arsitektur_id', sa.Integer(), nullable=False),
    sa.Column('epoch', sa.Integer(), nullable=False),
    sa.Column('loss', sa.Float(), nullable=False),
    sa.Column('accuracy', sa.Float(), nullable=False),
    sa.Column('val_loss', sa.Float(), nullable=False),
    sa.Column('val_accuracy', sa.Float(), nullable=False),
    sa.ForeignKeyConstraint(['arsitektur_id'], ['arsitektur_config.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('prediksi_model',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('arsitektur_id', sa.Integer(), nullable=False),
    sa.Column('dokumentasi_id', sa.Integer(), nullable=False),
    sa.Column('prediksi', sa.SmallInteger(), nullable=False),
    sa.Column('aktual', sa.SmallInteger(), nullable=True),
    sa.Column('confidence', sa.Float(), nullable=False),
    sa.Column('probabilitas', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['arsitektur_id'], ['arsitektur_config.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['dokumentasi_id'], ['dokumentasi_foto.id'], ondelete='CASCADE'),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('split_item',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('config_id', sa.Integer(), nullable=False),
    sa.Column('dokumentasi_id', sa.Integer(), nullable=False),
    sa.Column('tingkat_kerusakan_id', sa.Integer(), nullable=False),
    sa.Column('fold_index', sa.SmallInteger(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['config_id'], ['split_config.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['dokumentasi_id'], ['dokumentasi_foto.id'], ondelete='CASCADE'),
    sa.ForeignKeyConstraint(['tingkat_kerusakan_id'], ['tingkat_kerusakan.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_table('peta_kerusakan',
    sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
    sa.Column('lokasi_id', sa.Integer(), nullable=False),
    sa.Column('hasil_klasifikasi_id', sa.Integer(), nullable=False),
    sa.Column('status_pemetaan', sa.Enum('draft', 'terverifikasi', 'diperbaiki'), nullable=False),
    sa.Column('prioritas_perbaikan', sa.Integer(), nullable=False),
    sa.Column('tanggal_pemetaan', sa.Date(), nullable=False),
    sa.Column('pengguna_id', sa.Integer(), nullable=False),
    sa.ForeignKeyConstraint(['hasil_klasifikasi_id'], ['hasil_klasifikasi_cnn.id'], ),
    sa.ForeignKeyConstraint(['lokasi_id'], ['lokasi_kerusakan.id'], ),
    sa.ForeignKeyConstraint(['pengguna_id'], ['pengguna.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lokasi_id')
    )

    # Index ini ada di MySQL produksi tapi tidak dideklarasikan model (tidak ada
    # `index=True` di app/models). Tanpa ikut direproduksi, instalasi baru akan
    # berjalan tanpa index ini dan `uk_arsitektur_dok` kehilangan guarantor bahwa
    # satu dokumentasi tidak diprediksi dua kali oleh arsitektur yang sama.
    op.create_index('idx_cnn_valid', 'hasil_klasifikasi_cnn', ['is_valid'])
    op.create_index('idx_lokasi_koordinat', 'lokasi_kerusakan', ['latitude', 'longitude'])
    op.create_index('idx_lokasi_sumber', 'lokasi_kerusakan', ['sumber_data'])
    op.create_index('idx_peta_prioritas', 'peta_kerusakan', ['prioritas_perbaikan'])
    op.create_index('idx_peta_status', 'peta_kerusakan', ['status_pemetaan'])
    op.create_index('idx_split_fold', 'split_item', ['config_id', 'fold_index'])
    op.create_index('uk_arsitektur_dok', 'prediksi_model', ['arsitektur_id', 'dokumentasi_id'], unique=True)


def downgrade():
    op.drop_table('peta_kerusakan')
    op.drop_table('split_item')
    op.drop_table('prediksi_model')
    op.drop_table('hasil_training')
    op.drop_table('hasil_preprocessing')
    op.drop_table('hasil_klasifikasi_cnn')
    op.drop_table('hasil_evaluasi')
    op.drop_table('hasil_augmentasi')
    op.drop_table('label_kerusakan')
    op.drop_table('dokumentasi_foto')
    op.drop_table('arsitektur_config')
    op.drop_table('split_config')
    op.drop_table('preprocessing_config')
    op.drop_table('lokasi_kerusakan')
    op.drop_table('augmentasi_config')
    op.drop_table('tingkat_kerusakan')
    op.drop_table('pengguna')
    op.drop_table('jenis_kerusakan')
    op.drop_table('evaluasi_model')
