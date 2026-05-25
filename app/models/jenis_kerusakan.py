from app import db


class JenisKerusakan(db.Model):
    __tablename__ = 'jenis_kerusakan'

    id         = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nama_jenis = db.Column(db.String(50), nullable=False)
    kode       = db.Column(db.String(10), nullable=False, unique=True)
    deskripsi  = db.Column(db.Text)

    klasifikasi_list = db.relationship('HasilKlasifikasiCnn', backref='jenis_kerusakan', lazy=True)

    def __repr__(self):
        return f'<JenisKerusakan {self.kode}>'
