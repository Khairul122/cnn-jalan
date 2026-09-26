"""Menjaga agar Tailwind tidak kembali dan Bootstrap 5 tetap jadi sistem layout.

Bootstrap 5 dipulihkan sebagai sistem layout/komponen. Uji ini memastikan tidak
ada sisa kelas Tailwind di template internal, Bootstrap 5 dimuat di shell, dan
landing page memakai token yang sama tanpa Tailwind.
"""

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TEMPLATES = ROOT / "app" / "templates"
BASE = TEMPLATES / "base.html"

TAILWIND_UTILITIES = [
    "items-center", "items-start", "justify-between", "justify-center", "justify-end",
    "md:flex", "lg:hidden", "sm:block", "md:hidden",
    "text-xs", "text-sm", "text-lg", "text-xl", "font-semibold", "font-medium",
    "bg-white", "text-gray-500", "bg-gray-100", "rounded-lg", "rounded-xl", "shadow-md",
    "min-h-screen", "max-w-md", "flex-1", "shrink-0", "z-50",
]
TARGETS = [
    "lokasi/index.html", "lokasi/detail.html", "label/index.html", "label/hasil.html",
    "preprocessing/index.html", "augmentasi/index.html", "split/index.html",
    "arsitektur/index.html", "peta/index.html",
]


def class_tokens(html):
    out = set()
    for match in re.finditer(r'class="([^"}]*)"', html):
        out.update(token.split("{")[0].strip() for token in match.group(1).split() if token)
    return out


