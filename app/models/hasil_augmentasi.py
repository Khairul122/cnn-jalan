from app import utcnow
from app import db


class HasilAugmentasi(db.Model):
    """Satu salinan hasil augmentasi. `dokumentasi_id` = foto ASAL: salinan selalu ikut kelas dan fold foto itu."""
    __tablename__ = 'hasil_augmentasi'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dokumentasi_id = db.Column(db.Integer, db.ForeignKey('dokumentasi_foto.id', ondelete='CASCADE'), nullable=False)
    config_id      = db.Column(db.Integer, db.ForeignKey('augmentasi_config.id', ondelete='CASCADE'), nullable=False)
    salinan_ke     = db.Column(db.Integer, nullable=False)
    path_output    = db.Column(db.String(500), nullable=False)
    status         = db.Column(db.Enum('selesai', 'gagal'), nullable=False, default='selesai')
    catatan        = db.Column(db.Text, nullable=True)
    created_at     = db.Column(db.DateTime, default=utcnow)

    dokumentasi = db.relationship('DokumentasiFoto', backref='augmentasi_list', lazy=True)

    def __repr__(self):
        return f'<HasilAugmentasi doc={self.dokumentasi_id} salinan={self.salinan_ke}>'
