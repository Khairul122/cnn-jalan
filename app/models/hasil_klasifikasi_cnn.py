from datetime import datetime
from app import db


class HasilKlasifikasiCnn(db.Model):
    __tablename__ = 'hasil_klasifikasi_cnn'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    dokumentasi_id       = db.Column(db.Integer, db.ForeignKey('dokumentasi_foto.id'), nullable=False, unique=True)
    jenis_kerusakan_id   = db.Column(db.Integer, db.ForeignKey('jenis_kerusakan.id'), nullable=False)
    tingkat_kerusakan_id = db.Column(db.Integer, db.ForeignKey('tingkat_kerusakan.id'), nullable=False)
    confidence_score     = db.Column(db.Float, nullable=False)
    is_valid             = db.Column(db.Boolean, nullable=False, default=True)
    catatan              = db.Column(db.Text, nullable=True)
    created_at           = db.Column(db.DateTime, default=datetime.utcnow)

    peta = db.relationship('PetaKerusakan', backref='hasil_klasifikasi', uselist=False, lazy=True)

    def __repr__(self):
        return f'<HasilKlasifikasiCnn dok={self.dokumentasi_id} score={self.confidence_score}>'