class TestNoTailwindClasses(unittest.TestCase):
    def test_targets_exist(self):
        for rel in TARGETS:
            self.assertTrue((TEMPLATES / rel).exists(), f"{rel} tidak ada")

    def test_no_tailwind_utilities(self):
        for rel in TARGETS:
            found = sorted(class_tokens((TEMPLATES / rel).read_text(encoding="utf-8"))
                           & set(TAILWIND_UTILITIES))
            self.assertEqual(found, [], f"{rel} masih memakai utility Tailwind: {', '.join(found)}")

    def test_no_tailwind_colon_variants(self):
        for rel in TARGETS:
            html = (TEMPLATES / rel).read_text(encoding="utf-8")
            found = sorted(t for t in class_tokens(html) if re.match(r"^(sm|md|lg|xl|hover|focus):", t))
            self.assertEqual(found, [], f"{rel} masih memakai varian responsif Tailwind: {', '.join(found)}")

    def test_bootstrap_is_loaded(self):
        html = BASE.read_text(encoding="utf-8")
        self.assertIn("bootstrap@5.3.3/dist/css/bootstrap.min.css", html, "Bootstrap CSS belum dimuat")
        self.assertIn("bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js", html, "Bootstrap JS belum dimuat")

    def test_tailwind_is_gone_from_shell(self):
        html = BASE.read_text(encoding="utf-8")
        self.assertNotIn("cdn.tailwindcss.com", html, "Tailwind Play CDN masih dimuat")
        self.assertNotIn("tailwind.config", html, "tailwind.config masih ada")

    def test_landing_uses_bootstrap_and_tokens_not_tailwind(self):
        """Landing publik berdiri sendiri (tanpa base.html) tetapi memakai token dan Bootstrap yang sama."""
        html = (TEMPLATES / "landing" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("tailwind", html.lower())
        self.assertIn("bootstrap@5.3.3/dist/css/bootstrap.min.css", html)
        self.assertIn("css/tokens.css", html)
        self.assertNotIn("{% extends", html)

    def test_page_templates_carry_no_inline_style_block(self):
        """Aturan tampilan tinggal di components.css/layout.css. Blok <style> di
        template memakai kelas ad-hoc yang lolos dari design system. Daftar izin
        di bawah menyusut sampai kosong; jangan tambah entri baru."""
        allowlist = {
            # Menyusut: pindahkan aturannya ke components.css lalu hapus entri.
            "arsitektur/detail.html", "arsitektur/evaluasi.html",
            "arsitektur/form.html", "arsitektur/gis.html", "arsitektur/index.html",
            "dashboard/index.html", "peta/index.html",
            "preprocessing/config_form.html", "preprocessing/hasil.html",
            "split/detail.html",
            # Tetap: satu-satunya inline style yang sah, mengunci layout auth.
            "auth/login.html", "auth/register.html",
        }
        for rel in sorted(allowlist):
            self.assertTrue((TEMPLATES / rel).exists(), f"{rel} tidak ada")
        for path in sorted(TEMPLATES.rglob("*.html")):
            rel = path.relative_to(TEMPLATES).as_posix()
            if rel.startswith("landing/") or rel in allowlist:
                continue
            html = path.read_text(encoding="utf-8")
            self.assertNotIn("<style>", html, f"{rel} punya blok <style> inline")

    def test_detail_layout_uses_shared_grid_class(self):
        html = (TEMPLATES / "lokasi" / "detail.html").read_text(encoding="utf-8")
        self.assertIn("grid--detail", html)
        self.assertNotIn("detail-grid", html, "grid kolom ad-hoc masih dipakai")

    def test_augmentasi_pages_use_the_design_system(self):
        """Halaman index dan form konfigurasi augmentasi dulu memakai markup
        telanjang: div tanpa kelas, tabel tanpa panel, input tanpa .control.
        Kontrak ini menjaga keduanya tetap di dalam design system."""
        index = (TEMPLATES / "augmentasi" / "index.html").read_text(encoding="utf-8")
        form = (TEMPLATES / "augmentasi" / "config_form.html").read_text(encoding="utf-8")

        for rel, html in (("index.html", index), ("config_form.html", form)):
            self.assertNotIn("<style>", html, f"{rel} punya blok <style>")
            self.assertNotIn("btn-cnn-primary", html, f"{rel} memakai tombol legacy")
            self.assertNotIn("cnn-table", html, f"{rel} memakai tabel legacy")

        self.assertIn('include \'components/page_header.html\'', index)
        self.assertIn("kpi_card.html", index, "KPI tidak memakai komponen bersama")
        self.assertIn("config_list", index)

        self.assertIn("aug-param", form, "blok parameter tidak memakai komponen .aug-param")
        self.assertIn('class="panel__foot"', form, "tombol simpan tidak memakai footer panel")
        self.assertIn('class="control"', form, "input tidak memakai .control")

        # Setiap kunci transformasi harus tetap mengirim pasangan field yang sama,
        # karena _params_dari_form membacanya berdasarkan nama.
        for kunci in ("flip", "rotasi", "zoom", "translasi", "brightness", "contrast",
                      "hue", "saturasi", "noise", "erasing"):
            self.assertIn(f'name="{{{{ kunci }}}}_aktif"', form)
            self.assertIn(f'name="{{{{ kunci }}}}_{{{{ k }}}}"', form)

    def test_split_pages_use_the_design_system(self):
        """Index dan form split dulu membawa blok <style> masing-masing 2 KB
        dengan kelas ad-hoc (split-stat-card, sf-input, btn-split-primary) dan
        grid KPI tanpa gap. Keduanya sudah pindah ke components.css."""
        index = (TEMPLATES / "split" / "index.html").read_text(encoding="utf-8")
        form = (TEMPLATES / "split" / "form.html").read_text(encoding="utf-8")

        legacy = ("btn-split-primary", "btn-split-cancel", "split-stat-card",
                  "split-stat-val", "split-stat-lbl", "split-table-wrap",
                  "split-empty", "btn-action-view", "btn-action-del", "fold-badge",
                  "sf-info-bar", "sf-info-item", "sf-info-sep", "sf-card", "sf-field",
                  "sf-label", "sf-input", "sf-tag")
        for rel, html in (("index.html", index), ("form.html", form)):
            self.assertNotIn("<style>", html, f"{rel} punya blok <style>")
            for cls in legacy:
                self.assertNotIn(cls, html, f"{rel} masih memakai kelas ad-hoc {cls}")
            self.assertIn('include \'components/page_header.html\'', html)

        self.assertIn("kpi_card.html", index, "KPI tidak memakai komponen bersama")
        self.assertIn('class="panel"', index)
        self.assertIn("table-actions", index)

        # Nilai warna tidak boleh ditulis sebagai deklarasi literal di markup;
        # hanya custom property, supaya token tetap satu sumber.
        for rel, html in (("index.html", index), ("form.html", form)):
            for decl in re.findall(r'style="([^"]*)"', html):
                for prop in ("color:", "background:", "border:", "padding:", "font-size:"):
                    self.assertNotIn(prop, decl, f"{rel} punya deklarasi {prop} inline: {decl}")

        for nama in ("nama", "n_splits", "random_state", "radius_grup_m", "ulangan"):
            self.assertIn(f'name="{nama}"', form, f"field {nama} hilang dari form split")
        self.assertIn("previewText", form, "target pratinjau JS hilang")
        self.assertIn("function updatePreview", form, "updatePreview hilang")
        self.assertIn('name="n_splits"', form)
        self.assertIn("onchange=\"updatePreview()\"", form)
        self.assertIn("oninput=\"updatePreview()\"", form)


if __name__ == "__main__":
    unittest.main()
