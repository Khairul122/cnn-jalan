from datetime import datetime
from app import db


class PreprocessingConfig(db.Model):
    __tablename__ = 'preprocessing_config'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_config    = db.Column(db.String(100), nullable=False)
    # Resize
    target_width   = db.Column(db.Integer, nullable=False, default=224)
    target_height  = db.Column(db.Integer, nullable=False, default=224)
    resize_method  = db.Column(db.Enum('LANCZOS', 'BILINEAR', 'BICUBIC', 'NEAREST'), nullable=False, default='LANCZOS')
    # Center Crop
    crop_enabled   = db.Column(db.Boolean, nullable=False, default=False)
    crop_width     = db.Column(db.Integer, nullable=False, default=224)
    crop_height    = db.Column(db.Integer, nullable=False, default=224)
    # Normalisasi
    norm_method    = db.Column(db.Enum('minmax', 'zscore', 'none'), nullable=False, default='minmax')
    # Augmentasi
    aug_flip_h     = db.Column(db.Boolean, nullable=False, default=False)
    aug_flip_v     = db.Column(db.Boolean, nullable=False, default=False)
    aug_rotate_deg = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    aug_brightness = db.Column(db.Numeric(4, 2), nullable=False, default=1.0)
    aug_contrast   = db.Column(db.Numeric(4, 2), nullable=False, default=1.0)
    # Denoise
    denoise_method = db.Column(db.Enum('none', 'gaussian', 'median', 'bilateral'), nullable=False, default='none')
    denoise_ksize  = db.Column(db.Integer, nullable=False, default=3)
    # Meta
    is_default     = db.Column(db.Boolean, nullable=False, default=False)
    pengguna_id    = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    hasil_list = db.relationship('HasilPreprocessing', backref='config', lazy=True, cascade='all, delete-orphan')
    pengguna   = db.relationship('Pengguna', backref='preprocessing_config_list', lazy=True)

    def __repr__(self):
        return f'<PreprocessingConfig {self.nama_config}>'
