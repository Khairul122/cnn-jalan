from app import utcnow
from app import db


class PreprocessingConfig(db.Model):
    __tablename__ = 'preprocessing_config'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_config    = db.Column(db.String(100), nullable=False)
    # Resize
    target_width   = db.Column(db.Integer, nullable=False, default=256)
    target_height  = db.Column(db.Integer, nullable=False, default=256)
    resize_method  = db.Column(db.Enum('LANCZOS', 'BILINEAR', 'BICUBIC', 'NEAREST', 'LANCZOS_CV'), nullable=False, default='LANCZOS')
    resize_mode      = db.Column(db.Enum('stretch', 'letterbox'), nullable=False, default='stretch')
    illum_correction = db.Column(db.Boolean, nullable=False, default=False)
    # Center Crop
    crop_enabled   = db.Column(db.Boolean, nullable=False, default=True)
    crop_width     = db.Column(db.Integer, nullable=False, default=224)
    crop_height    = db.Column(db.Integer, nullable=False, default=224)
    # Normalisasi
    norm_method    = db.Column(db.Enum('minmax', 'zscore', 'none', 'clahe'), nullable=False, default='none')
    # Denoise
    denoise_method = db.Column(db.Enum('none', 'gaussian', 'median', 'bilateral', 'nlmeans'), nullable=False, default='bilateral')
    denoise_ksize  = db.Column(db.Integer, nullable=False, default=3)
    # Meta
    is_default     = db.Column(db.Boolean, nullable=False, default=False)
    pengguna_id    = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at     = db.Column(db.DateTime, default=utcnow)

    hasil_list = db.relationship('HasilPreprocessing', backref='config', lazy=True, cascade='all, delete-orphan')
    pengguna   = db.relationship('Pengguna', backref='preprocessing_config_list', lazy=True)

    @classmethod
    def aktif(cls):
        """Config yang menghasilkan hasil_preprocessing saat ini. Invarian: hasil_preprocessing hanya
        berisi satu config (menjalankan preprocessing menggantikan hasil sebelumnya), jadi data training
        dan foto baru selalu diproses dengan config yang sama. Belum ada hasil -> config bawaan/pertama."""
        from app.models.hasil_preprocessing import HasilPreprocessing
        terakhir = HasilPreprocessing.query.order_by(HasilPreprocessing.id.desc()).first()
        return (terakhir.config if terakhir else None) \
            or cls.query.filter_by(is_default=True).first() or cls.query.order_by(cls.id).first()

    def __repr__(self):
        return f'<PreprocessingConfig {self.nama_config}>'

