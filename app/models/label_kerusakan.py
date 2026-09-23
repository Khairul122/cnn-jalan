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

    # Kalibrasi formula kontinu estimasi_dari_dimensi() (opsi A, diputuskan 2026-09-23
    # menggantikan tabel diskrit 5-bucket lama — lihat CLAUDE.md untuk rasionalnya).
    REF_RETAK    = 1.0    # m^2 per 1 poin persen_retak, sebelum dipotong di 100
    REF_RUTTING  = 4.0    # m^2 per 1 cm kedalaman rutting
    RUTTING_MAX  = 5.0    # cm, batas atas fisik yang masuk akal
    AMBANG_LEBAR = 2.0    # m^2 — di atas ini jenis_retak dianggap 'lebar'
    LUBANG_MAX   = 999    # cap tampilan — F_lubang sendiri sudah jenuh di jumlah_lubang > 50

    @staticmethod
    def estimasi_dari_dimensi(panjang, lebar):
        """Estimasi kontinu parameter SDI dari dimensi kerusakan (panjang Ã— lebar = area mÂ²).

        Formula dasar dari studi.md:
          persen_retak      = min(luas / REF_RETAK, 100)
          jumlah_lubang     = luas / 0,1                 (1 lubang per 0,1 mÂ², studi.md)
          kedalaman_rutting = min(luas / REF_RUTTING, RUTTING_MAX)
          jenis_retak       = 'lebar' kalau luas > AMBANG_LEBAR, selain itu 'halus'

        REF_RETAK/REF_RUTTING/AMBANG_LEBAR adalah pilihan kalibrasi (bukan nilai baku Bina
        Marga) berdasarkan distribusi luas riil dataset (persentil 10â€“95 âˆˆ [1, 60] mÂ², audit
        2026-09-23) supaya nilai tersebar ke semua bucket F_retak/F_rutting, bukan menumpuk di
        satu bucket seperti tabel diskrit lama (yang cuma menghasilkan 5 SDI tetap untuk 280
        foto, tidak pernah dekat ambang 50/150). AMBANG_LEBAR=2 mÂ² mengikuti titik transisi
        halus->lebar pada tabel lama. Didokumentasikan sebagai keterbatasan metodologis (bukan
        nilai terukur) di CLAUDE.md/bab pembahasan skripsi.

        jumlah_lubang dipotong di LUBANG_MAX untuk tampilan â€” beberapa baris 'Ukur' di dataset
        punya panjang dalam ribuan meter (kemungkinan data segmen jalan, bukan patch kerusakan)
        yang tanpa cap menghasilkan angka jumlah_lubang tidak masuk akal; F_lubang di hitung_sdi
        sendiri sudah jenuh di jumlah_lubang > 50 jadi hasil SDI tidak berubah.
        """
        p = float(panjang or 1.0)
        l = float(lebar or 0.5)
        area = p * l

        persen_retak = round(min(area / LabelKerusakan.REF_RETAK, 100), 2)
        jumlah_lubang = min(int(round(area / 0.1)), LabelKerusakan.LUBANG_MAX)
        kedalaman_rutting = round(min(area / LabelKerusakan.REF_RUTTING, LabelKerusakan.RUTTING_MAX), 2)
        jenis_retak = 'lebar' if area > LabelKerusakan.AMBANG_LEBAR else 'halus'

        params = dict(persen_retak=persen_retak, jenis_retak=jenis_retak,
                      jumlah_lubang=jumlah_lubang, kedalaman_rutting=kedalaman_rutting)
        sdi = LabelKerusakan.hitung_sdi(**params)
        return params, sdi, area

    def __repr__(self):
        return f'<LabelKerusakan lokasi={self.lokasi_id} sdi={self.sdi_score}>'

