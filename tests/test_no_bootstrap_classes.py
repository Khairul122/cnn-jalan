"""Menjaga agar kelas Bootstrap tidak tersisa di template internal.

Bootstrap CSS keluar di Task 2. Kelas yang masih tertinggal tidak akan
bergaya, dan grid `row`/`col-*` yang kehilangan makna membuat form kehilangan
tata letak kolomnya tanpa error. Uji ini memindai markup secara statis.
"""

import re
import unittest
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"
FORBIDDEN = [
    "row", "col-1", "col-2", "col-3", "col-4", "col-5", "col-6", "col-7", "col-8", "col-9", "col-10", "col-11", "col-12",
    "col-sm-1", "col-sm-2", "col-sm-3", "col-sm-4", "col-sm-6", "col-md-1", "col-md-2", "col-md-3", "col-md-4", "col-md-6", "col-md-8", "col-lg-2", "col-lg-3", "col-lg-4", "col-lg-6",
    "container", "container-fluid", "g-2", "g-3", "g-4", "card", "card-body", "card-header", "card-title", "card-footer", "form-control", "form-control-sm", "form-label", "form-select", "form-floating", "form-check", "form-check-input", "form-check-label", "form-text", "form-group", "input-group", "invalid-feedback", "valid-feedback", "table-responsive", "table-sm", "table-striped", "table-hover", "table-bordered", "alert", "alert-danger", "alert-warning", "alert-info", "alert-success", "badge", "list-group", "list-group-item", "nav", "navbar", "dropdown-menu", "modal", "spinner-border", "pagination", "offcanvas", "accordion", "tooltip", "btn-close", "visually-hidden",
    "d-flex", "d-block", "d-none", "d-grid", "d-inline-flex", "justify-content-between", "justify-content-end", "justify-content-center", "align-items-center", "align-items-start", "align-self-center", "flex-column", "flex-wrap", "flex-shrink-0", "flex-grow-1", "text-center", "text-end", "text-muted", "text-danger", "text-success", "fw-bold", "fw-normal", "fw-semibold", "fs-5", "fs-6", "mb-0", "mb-1", "mb-2", "mb-3", "mb-4", "me-1", "me-2", "ms-1", "ms-2", "mt-1", "mt-2", "mt-3", "p-0", "p-1", "p-2", "p-3", "w-100", "w-50", "h-100", "min-w-0", "rounded", "rounded-circle", "shadow-sm", "shadow", "border", "border-0", "overflow-hidden", "no-underline", "cursor-pointer", "sticky-top",
]
TARGETS = ["lokasi/index.html", "lokasi/detail.html", "label/index.html", "label/hasil.html", "preprocessing/index.html", "augmentasi/index.html", "split/index.html", "arsitektur/index.html", "peta/index.html"]


def class_tokens(html):
    out = set()
    for match in re.finditer(r'class="([^"}]*)"', html):
        out.update(token.split("{")[0].strip() for token in match.group(1).split() if token)
    return out


class TestNoBootstrapClasses(unittest.TestCase):
    def test_targets_exist(self):
        for rel in TARGETS:
            self.assertTrue((TEMPLATES / rel).exists(), f"{rel} tidak ada")

    def test_no_bootstrap_classes(self):
        for rel in TARGETS:
            found = sorted(class_tokens((TEMPLATES / rel).read_text(encoding="utf-8")) & set(FORBIDDEN))
            self.assertEqual(found, [], f"{rel} masih memakai kelas Bootstrap: {', '.join(found)}")

    def test_bootstrap_responsive_helpers_gone(self):
        for rel in TARGETS:
            html = (TEMPLATES / rel).read_text(encoding="utf-8")
            self.assertIsNone(re.search(r'class="[^"]*\b(?:d-(?:sm|md|lg|xl)-|d-none\s+d-|(?:visible|invisible|float)-(?:sm|md|lg|xl))[^\"]*"', html), rel)

    def test_landing_untouched(self):
        html = (TEMPLATES / "landing" / "index.html").read_text(encoding="utf-8")
        self.assertIn("cdn.tailwindcss.com", html)
        self.assertNotIn("{% extends", html)


if __name__ == "__main__":
    unittest.main()
