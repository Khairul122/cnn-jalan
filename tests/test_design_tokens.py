"""Menjaga agar token severity selalu terdefinisi.

Empat warna ini berasal dari `tingkat_kerusakan.warna_peta` dan sudah dipakai di
peta. Kalau `--sev-N` hilang, chip dan meter kerusakan tampil tanpa warna sama
sekali, dan tingkat kerusakan jadi tidak bisa dibedakan dari sel kosong.

Uji ini murni membaca CSS: tanpa database, tanpa app context, tanpa Flask. Itu
agar cepat dan tidak gagal saat MySQL sedang mati. Pemeriksaan silang antara
CSS dan database adalah langkah verifikasi terpisah di Task 1 Step 9, bukan
bagian dari suite ini.
"""

import re
import unittest
from pathlib import Path

CSS = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "tokens.css"

# Dikunci dengan tingkat_kerusakan.warna_peta. Mengubahnya berarti warna di UI
# berubah, jadi harus jadi keputusan tersendiri, bukan kebetulan.
EXPECTED = {
    1: "#E53E3E",  # Rusak Berat
    2: "#F97316",  # Rusak Ringan
    3: "#F59E0B",  # Sedang
    4: "#10B981",  # Baik
}

# Warna solid yang boleh ada di :root besides severity: status dan aksen.
ALLOWED_SOLID = set(EXPECTED.values()) | {
    "#059669",  # ok
    "#D97706",  # warn
    "#DC2626",  # danger
    "#0284C7",  # info
    "#0F4C81",  # accent
    "#0B3A66",  # accent-hover: shade of the same hue, not a new hue
}

# Pasangan latar, diabaikan oleh pemeriksaan palet.
BACKGROUND_ONLY = {
    "#ECFDF5", "#FFFBEB", "#FEF2F2", "#E0F2FE",
    "#FDECEC", "#FEF0E6", "#FEF6E4", "#E7F8F1",
}


class TestSeverityTokens(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Tidak memakai SkipTest: sebelum tokens.css dibuat, kelas ini harus
        # GAGAL, bukan dilewati, supaya siklus merah-hijau benar-benar bekerja.
        cls.exists = CSS.exists()
        cls.css = CSS.read_text(encoding="utf-8") if cls.exists else ""

    def test_tokens_file_exists(self):
        self.assertTrue(
            self.exists,
            f"{CSS} tidak ada; harus dibuat di Task 1 Step 3",
        )

    def test_every_severity_has_a_token(self):
        for level in EXPECTED:
            self.assertRegex(
                self.css,
                rf"--sev-{level}\s*:\s*#[0-9A-Fa-f]{{6}}\s*;",
                f"token --sev-{level} tidak terdefinisi di tokens.css",
            )

    def test_token_values_are_the_agreed_hex(self):
        """Nilai hex dikunci. Ini kontrak antara CSS dan palette di database."""
        for level, expected_hex in EXPECTED.items():
            match = re.search(rf"--sev-{level}\s*:\s*(#[0-9A-Fa-f]{{6}})", self.css)
            self.assertIsNotNone(match, f"--sev-{level} tidak ditemukan")
            self.assertEqual(
                match.group(1).upper(),
                expected_hex,
                f"--sev-{level} di CSS ({match.group(1).upper()}) berbeda dari "
                f"nilai yang disepakati ({expected_hex})",
            )

    def test_each_severity_has_a_background_companion(self):
        for level in EXPECTED:
            self.assertRegex(
                self.css,
                rf"--sev-{level}-bg\s*:\s*#[0-9A-Fa-f]{{6}}\s*;",
                f"token --sev-{level}-bg tidak terdefinisi",
            )

    def test_severity_defined_exactly_once(self):
        """Delapan definisi: 4 token solid dan 4 pasangan latar."""
        definitions = re.findall(r"^\s*--sev-\d+", self.css, re.MULTILINE)
        self.assertEqual(
            len(definitions), 8,
            f"harus ada 4 --sev-N dan 4 --sev-N-bg, ditemukan {len(definitions)}",
        )

    def test_no_new_chromatic_colour_in_root(self):
        """Klausul palet: empat severity, empat status, satu aksen.

        Warna kromatik lain berarti ada komponen yang belum ada, bukan berarti
        token baru diperlukan. Uji ini menjaga palet tetap empat warna.
        """
        root = self.css.split(":root", 1)[1].split("\n}", 1)[0]
        found = {m.upper() for m in re.findall(r"#[0-9A-Fa-f]{6}", root)}
        unexpected = found - ALLOWED_SOLID - BACKGROUND_ONLY
        # Netral dan pasangan latar lain juga boleh muncul; yang diuji hanya
        # warna kromatik yang tidak ada dalam daftar di atas.
        chromatic = {c for c in unexpected if not _is_neutral(c)}
        self.assertEqual(
            sorted(chromatic), [],
            f"warna kromatik baru di :root: {sorted(chromatic)}",
        )


def _is_neutral(hex_color):
    """True bila warnanya praktis abu-abu, yaitu chroma-nya kecil.

    Chroma diukur sebagai selisih terbesar dari abu-abu dengan kecerahan
    yang sama, bukan selisih mentah antar kanal. Seluruh ramp netral di
    spec ini bernuansa biru (R < G < B), jadi selisih kanal mentah bertambah
    seiring naiknya kecerahan: abu-abu terang seperti #D3D9E0 punya selisih
    13 padahal mata membacanya sebagai abu-abu, bukan sebagai warna.

    Ambang 12% memisahkan dua kelompok itu dengan lebar yang nyaman:
    abu-abu spec berada di 0,0%--5,6%, sedangkan warna kromatik asli
    (aksen 18,0%, status 32,0%--49,8%, dan ungu/merah/biru baru yang
    mungkin menyusul) semuanya di atas 16%.
    """
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    mean = (r + g + b) / 3
    return max(abs(r - mean), abs(g - mean), abs(b - mean)) / 255 <= 0.12


if __name__ == "__main__":
    unittest.main()
