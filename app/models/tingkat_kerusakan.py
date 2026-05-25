from app import db


class TingkatKerusakan(db.Model):
    __tablename__ = 'tingkat_kerusakan'

    id             = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_tingkat   = db.Column(db.String(20), nullable=False)
    warna_peta     = db.Column(db.String(7), nullable=False)
    skor_prioritas = db.Column(db.Integer, nullable=False)

    klasifikasi_list = db.relationship('HasilKlasifikasiCnn', backref='tingkat_kerusakan', lazy=True)

    def __repr__(self):
        return f'<TingkatKerusakan {self.nama_tingkat}>'
