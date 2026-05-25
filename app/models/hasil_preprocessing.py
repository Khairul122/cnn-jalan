from datetime import datetime
from app import db


class HasilPreprocessing(db.Model):
    __tablename__ = 'hasil_preprocessing'

    id              = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dokumentasi_id  = db.Column(db.Integer, db.ForeignKey('dokumentasi_foto.id', ondelete='CASCADE'), nullable=False)
    config_id       = db.Column(db.Integer, db.ForeignKey('preprocessing_config.id'), nullable=False)
    path_output     = db.Column(db.String(500), nullable=False)
    ukuran_kb_asal  = db.Column(db.Integer, nullable=True)
    ukuran_kb_hasil = db.Column(db.Integer, nullable=True)
    durasi_ms       = db.Column(db.Integer, nullable=True)
    status          = db.Column(db.Enum('selesai', 'gagal'), nullable=False, default='selesai')
    catatan         = db.Column(db.Text, nullable=True)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    dokumentasi = db.relationship('DokumentasiFoto', backref='preprocessing_list', lazy=True)

    def __repr__(self):
        return f'<HasilPreprocessing doc={self.dokumentasi_id} status={self.status}>'
