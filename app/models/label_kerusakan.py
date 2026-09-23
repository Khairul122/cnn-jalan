from app import utcnow
from app import db


class LabelKerusakan(db.Model):
    __tablename__ = 'label_kerusakan'

    id                   = db.Column(db.Integer, primary_key=True, autoincrement=True)
    lokasi_id            = db.Column(db.Integer, db.ForeignKey('lokasi_kerusakan.id', ondelete='CASCADE'), nullable=False, unique=True)
    persen_retak         = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    jenis_retak          = db.Column(db.Enum('halus', 'lebar'), nullable=False, default='halus')
    jumlah_lubang        = db.Column(db.Integer, nullable=False, default=0)
    kedalaman_rutting    = db.Column(db.Numeric(5, 2), nullable=False, default=0)
    sdi_score            = db.Column(db.Numeric(6, 2), nullable=False, default=0)
    tingkat_kerusakan_id = db.Column(db.Integer, db.ForeignKey('tingkat_kerusakan.id'), nullable=False)
    catatan              = db.Column(db.Text, nullable=True)
    pengguna_id          = db.Column(db.Integer, db.ForeignKey('pengguna.id'), nullable=False)
    created_at           = db.Column(db.DateTime, default=utcnow)
    updated_at           = db.Column(db.DateTime, default=utcnow, onupdate=utcnow)

    tingkat = db.relationship('TingkatKerusakan', backref='label_list', lazy=True)
    pengguna = db.relationship('Pengguna', backref='label_list', lazy=True)

    @staticmethod
    def hitung_sdi(persen_retak, jenis_retak, jumlah_lubang, kedalaman_rutting):
        """Hitung SDI berdasarkan standar Bina Marga."""
        p = float(persen_retak or 0)
        j = str(jenis_retak or 'halus')
        l = int(jumlah_lubang or 0)
        r = float(kedalaman_rutting or 0)

        # F_retak
        if p == 0:
            f_retak = 0
        elif p <= 10:
            f_retak = 5
        elif p <= 20:
            f_retak = 20
        else:
            f_retak = 40
        if j == 'lebar':
            f_retak *= 2

        # F_lubang
        if l == 0:
            f_lubang = 0
        elif l <= 10:
            f_lubang = 15
        elif l <= 50:
            f_lubang = 75
        else:
            f_lubang = 225

        # F_rutting
        if r == 0:
            f_rutting = 0
        elif r <= 1:
            f_rutting = 5
        elif r <= 3:
            f_rutting = 20
        else:
            f_rutting = 40

        return round(f_retak + f_lubang + f_rutting, 2)

    @staticmethod
    def tingkat_dari_sdi(sdi):
        """Kembalikan tingkat_kerusakan_id berdasarkan skor SDI."""
        sdi = float(sdi)
        if sdi <= 50:
            return 3   # Ringan
        elif sdi <= 150:
            return 2   # Sedang
        else:
            return 1   # Berat

    @staticmethod
    def estimasi_dari_dimensi(panjang, lebar):
        """Estimasi parameter SDI dari dimensi kerusakan dalam meter (panjang Ã— lebar = area mÂ²).

        Mapping area â†’ parameter SDI:
          area â‰¤ 0.5  â†’ SDI ~20  â†’ Ringan
          area â‰¤ 2    â†’ SDI ~25  â†’ Ringan
          area â‰¤ 6    â†’ SDI ~75  â†’ Sedang
          area â‰¤ 12   â†’ SDI ~135 â†’ Sedang
          area  > 12  â†’ SDI ~195 â†’ Berat
        """
        p = float(panjang or 1.0)
        l = float(lebar or 0.5)
        area = p * l

        if area <= 0.5:
            params = dict(persen_retak=5,  jenis_retak='halus', jumlah_lubang=1,  kedalaman_rutting=0.0)
        elif area <= 2:
            params = dict(persen_retak=8,  jenis_retak='halus', jumlah_lubang=5,  kedalaman_rutting=0.5)
        elif area <= 6:
            params = dict(persen_retak=15, jenis_retak='lebar', jumlah_lubang=8,  kedalaman_rutting=1.5)
        elif area <= 12:
            params = dict(persen_retak=18, jenis_retak='lebar', jumlah_lubang=20, kedalaman_rutting=2.0)
        else:
            params = dict(persen_retak=25, jenis_retak='lebar', jumlah_lubang=30, kedalaman_rutting=3.5)

        sdi = LabelKerusakan.hitung_sdi(**params)
        return params, sdi, area

    def __repr__(self):
        return f'<LabelKerusakan lokasi={self.lokasi_id} sdi={self.sdi_score}>'

