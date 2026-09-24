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
        elif p <= 30:
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
            f_rutting = 2.5
        elif r <= 3:
            f_rutting = 10
        else:
            f_rutting = 20

        return round(f_retak + f_lubang + f_rutting, 2)

    @staticmethod
    def tingkat_dari_sdi(sdi):
        """Kembalikan tingkat_kerusakan_id berdasarkan skor SDI."""
        sdi = float(sdi)
        if sdi < 50:
            return 4   # Baik
        elif sdi <= 100:
            return 3   # Sedang
        elif sdi <= 150:
            return 2   # Rusak Ringan
        else:
            return 1   # Rusak Berat

    # Model estimasi SDI dari luas (P x L). Semua konstanta di bawah adalah ASUMSI kalibrasi,
    # bukan hasil ukur di lapangan (dataset tidak punya jumlah lubang / kedalaman rutting).
    # Standar Bina Marga mengukur per segmen 100 m, jadi retak dinyatakan sebagai % luas segmen.
    SEGMEN_M2    = 700.0  # 100 m x 7 m (jalan 2 lajur), penyebut persen_retak
    LUBANG_M2    = 0.5    # asumsi luas satu lubang (m^2) -> jumlah_lubang = luas / LUBANG_M2
    REF_RUTTING  = 4.0    # m^2 per 1 cm kedalaman rutting
    RUTTING_MAX  = 5.0    # cm, batas atas fisik yang masuk akal
    AMBANG_LEBAR = 2.0    # m^2 — di atas ini jenis_retak dianggap 'lebar'
    LUBANG_MAX   = 999    # cap tampilan — F_lubang sendiri sudah jenuh di jumlah_lubang > 50

    @staticmethod
    def estimasi_dari_dimensi(panjang, lebar):
        """Estimasi parameter SDI dari dimensi kerusakan (panjang x lebar = luas m^2).

          persen_retak      = min(luas / SEGMEN_M2 * 100, 100)
          jumlah_lubang     = luas / LUBANG_M2
          kedalaman_rutting = min(luas / REF_RUTTING, RUTTING_MAX)
          jenis_retak       = 'lebar' kalau luas > AMBANG_LEBAR, selain itu 'halus'

        Keterbatasan (wajib disebut di bab metodologi): jumlah lubang dan kedalaman rutting
        tidak pernah diukur, keduanya proksi dari luas. Kelas Rusak Ringan/Rusak Berat praktis
        hanya bisa dicapai lewat F_lubang, jadi kelas ditentukan luas kerusakan, bukan jenisnya.
        """
        p = float(panjang or 1.0)
        l = float(lebar or 0.5)
        area = p * l

        persen_retak = round(min(area / LabelKerusakan.SEGMEN_M2 * 100, 100), 2)
        jumlah_lubang = min(int(round(area / LabelKerusakan.LUBANG_M2)), LabelKerusakan.LUBANG_MAX)
        kedalaman_rutting = round(min(area / LabelKerusakan.REF_RUTTING, LabelKerusakan.RUTTING_MAX), 2)
        jenis_retak = 'lebar' if area > LabelKerusakan.AMBANG_LEBAR else 'halus'

        params = dict(persen_retak=persen_retak, jenis_retak=jenis_retak,
                      jumlah_lubang=jumlah_lubang, kedalaman_rutting=kedalaman_rutting)
        sdi = LabelKerusakan.hitung_sdi(**params)
        return params, sdi, area

    def __repr__(self):
        return f'<LabelKerusakan lokasi={self.lokasi_id} sdi={self.sdi_score}>'

