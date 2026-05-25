from datetime import datetime
from app import db


class LokasiKerusakan(db.Model):
    __tablename__ = 'lokasi_kerusakan'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_citra     = db.Column(db.String(50), nullable=False)
    latitude       = db.Column(db.Numeric(10, 7), nullable=False)
    longitude      = db.Column(db.Numeric(10, 7), nullable=False)
    panjang        = db.Column(db.String(20), nullable=True)
    lebar          = db.Column(db.String(20), nullable=True)
    sumber_data    = db.Column(db.Enum('primer', 'sekunder'), nullable=False, default='primer')
    pengguna_id    = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    foto_list = db.relationship('DokumentasiFoto', backref='lokasi', lazy=True, cascade='all, delete-orphan')
    peta      = db.relationship('PetaKerusakan', backref='lokasi', uselist=False, lazy=True)
    label_sdi = db.relationship('LabelKerusakan', backref='lokasi', uselist=False, lazy=True)

    def __repr__(self):
        return f'<LokasiKerusakan {self.nama_citra}>'

