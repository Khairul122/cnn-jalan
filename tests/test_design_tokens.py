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


class TestShellContract(unittest.TestCase):
    """Menjaga ID dan hook JS yang dibaca toast.js, peta.js, dan dialog konfirmasi.

    Test suite tidak pernah mengeksekusi JavaScript, jadi ID yang salah nama
    hanya akan muncul sebagai TypeError di browser. Test ini memindai markup
    shell secara statis.
    """

    TEMPLATE = Path(__file__).resolve().parent.parent / "app" / "templates" / "base.html"

    LOAD_BEARING = [
        'id="toast-container"',
        'id="flash-data"',
        'id="sidebar"',
        'id="sidebar-overlay"',
        'id="hamburger-btn"',
        'id="main-content"',
        'id="gcModal"',
        'id="gcHeader"',
        'id="gcIconWrap"',
        'id="gcIcon"',
        'id="gcTitle"',
        'id="gcSubtitle"',
        'id="gcMessage"',
        'id="gcConfirmBtn"',
    ]

    def test_shell_exists(self):
        self.assertTrue(self.TEMPLATE.exists())

    def test_load_bearing_ids_present(self):
        html = self.TEMPLATE.read_text(encoding="utf-8")
        for needle in self.LOAD_BEARING:
            self.assertIn(needle, html, f"{needle} hilang dari base.html")

    def test_tailwind_is_gone(self):
        html = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("cdn.tailwindcss.com", html, "Tailwind Play CDN masih dimuat")
        self.assertNotIn("tailwind.config", html, "tailwind.config masih ada")
        for cls in ("-translate-x-full", "lg:hidden", "lg:relative", "lg:flex-shrink-0",
                    "lg:translate-x-0", "z-[9999]", "max-w-[calc(100vw-2rem)]"):
            self.assertNotIn(cls, html, f"utility class Tailwind {cls} masih dipakai")

    def test_bootstrap_css_and_js_are_loaded(self):
        """Bootstrap 5 adalah sistem layout; ia harus dimuat dan dimuat lebih dulu
        daripada lapisan tokens/components/layout agar bisa di-override."""
        html = self.TEMPLATE.read_text(encoding="utf-8")
        css_pos = html.find("bootstrap@5.3.3/dist/css/bootstrap.min.css")
        js_pos = html.find("bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js")
        tokens_pos = html.find("css/tokens.css")
        self.assertNotEqual(css_pos, -1, "Bootstrap CSS belum dimuat")
        self.assertNotEqual(js_pos, -1, "Bootstrap JS belum dimuat")
        self.assertLess(css_pos, tokens_pos, "Bootstrap CSS harus dimuat sebelum tokens.css")

    def test_google_fonts_is_gone(self):
        html = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("fonts.googleapis.com", html, "Google Fonts masih dimuat")
        self.assertNotIn("fonts.gstatic.com", html, "Google Fonts masih dimuat")

    def test_bootstrap_icons_stay(self):
        """Non-goal yang disengaja: icon font dipertahankan."""
        html = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("bootstrap-icons", html, "Bootstrap Icons harus tetap dimuat")

    def test_no_inline_style_in_shell(self):
        html = self.TEMPLATE.read_text(encoding="utf-8")
        found = re.findall(r'style="([^"]*)"', html)
        offenders = [s for s in found if "{" not in s and "{%" not in s]
        self.assertEqual(
            offenders, [],
            "base.html masih punya inline style statis: " + "; ".join(offenders[:5]),
        )

    def test_dialog_colours_come_from_css_not_js(self):
        """showConfirm tidak boleh menyetel warna lewat .style. anymore."""
        html = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn(
            "iconWrap.style.background", html,
            "showConfirm masih menyetel warna dari JS, melanggar aturan tokens.css",
        )
        self.assertNotIn("btn.style.background", html,
                         "showConfirm masih menyetel warna tombol dari JS")
        self.assertIn("dataset.type", html,
                      "dialog harus menetapkan data-type agar CSS yang mengambil alih")

    def test_sidebar_toggle_uses_new_class(self):
        html = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("is-open", html,
                      "toggleSidebar harus memutar kelas .is-open, bukan utility Tailwind")

    def test_content_block_defined_once(self):
        """Jinja hanya izinkan satu {% block content %}. Dua definisi (mis. satu
        di tiap cabang if/else) membuat SETIAP halaman 500 dan tampil tanpa CSS."""
        html = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(
            html.count("{% block content %}"), 1,
            "base.html mendefinisikan block content lebih dari sekali",
        )

    def test_main_landmark_present_in_both_states(self):
        """Skip-link menunjuk #main-content; landmark harus ada di halaman
        auth maupun halaman authed."""
        html = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertEqual(html.count('id="main-content"'), 1)
        self.assertIn('href="#main-content"', html)

    def test_confirm_dialog_uses_bootstrap_modal(self):
        """Dialog konfirmasi memakai modal Bootstrap 5, bukan markup custom."""
        html = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn('class="modal fade"', html, "dialog bukan modal Bootstrap")
        self.assertIn("modal-dialog", html)
        self.assertIn("modal-content", html)
        self.assertIn('data-bs-dismiss="modal"', html, "tombol Batal harus memakai dismiss Bootstrap")
        self.assertNotIn('class="dialog"', html, "markup dialog custom masih tersisa")
        self.assertNotIn("dialog__foot", html)

    def test_confirm_api_preserved_over_bootstrap_modal(self):
        """12 call site memanggil showConfirmForm/showConfirm; API tak boleh berubah."""
        html = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertIn("window.showConfirm = function", html)
        self.assertIn("window.showConfirmForm = function", html)
        self.assertIn("bootstrap.Modal.getOrCreateInstance", html)
        self.assertNotIn("classList.add('is-open')", html.split("Global Confirm Dialog")[1].split("</script>")[0])

    def test_dialog_styles_target_bootstrap_classes(self):
        css = (Path(__file__).resolve().parent.parent
               / "app" / "static" / "css" / "components.css").read_text(encoding="utf-8")
        self.assertIn("#gcModal .modal-content", css)
        self.assertIn("#gcModal .modal-header", css)
        self.assertIn("#gcModal .modal-footer", css)
        self.assertIn('#gcModal[data-type="warning"]', css)

    def test_table_neutralises_bootstrap_cell_rule(self):
        """Bootstrap 5 ships `.table > :not(caption) > * > *` at specificity
        (0,2,3), which beats a plain `.table td` (0,1,1) and forces its own
        padding and background onto every cell. components.css must use the
        same selector shape so the design system wins the cascade."""
        css = (Path(__file__).resolve().parent.parent
               / "app" / "static" / "css" / "components.css").read_text(encoding="utf-8")
        self.assertIn(".table > :not(caption) > * > *", css)
        self.assertIn("box-shadow: none;", css, "box-shadow Bootstrap belum dinetralkan")
        self.assertNotIn(".table td {", css, "selector lama (0,1,1) kalah dari Bootstrap")

    def test_colour_mix_has_an_opaque_fallback(self):
        """color-mix() is a modern-only feature. Where a declaration depends on
        it for text or background colour, an unconditional fallback must come
        first, or an older browser paints white text on a grey background and
        the chip disappears."""
        css = (Path(__file__).resolve().parent.parent
               / "app" / "static" / "css" / "components.css").read_text(encoding="utf-8")
        self.assertIn('.chip[style*="--fc:"]', css)
        chip_block = css[css.index(".status-chip[style*=\"--fc:\"]"):]
        chip_block = chip_block[:chip_block.index("}")]
        self.assertIn("color: var(--fc);", chip_block)
        self.assertIn("background: var(--surface-2);", chip_block)
        self.assertNotIn("color-mix(", chip_block,
                         "color-mix tanpa fallback: chip bisa putih-di-abu")
        self.assertIn("@supports (background: color-mix(", css)


