from datetime import datetime
from app import db


class DokumentasiFoto(db.Model):
    __tablename__ = 'dokumentasi_foto'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lokasi_id  = db.Column(db.Integer, db.ForeignKey('lokasi_kerusakan.id'), nullable=False)
    nama_file  = db.Column(db.String(255), nullable=False)
    path_file  = db.Column(db.String(500), nullable=False)
    ukuran_kb  = db.Column(db.Integer, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    hasil_klasifikasi = db.relationship('HasilKlasifikasiCnn', backref='dokumentasi', uselist=False, lazy=True, cascade='all, delete-orphan')

    def __repr__(self):
        return f'<DokumentasiFoto {self.nama_file}>'
