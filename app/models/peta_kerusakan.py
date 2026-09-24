from app import db


class PetaKerusakan(db.Model):
    __tablename__ = 'peta_kerusakan'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lokasi_id            = db.Column(db.Integer, db.ForeignKey('lokasi_kerusakan.id'), nullable=False, unique=True)
    hasil_klasifikasi_id = db.Column(db.Integer, db.ForeignKey('hasil_klasifikasi_cnn.id'), nullable=False)
    status_pemetaan      = db.Column(db.Enum('draft', 'terverifikasi', 'diperbaiki'), nullable=False, default='draft')
    prioritas_perbaikan  = db.Column(db.Integer, nullable=False)
    tanggal_pemetaan     = db.Column(db.Date, nullable=False)
    pengguna_id          = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)

    def __repr__(self):
        return f'<PetaKerusakan lokasi={self.lokasi_id} status={self.status_pemetaan}>'
