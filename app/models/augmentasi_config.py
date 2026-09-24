import json

from app import utcnow
from app import db


class AugmentasiConfig(db.Model):
    """Konfigurasi tahap Augmentasi (terpisah dari Preprocessing). Menghasilkan `n_salinan` gambar tambahan per foto
    dari hasil tahap denoise; salinan mewarisi kelas dan fold foto asalnya (lihat cnn_service.dataset.load_dataset)."""
    __tablename__ = 'augmentasi_config'

    id          = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_config = db.Column(db.String(100), nullable=False)
    n_salinan   = db.Column(db.Integer, nullable=False, default=3)
    seed        = db.Column(db.Integer, nullable=False, default=42)
    parameter   = db.Column(db.Text, nullable=False)          # JSON {transformasi: {aktif, ...besaran}}, lihat augmentation_service
    is_default  = db.Column(db.Boolean, nullable=False, default=False)
    pengguna_id = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at  = db.Column(db.DateTime, default=utcnow)

    hasil_list = db.relationship('HasilAugmentasi', backref='config', lazy=True, cascade='all, delete-orphan')
    pengguna   = db.relationship('Pengguna', backref='augmentasi_config_list', lazy=True)

    def get_parameter(self):
        return json.loads(self.parameter)

    @classmethod
    def aktif(cls):
        """Config yang menghasilkan hasil_augmentasi saat ini (invarian satu config aktif, seperti preprocessing);
        belum ada hasil -> config bawaan/pertama."""
        from app.models.hasil_augmentasi import HasilAugmentasi
        terakhir = HasilAugmentasi.query.order_by(HasilAugmentasi.id.desc()).first()
        return (terakhir.config if terakhir else None) \
            or cls.query.filter_by(is_default=True).first() or cls.query.order_by(cls.id).first()

    def __repr__(self):
        return f'<AugmentasiConfig {self.nama_config}>'