class TestToastContract(unittest.TestCase):
    TOAST = Path(__file__).resolve().parent.parent / "app" / "static" / "js" / "toast.js"

    def setUp(self):
        self.js = self.TOAST.read_text(encoding="utf-8")

    def test_toast_uses_component_classes_and_no_tailwind_utilities(self):
        for utility in (
            "flex", "items-start", "gap-3", "p-4", "bg-red-50", "absolute",
            "overflow-hidden", "w-5", "h-5", "text-sm", "font-medium",
        ):
            self.assertNotRegex(self.js, rf"(?:className|class)\s*[^\n]*\b{re.escape(utility)}\b")
        self.assertIn("toast toast--ok", self.js)
        self.assertIn("toast toast--warn", self.js)
        self.assertIn("toast toast--danger", self.js)
        self.assertIn("toast toast--info", self.js)
        self.assertIn("tw-progress-bar", self.js)

    def test_toast_maps_error_to_danger_and_uses_bootstrap_icons(self):
        self.assertRegex(self.js, r"error:\s*['\"]toast toast--danger['\"]")
        self.assertIn("bi bi-", self.js)
        self.assertNotIn("<svg", self.js)
        self.assertNotRegex(self.js, r"style\.cssText\s*=.*width|transition:width")


class TestRailAndDrawerContract(unittest.TestCase):
    LAYOUT = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "layout.css"
    TOKENS = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "tokens.css"
    TEMPLATE = Path(__file__).resolve().parent.parent / "app" / "templates" / "base.html"

    def setUp(self):
        self.css = self.LAYOUT.read_text(encoding="utf-8")
        self.tokens = self.TOKENS.read_text(encoding="utf-8")
        self.html = self.TEMPLATE.read_text(encoding="utf-8")

    def rail_token(self):
        token = re.search(r"--rail-w:\s*(\d+)px", self.tokens)
        self.assertIsNotNone(token, "--rail-w hilang dari tokens.css")
        return int(token.group(1))

    def test_rail_width_is_one_value_from_the_token(self):
        """Sidebar berlabel: satu lebar di semua viewport desktop. Tidak boleh ada media query
        tablet yang memampatkannya jadi rail ikon-saja."""
        self.assertGreaterEqual(self.rail_token(), 200, "rail terlalu sempit untuk menampilkan label")
        self.assertNotRegex(self.css, r"@media\s*\(min-width:\s*1024px\)\s*and\s*\(max-width:\s*1279px\)",
                            "media query rail ikon-saja untuk tablet masih ada")

    def test_sidebar_shows_text_labels_grouped_by_stage(self):
        """Setiap item menampilkan nama menu sebagai teks (bukan hanya ikon atau tooltip),
        dan dikelompokkan menurut tahap pipeline."""
        for label in ("Dashboard", "Lokasi", "Labeling Visual", "Preprocessing",
                      "Augmentasi", "Split Data", "Arsitektur CNN", "Peta GIS"):
            self.assertIn(f"'{label}'", self.html, f"nav_link {label} hilang dari base.html")
        self.assertIn("sidebar-nav-link__label", self.html)
        self.assertIn("{{ label }}", self.html)
        self.assertNotIn("rail__tip", self.html, "tooltip ikon-saja masih dirender")
        for grup in ("Data", "Persiapan", "Model dan hasil"):
            self.assertIn(f'sidebar-section-label">{grup}<', self.html, f"grup {grup} hilang")
        self.assertRegex(self.css, r"\.sidebar-nav-link__label\s*\{")
        self.assertNotIn(".rail__tip", self.css)

    def test_rail_hit_target_is_at_least_44px(self):
        """Item navigasi harus tetap nyaman disentuh."""
        nav = re.search(r"\.sidebar-nav-link\s*\{(?P<body>.*?)\}", self.css, re.DOTALL)
        self.assertIsNotNone(nav)
        h = re.search(r"min-height:\s*(\d+)px", nav.group("body"))
        self.assertIsNotNone(h)
        self.assertGreaterEqual(int(h.group(1)), 44)

    def test_drawer_keeps_the_same_labelled_width(self):
        """Di bawah 1024px sidebar jadi drawer dengan lebar penuh yang sama seperti di desktop."""
        mobile = re.search(
            r"@media\s*\(max-width:\s*1023px\)\s*\{(?P<body>.*?)\n\}",
            self.css,
            re.DOTALL,
        )
        self.assertIsNotNone(mobile)
        width = re.search(r"#sidebar\s*\{[^}]*width:\s*(\d+)px;", mobile.group("body"))
        self.assertIsNotNone(width, "lebar drawer tidak dideklarasikan")
        self.assertGreaterEqual(int(width.group(1)), self.rail_token())

    def test_header_brand_is_a_plain_container(self):
        """Merek di topbar menggantikan wordmark rail. Bukan link, dan tidak
        boleh memakai kelas Bootstrap yang menyeret gaya lain."""
        self.assertIn('class="shell__brand"', self.html)
        brand = re.search(r'<div class="shell__brand">(?P<body>.*?)</div>', self.html, re.DOTALL)
        self.assertIsNotNone(brand)
        self.assertNotIn("<a ", brand.group("body"))
        header = re.search(r"\.shell__brand\s*\{(?P<body>.*?)\}", self.css, re.DOTALL)
        self.assertIsNotNone(header, ".shell__brand tidak punya aturan di layout.css")

    def test_mobile_rail_remains_off_canvas(self):
        mobile = re.search(
            r"@media\s*\(max-width:\s*1023px\)\s*\{(?P<body>.*?)\}",
            self.css,
            re.DOTALL,
        )
        self.assertIsNotNone(mobile)
        self.assertRegex(mobile.group("body"), r"(?s)#sidebar\s*\{.*?transform:\s*translateX\(-100%\);")

    def test_drawer_functions_guard_missing_sidebar_and_manage_focus(self):
        toggle = re.search(r"window\.toggleSidebar\s*=\s*function \(\)\s*\{(?P<body>.*?)\n\s*\};", self.html, re.DOTALL)
        close = re.search(r"window\.closeSidebar\s*=\s*function \(\)\s*\{(?P<body>.*?)\n\s*\};", self.html, re.DOTALL)
        self.assertIsNotNone(toggle)
        self.assertIsNotNone(close)
        self.assertRegex(toggle.group("body"), r"var\s+sidebar\s*=\s*document\.getElementById\(['\"]sidebar['\"]\)")
        self.assertIn("if (!sidebar) return", toggle.group("body"))
        self.assertIn("focusFirstInSidebar(sidebar)", toggle.group("body"))
        self.assertRegex(close.group("body"), r"button\.focus\(\)")
        self.assertRegex(self.html, r"(?s)function focusFirstInSidebar\(sidebar\).*?\.focus\(\)")
        self.assertRegex(self.html, r"(?s)function focusablesInSidebar\(sidebar\).*?querySelectorAll")

    def test_drawer_handles_tab_trapping_and_safe_escape(self):
        self.assertRegex(self.html, r"e\.key\s*===\s*['\"]Tab['\"]")
        self.assertIn("shiftKey", self.html)
        self.assertRegex(
            self.html,
            r"var\s+sidebar\s*=\s*document\.getElementById\(['\"]sidebar['\"]\);\s*if\s*\(!sidebar\)\s*return",
        )
        self.assertRegex(
            self.html,
            r"(?s)if\s*\(e\.key\s*===\s*['\"]Escape['\"]\).*?closeSidebar\(\)",
        )

    def test_visually_hidden_aliases_sr_only(self):
        self.assertRegex(self.css, r"\.sr-only,\s*\.visually-hidden\s*\{")


class TestDetailRowContract(unittest.TestCase):
    PARTIAL = Path(__file__).resolve().parent.parent / "app" / "templates" / "components" / "detail_row.html"

    def test_detail_row_is_a_list_item(self):
        source = self.PARTIAL.read_text(encoding="utf-8").lstrip()
        self.assertTrue(source.startswith("{#"))
        markup = source[source.index("\n") + 1:].lstrip()
        self.assertTrue(markup.startswith("<li"), "detail_row must be valid inside ul")
        self.assertNotIn("<div class=\"dl__row\">", markup)


if __name__ == "__main__":
    unittest.main()
