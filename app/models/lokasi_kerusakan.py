from app import utcnow
from app import db


class LokasiKerusakan(db.Model):
    __tablename__ = 'lokasi_kerusakan'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_citra     = db.Column(db.String(50), nullable=False)
    latitude       = db.Column(db.Numeric(10, 7), nullable=False)
    longitude      = db.Column(db.Numeric(10, 7), nullable=False)
    panjang        = db.Column(db.Numeric(8, 2), nullable=True)  # meter
    lebar          = db.Column(db.Numeric(8, 2), nullable=True)  # meter
    keterangan     = db.Column(db.String(50), nullable=True)     # 'Ukur' | 'Estimasi (Ringan|Sedang|Berat)'
    sumber_data    = db.Column(db.Enum('primer', 'sekunder'), nullable=False, default='primer')
    pengguna_id    = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at     = db.Column(db.DateTime, default=utcnow)

    foto_list = db.relationship('DokumentasiFoto', backref='lokasi', lazy=True, cascade='all, delete-orphan')
    peta      = db.relationship('PetaKerusakan', backref='lokasi', uselist=False, lazy=True)
    label_sdi = db.relationship('LabelKerusakan', backref='lokasi', uselist=False, lazy=True)

    def __repr__(self):
        return f'<LokasiKerusakan {self.nama_citra}>'


