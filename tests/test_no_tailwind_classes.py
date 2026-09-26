"""Menjaga agar Tailwind tidak kembali dan Bootstrap 5 tetap jadi sistem layout.

Bootstrap 5 dipulihkan sebagai sistem layout/komponen. Uji ini memastikan tidak
ada sisa kelas Tailwind di template internal, Bootstrap 5 dimuat di shell, dan
landing page tetap tak tersentuh.
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

    def test_landing_still_owns_its_own_tailwind(self):
        """Landing page di luar scope: tetap pakai Tailwind miliknya sendiri."""
        html = (TEMPLATES / "landing" / "index.html").read_text(encoding="utf-8")
        self.assertIn("cdn.tailwindcss.com", html)
        self.assertNotIn("{% extends", html)


if __name__ == "__main__":
    unittest.main()
