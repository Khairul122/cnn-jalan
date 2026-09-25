# Clinical Instrument Redesign — Phase A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the app's three competing CSS systems with one hand-written design system, and eliminate all 831 inline `style` attributes from the 28 internal templates.

**Architecture:** `style.css` is split additively into `tokens.css` (new vocabulary plus a legacy alias layer), `components.css`, and `layout.css`. Bootstrap CSS and the Tailwind Play CDN are removed from `base.html`, which is rewritten around a numbered rail. Work proceeds in five waves; each wave is one commit and leaves the 76-test suite green.

**Tech Stack:** Flask + Jinja2, plain CSS with custom properties, Bootstrap Icons (icon font, retained), Leaflet and Chart.js loaded per-page via `extra_css`/`extra_js` blocks.

**Spec:** `docs/superpowers/specs/2026-09-26-clinical-instrument-redesign-design.md`

---

## Global Constraints

These apply to every task. Copy them verbatim.

- **Test command, run after every wave:**
  `.\.venv\Scripts\python.exe -m unittest discover tests`
  Expect `Ran 76 tests` and `OK`. Exit code 0. The suite takes about 220 seconds; that is normal, not a hang.
- **Never touch** `app/templates/landing/index.html`. It is standalone with its own `<!DOCTYPE html>` and its own six CDN references. It does not extend `base.html`. Verify it is unchanged with `git diff --stat -- app/templates/landing/index.html` returning empty.
- **Never touch** `TODO.md` or the 21 files it marks JANGAN DIUBAH.
- **Never touch** Python: no route, controller, model, service, or config changes.
- **Preserve** every `name=` form field, every `url_for` endpoint, and every `data-*` or element `id` that JavaScript reads. These are contracts, not styling.
- **Load-bearing element IDs** that must survive every wave: `#toast-container`, `.tw-progress-bar`, `#flash-data`, `#sidebar`, `#sidebar-overlay`, `#hamburger-btn`, `#main-content`, `#gcModal`, `#gcHeader`, `#gcIconWrap`, `#gcIcon`, `#gcTitle`, `#gcSubtitle`, `#gcMessage`, `#gcConfirmBtn`, `#map`, `#map-skeleton`, `#map-error`, `#map-error-msg`, `#filterStatus`, `#btnFilter`.
- **Bootstrap Icons stay.** 190 instances, 81 names, loaded from CDN. Icon font only, not a layout system. Do not replace with inline SVG.
- **Dynamic inline styles are values, not styles.** The 52 inline `style` attributes containing Jinja become custom properties, never a moved style declaration. This pattern already exists in the codebase (`--dmg-color`, `--kpi-accent`, `--fc`, `--cm-opacity`, `--qa-bg`).
- **Encoding.** Write every file as UTF-8 without BOM. PowerShell `Set-Content -Encoding utf8` writes a BOM and will corrupt it. Use `[System.IO.File]::WriteAllText($path, $content, (New-Object System.Text.UTF8Encoding($false)))` or the `write` tool.
- **Verify by command, never by eye.** Reading a UTF-8 file with `Get-Content` under Windows PowerShell shows mojibake for `—`, `±`, `≈`, `─`. Use `[System.IO.File]::ReadAllLines($f, [System.Text.Encoding]::UTF8)` before concluding a file is corrupted.

## Review Focus

The 76 tests assert HTTP status codes and Indonesian copy strings. They never assert on a CSS class, an element ID, or a visual property. A wave can therefore pass the whole suite while rendering an unusable page. These are the failure modes most likely to reach a person using this app; each has a test named in its owning task.

1. **JavaScript reading a renamed ID or class.** `toast.js` reads `#toast-container`, `.tw-progress-bar`, `#flash-data`; `peta.js` reads `#map`, `#map-skeleton`, `#map-error`, `#map-error-msg`, `#filterStatus`, `#btnFilter`; the inline confirm-dialog script reads thirteen `#gc*` IDs. Renaming any of them throws a `TypeError` at runtime and the test suite stays green because the tests never execute that JavaScript. Pinned in Task 2.
2. **Contrast failure on inactive navigation text.** `style.css` line 164 dims inactive rail items with `opacity: .72`, which puts `#8A94A0` text on `#12161C` below the 4.5:1 that WCAG AA requires for body text. Every rail label becomes unreadable for low-vision users. Pinned in Task 2.
3. **A severity colour rendering as an undefined custom property.** The four `tingkat_kerusakan.warna_peta` values arrive from the database as Jinja. If a chip or meter references `var(--sev-2)` and the token is missing, the element renders with no background at all and the damage level becomes indistinguishable from blank. Pinned in Task 1.
4. **A `col-*` or `row` grid class losing its meaning when Bootstrap leaves.** 69 distinct Bootstrap classes are in use, mostly `form-control` (34), `form-floating` (21), `btn` (23), `table` (16), `card` (14). If a Wave A3 or A4 page keeps a Bootstrap grid class with no replacement, its form silently loses its column layout. Pinned in Task 4.
5. **Horizontal page scroll at 390px.** Dense tables in `preprocessing/hasil.html` and `arsitektur/detail.html` overflow their container if `.table-wrap` is missing or if a fixed pixel width replaces a fluid one. Unusable one-handed on a phone. Pinned in Task 5.

---

## File Structure

**Created in Phase A:**

| Path | Responsibility |
|---|---|
| `app/static/css/tokens.css` | All custom properties. The new vocabulary plus a legacy alias layer for the 883 existing `var()` uses. Single `:root` block. No selectors. |
| `app/static/css/components.css` | Reusable class rules: panels, KPI, grids, fields, buttons, tables, chips, meters, matrices, dialogs, toasts. No custom property definitions. |
| `app/static/css/layout.css` | App shell only: wrapper, rail, rail items, header, breadcrumb, drawer, overlay, main, skip link, visually-hidden, Leaflet popup. No component styling. |

**Modified in Phase A:**

| Path | Change |
|---|---|
| `app/static/css/style.css` | Emptied to a deprecation stub in Task 1, deleted in Task 5 once nothing references it. |
| `app/templates/base.html` | Shell rewrite, CDN removal, two inline script rewrites. |
| `app/templates/components/*.html` | Ten partials moved to the new vocabulary. |
| 28 internal templates | Inline styles removed, classes mapped. |

**Unchanged and load-bearing:** `app/static/js/toast.js`, `app/static/js/peta.js`, all Python, `app/templates/landing/index.html`.

---

## Task 1: Split `style.css` into three files, additively

`style.css` currently holds 78 class selectors and 34 custom properties. **883 `var()` uses of those properties live across 28 template files** (`--c-muted` 207, `--c-border` 159, `--c-text` 116, `--c-surface` 80, `--r-card` 77, `--r-input` 66, `--c-accent` 51). This task must therefore be **purely additive**: the new vocabulary is introduced alongside the old names, and every old name keeps resolving. Renaming anything here breaks Waves A2 through A5 before they start.

Only `base.html` links `style.css`, so all 78 selectors reach the browser through the 29 templates that extend it. Just 57 of the 78 are actually referenced by internal templates; the remaining 21 are dead. Carry the live ones across during the split, and let Phase B delete the dead ones once the directory-wide checks confirm nothing still needs them.

**Files:**
- Create: `app/static/css/tokens.css`
- Create: `app/static/css/components.css`
- Create: `app/static/css/layout.css`
- Modify: `app/static/css/style.css` (reduced to a stub)
- Modify: `app/templates/base.html` (link the three files instead of `style.css`)

**Interfaces:**
- Consumes: nothing. This is the first task.
- Produces: the custom property names every later task uses.
  - Vocabulary: `--surface-0` `--surface-1` `--surface-2` `--surface-3` `--ink-1` `--ink-2` `--ink-3` `--rule` `--rule-strong` `--accent` `--accent-hover` `--accent-ink` `--accent-wash` `--rail` `--rail-ink` `--rail-ink-dim` `--rail-active` `--ok` `--warn` `--danger` `--info` `--sev-1` `--sev-2` `--sev-3` `--sev-4` and a `-bg` companion for each severity and status token; `--font-ui` `--font-mono`; `--t-xs` `--t-sm` `--t-base` `--t-md` `--t-lg` `--t-xl` `--t-metric`; `--s-1` through `--s-12`; `--gap`; `--r-1` `--r-2`; `--shadow-1` `--shadow-2`; `--dur-1` `--dur-2` `--ease`; `--rail-w`.
  - Legacy alias, still resolving: every `--c-*`, `--r-card`, `--r-input`, `--shadow-card`, `--shadow-hover`, `--shadow-md`, `--shadow-lg`, `--shadow-xl`, `--sidebar-w`, `--ease-spring`, `--duration-fast`, `--duration-normal`, `--duration-slow`, `--focus-ring`, `--sidebar-active-bg`, `--sidebar-hover-bg`.

- [ ] **Step 1: Write the severity-token guard test**

Create `tests/test_design_tokens.py`:

```python
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
# berubah, jadi harus jadi keputusan tersendiri, bukan accidentsi.
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
    """True bila R, G, B saling dekat, jadi warnanya praktis abu-abu."""
    r, g, b = (int(hex_color[i:i + 2], 16) for i in (1, 3, 5))
    return max(r, g, b) - min(r, g, b) <= 12


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run the new test and confirm it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_design_tokens -v`
Expected: 6 tests, all FAIL. `test_tokens_file_exists` reports that `tokens.css` is
absent; the rest fail on the missing hex definitions. A skip here means the test is not
actually guarding anything.

- [ ] **Step 3: Create `tokens.css`**

Write `app/static/css/tokens.css`:

```css
/* Design tokens — the single source of truth for every value in Phase A.
   No selectors live in this file. Nothing outside this file may define a token.
   The severity block mirrors `tingkat_kerusakan.warna_peta` and is pinned by
   tests/test_design_tokens.py. */

:root {
  /* ── Surfaces ─────────────────────────────────────────────────────── */
  --surface-0: #F4F6F8;   /* page background */
  --surface-1: #FFFFFF;   /* panel, card */
  --surface-2: #E8ECF0;   /* panel head, table thead, chip */
  --surface-3: #D3D9E0;   /* hairline, placeholder */

  /* ── Ink ───────────────────────────────────────────────────────────── */
  --ink-1: #12161C;       /* primary text, rail background */
  --ink-2: #5F6B7A;       /* secondary text, labels */
  --ink-3: #8794A3;       /* muted text, placeholder */

  /* ── Rules ─────────────────────────────────────────────────────────── */
  --rule: #D3D9E0;        /* hairline border, 1px */
  --rule-strong: #B7C1CC; /* control border, emphasis border */

  /* ── Accent, the only interactive hue ──────────────────────────────── */
  --accent: #0F4C81;
  --accent-hover: #0B3A66;
  --accent-ink: #FFFFFF;
  --accent-wash: #EAF1F7;

  /* ── Rail ──────────────────────────────────────────────────────────── */
  --rail: #12161C;
  --rail-ink: #E7EBEF;
  --rail-ink-dim: #8A94A0;
  --rail-active: #0F4C81;

  /* ── Status ────────────────────────────────────────────────────────── */
  --ok: #059669;      --ok-bg: #ECFDF5;
  --warn: #D97706;    --warn-bg: #FFFBEB;
  --danger: #DC2626;  --danger-bg: #FEF2F2;
  --info: #0284C7;    --info-bg: #E0F2FE;

  /* ── Severity: sourced from tingkat_kerusakan.warna_peta ───────────── */
  --sev-1: #E53E3E;    --sev-1-bg: #FDECEC;   /* Rusak Berat */
  --sev-2: #F97316;    --sev-2-bg: #FEF0E6;   /* Rusak Ringan */
  --sev-3: #F59E0B;    --sev-3-bg: #FEF6E4;   /* Sedang */
  --sev-4: #10B981;    --sev-4-bg: #E7F8F1;   /* Baik */

  /* ── Type ──────────────────────────────────────────────────────────── */
  --font-ui: system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif;
  --font-mono: ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace;

  --t-xs: 10.5px;      /* uppercase label, letter-spacing .08em */
  --t-sm: 12px;        /* meta, secondary cell, badge */
  --t-base: 13.5px;    /* body, table cell */
  --t-md: 15px;        /* subhead, dialog title */
  --t-lg: 18px;        /* panel title */
  --t-xl: 22px;        /* page title */
  --t-metric: 30px;    /* KPI value */

  /* ── Spacing, multiples of 4 ────────────────────────────────────────── */
  --s-1: 4px;   --s-2: 8px;   --s-3: 12px;  --s-4: 16px;
  --s-5: 20px;  --s-6: 24px;  --s-8: 32px;  --s-10: 40px;
  --s-12: 48px;
  --gap: 12px;

  /* ── Radius ────────────────────────────────────────────────────────── */
  --r-1: 3px;
  --r-2: 5px;

  /* ── Shadow: overlay only. Panels and tables never use these. ───────── */
  --shadow-1: 0 1px 2px rgba(18, 22, 28, .06);   /* dialog, toast, drawer */
  --shadow-2: 0 8px 28px rgba(18, 22, 28, .14);  /* dialog, raised state */

  /* ── Motion ────────────────────────────────────────────────────────── */
  --dur-1: 120ms;
  --dur-2: 180ms;
  --ease: cubic-bezier(.2, 0, .2, 1);

  --rail-w: 240px;

  /* ══ Legacy alias layer ══════════════════════════════════════════════
     883 var() references to these names live across 28 templates. They are
     remapped to the new vocabulary, not restated, so the two vocabularies
     cannot drift apart. Tasks A3, A4 and A5 migrate call sites off these
     names; Task 5 deletes this block once no reference remains. */

  --c-primary: var(--ink-1);
  --c-secondary: var(--rail);
  --c-secondary-light: var(--ink-2);
  --c-accent: var(--accent);
  --c-accent-dark: var(--accent-hover);
  --c-accent-light: var(--accent-wash);
  --c-primary-glow: rgba(18, 22, 28, .18);
  --c-accent-glow: rgba(15, 76, 129, .25);

  --c-ok: var(--ok);         --c-ok-bg: var(--ok-bg);
  --c-warn: var(--warn);     --c-warn-bg: var(--warn-bg);
  --c-danger: var(--danger); --c-danger-bg: var(--danger-bg);
  --c-info: var(--info);     --c-info-bg: var(--info-bg);

  --c-surface: var(--surface-1);
  --c-bg: var(--surface-0);
  --c-border: var(--rule);
  --c-border-sub: var(--surface-2);
  --c-muted: var(--ink-2);
  --c-text: var(--ink-1);
  --c-label: var(--ink-2);

  --r-card: var(--r-1);
  --r-input: var(--r-1);

  --shadow-card: none;
  --shadow-hover: none;
  --shadow-md: var(--shadow-1);
  --shadow-lg: var(--shadow-2);
  --shadow-xl: var(--shadow-2);

  --sidebar-w: var(--rail-w);
  --sidebar-active-bg: var(--rail-active);
  --sidebar-hover-bg: rgba(255, 255, 255, .08);

  --ease-spring: var(--ease);
  --duration-fast: var(--dur-1);
  --duration-normal: var(--dur-2);
  --duration-slow: var(--dur-2);
  --focus-ring: 0 0 0 3px rgba(15, 76, 129, .35);
}
```

Note the two deliberate changes in the alias block: all five panel shadows collapse to `none` except the two overlay ones, and `--ease-spring` becomes the non-bouncy curve. This is where the visual shift begins, and it happens without touching a single template.

- [ ] **Step 4: Create `layout.css`**

Write `app/static/css/layout.css` by moving the shell-level rules out of `style.css`. Copy these sections verbatim from `app/static/css/style.css`, then adjust only the token references and the contrast rule noted:

| From `style.css` lines | Section |
|---|---|
| 86 to 105 | `.skip-link` |
| 107 to 182 | `.sidebar-nav-link`, `.nav-ico`, `.sidebar-section-label` |
| 648 to 674 | `.cnn-breadcrumb` |
| 675 to 700 | `.cnn-avatar`, `.cnn-role-badge` |
| 701 to 710 | focus ring |
| 711 to 713 | Leaflet popup |
| 744 to 751 | responsive block |

Then add the shell primitives that did not exist before, and append this contrast fix to `.sidebar-nav-link`:

```css
/* Shell ─────────────────────────────────────────────────────────────── */

*, *::before, *::after { box-sizing: border-box; }

html { -webkit-text-size-adjust: 100%; }

body {
  margin: 0;
  font-family: var(--font-ui);
  font-size: var(--t-base);
  line-height: 1.5;
  color: var(--ink-1);
  background: var(--surface-0);
  -webkit-font-smoothing: antialiased;
}

a { color: var(--accent); }

/* Bootstrap defined .sr-only. base.html uses it once (the breadcrumb home
   label) and the 38 inline <style> blocks assume it exists. */
.sr-only {
  position: absolute;
  width: 1px; height: 1px;
  padding: 0; margin: -1px;
  overflow: hidden;
  clip: rect(0, 0, 0, 0);
  white-space: nowrap;
  border: 0;
}

/* Wrapper: rail plus main column */
#wrapper {
  display: flex;
  height: 100vh;
  overflow: hidden;
}

/* Rail, permanent at >=1024px, drawer below */
#sidebar {
  width: var(--rail-w);
  min-width: var(--rail-w);
  background: var(--rail);
  color: var(--rail-ink);
  display: flex;
  flex-direction: column;
  z-index: 30;
  flex-shrink: 0;
}

#sidebar-overlay {
  display: none;
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, .5);
  z-index: 20;
}

/* Main column */
.shell__main {
  display: flex;
  flex-direction: column;
  flex: 1;
  min-width: 0;
  overflow: hidden;
}

.shell__header {
  display: flex;
  align-items: center;
  gap: var(--s-3);
  height: 48px;
  padding: 0 var(--s-4);
  background: var(--surface-1);
  border-bottom: 1px solid var(--rule);
  flex-shrink: 0;
}

#hamburger-btn {
  display: none;
  min-width: 44px;
  min-height: 44px;
  background: none;
  border: 0;
  color: var(--ink-2);
  cursor: pointer;
  align-items: center;
  justify-content: center;
}

#main-content {
  flex: 1;
  overflow-y: auto;
  padding: var(--s-4);
  outline: none;
}

@media (min-width: 1024px) {
  #hamburger-btn { display: none; }
  #sidebar-overlay { display: none !important; }
}

@media (max-width: 1023px) {
  #sidebar {
    position: fixed;
    top: 0; left: 0;
    height: 100%;
    transform: translateX(-100%);
    transition: transform var(--dur-2) var(--ease);
  }
  #sidebar.is-open { transform: translateX(0); }
  #sidebar-overlay:not([aria-hidden="true"]) { display: block; }
  #hamburger-btn { display: inline-flex; }
  #main-content { padding: var(--s-3); }
}
```

The critical change inside `.sidebar-nav-link`: the existing rule dims inactive items with `opacity: .72`, which drops `#8A94A0` on `#12161C` to roughly 4.0:1 and fails WCAG AA. Replace the opacity approach with explicit colours so inactive labels are at or above 4.5:1.

- [ ] **Step 5: Create `components.css`**

Write `app/static/css/components.css` by moving these `style.css` sections verbatim, adjusting only token references:

| From `style.css` lines | Section |
|---|---|
| 186 to 261 | `.cnn-kpi-card` and friends |
| 262 to 288 | `.cnn-status-bar-*` |
| 289 to 324 | `.cnn-qa-link` |
| 325 to 351 | `.cnn-table` |
| 352 to 365 | `.cnn-empty-state` |
| 366 to 373 | `.cnn-skeleton` |
| 374 to 568 | `.auth-*`, login and register |
| 569 to 602 | `.btn-auth-primary` |
| 603 to 647 | `.cnn-dropzone-*` |
| 729 to 743 | `.cnn-confidence-*` |
| 719 to 728 | `.table` and `.form-control` focus overrides |

Then append the new vocabulary that Wave A3 onward depends on:

```css
/* Components ────────────────────────────────────────────────────────── */

.panel {
  background: var(--surface-1);
  border: 1px solid var(--rule);
  border-radius: var(--r-1);
}
.panel__head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-2);
  height: 32px;
  padding: 0 var(--s-3);
  background: var(--surface-2);
  border-bottom: 1px solid var(--rule);
  font-size: var(--t-xs);
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.panel__body { padding: var(--s-3); }

.kpi {
  background: var(--surface-1);
  border: 1px solid var(--rule);
  border-left: 2px solid var(--kpi-accent, var(--accent));
  border-radius: var(--r-1);
  padding: var(--s-3);
}
.kpi--lead { background: var(--accent); border-left-color: var(--accent); color: var(--accent-ink); }
.kpi--lead .kpi__label,
.kpi--lead .kpi__unit { color: rgba(255, 255, 255, .82); }
.kpi__label {
  font-size: var(--t-xs);
  font-weight: 500;
  letter-spacing: .09em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.kpi__value {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--t-metric);
  font-weight: 700;
  line-height: 1.1;
  letter-spacing: -.01em;
  margin-top: 3px;
}
.kpi__unit { font-size: var(--t-xs); color: var(--ink-3); }

.grid { display: grid; gap: var(--gap); }
.grid--2 { grid-template-columns: repeat(2, minmax(0, 1fr)); }
.grid--3 { grid-template-columns: repeat(3, minmax(0, 1fr)); }
.grid--4 { grid-template-columns: repeat(4, minmax(0, 1fr)); }
.grid--auto { grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); }
.stack { display: flex; flex-direction: column; gap: var(--gap); }

@media (min-width: 1024px) { .grid--4 { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
@media (max-width: 1023px) { .grid--3, .grid--4 { grid-template-columns: repeat(2, minmax(0, 1fr)); } }
@media (max-width: 639px)  { .grid--2, .grid--3, .grid--4 { grid-template-columns: minmax(0, 1fr); } }

.field { display: flex; flex-direction: column; gap: var(--s-1); }
.field__label {
  font-size: var(--t-xs);
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ink-2);
}
.control {
  height: 30px;
  padding: 0 var(--s-2);
  font-family: var(--font-ui);
  font-size: var(--t-base);
  color: var(--ink-1);
  background: var(--surface-1);
  border: 1px solid var(--rule-strong);
  border-radius: var(--r-1);
}
textarea.control { height: auto; min-height: 72px; padding: var(--s-2); }
select.control { padding-right: var(--s-2); }
.control:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.control[aria-invalid="true"] { border-color: var(--danger); }
.hint { font-size: var(--t-sm); color: var(--ink-3); }
.error-text { font-size: var(--t-sm); color: var(--danger); }

.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  height: 30px;
  padding: 0 var(--s-3);
  font-family: var(--font-ui);
  font-size: var(--t-sm);
  font-weight: 600;
  line-height: 1;
  text-decoration: none;
  white-space: nowrap;
  border: 1px solid transparent;
  border-radius: var(--r-1);
  cursor: pointer;
  transition: background var(--dur-1) var(--ease), border-color var(--dur-1) var(--ease);
}
.btn:focus-visible { outline: 2px solid var(--accent); outline-offset: 1px; }
.btn--primary { background: var(--accent); color: #fff; }
.btn--primary:hover { background: var(--accent-hover); }
.btn--ghost { background: transparent; color: var(--ink-2); border-color: var(--rule-strong); }
.btn--ghost:hover { color: var(--ink-1); border-color: var(--ink-2); }
.btn--danger { background: var(--danger); color: #fff; }
.btn--sm { height: 26px; padding: 0 var(--s-2); font-size: var(--t-xs); }

.table-wrap { overflow-x: auto; max-width: 100%; }
.table { width: 100%; border-collapse: collapse; font-size: var(--t-base); }
.table thead th {
  position: sticky;
  top: 0;
  z-index: 2;
  background: var(--surface-2);
  padding: var(--s-2) var(--s-2);
  text-align: left;
  font-size: var(--t-xs);
  font-weight: 600;
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--ink-2);
  border-bottom: 1px solid var(--ink-1);
  white-space: nowrap;
}
.table td {
  padding: 0 var(--s-2);
  height: 30px;
  border-bottom: 1px solid var(--rule);
  vertical-align: middle;
}
.table__num {
  text-align: right;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.table__key {
  position: sticky;
  left: 0;
  z-index: 1;
  background: var(--surface-1);
  font-weight: 600;
}

.chip {
  display: inline-block;
  padding: 1px 6px;
  font-size: var(--t-xs);
  font-weight: 600;
  line-height: 1.4;
  color: #fff;
  background: var(--chip-color, var(--ink-2));
  border-radius: var(--r-1);
  white-space: nowrap;
}
.chip--sev1 { background: var(--sev-1); } .chip--sev1-bg { background: var(--sev-1-bg); }
.chip--sev2 { background: var(--sev-2); } .chip--sev2-bg { background: var(--sev-2-bg); }
.chip--sev3 { background: var(--sev-3); } .chip--sev3-bg { background: var(--sev-3-bg); }
.chip--sev4 { background: var(--sev-4); } .chip--sev4-bg { background: var(--sev-4-bg); }
.chip--ok { background: var(--ok); }         .chip--ok-bg { background: var(--ok-bg); }
.chip--warn { background: var(--warn); }     .chip--warn-bg { background: var(--warn-bg); }
.chip--danger { background: var(--danger); } .chip--danger-bg { background: var(--danger-bg); }
.chip--info { background: var(--info); }     .chip--info-bg { background: var(--info-bg); }
.chip--muted { background: var(--surface-2); color: var(--ink-2); }

.meter {
  display: flex;
  height: 8px;
  border-radius: 999px;
  overflow: hidden;
  background: var(--surface-2);
}
.meter > span { display: block; height: 100%; }

.dl { display: flex; flex-direction: column; margin: 0; }
.dl__row {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: var(--s-2);
  padding: var(--s-1) 0;
  border-bottom: 1px solid var(--rule);
}
.dl__k { font-size: var(--t-sm); color: var(--ink-2); }
.dl__v {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--t-base);
  font-weight: 600;
  min-width: 0;
  overflow-wrap: anywhere;
}

/* Confusion matrix and similar dense numeric grids */
.matrix { border-collapse: collapse; font-size: var(--t-sm); }
.matrix th, .matrix td {
  border: 1px solid var(--rule);
  padding: var(--s-1) var(--s-2);
  text-align: right;
}
.matrix thead th {
  background: var(--surface-2);
  font-size: var(--t-xs);
  font-weight: 600;
  letter-spacing: .06em;
  text-transform: uppercase;
  color: var(--ink-2);
  white-space: nowrap;
}
.matrix__row-label,
.matrix__corner {
  position: sticky;
  left: 0;
  background: var(--surface-1);
  text-align: left;
  font-weight: 600;
  white-space: nowrap;
}
.matrix thead .matrix__corner { background: var(--surface-2); }
.matrix__cell {
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
}
.matrix__cell--hi { background: var(--accent-wash); font-weight: 700; }
.matrix__cell--low { color: var(--ink-3); }

.toast {
  background: var(--surface-1);
  border: 1px solid var(--rule);
  border-left: 2px solid var(--toast-accent, var(--accent));
  border-radius: var(--r-1);
  box-shadow: var(--shadow-1);
  padding: var(--s-2) var(--s-3);
}
.toast--ok     { --toast-accent: var(--ok); }
.toast--warn   { --toast-accent: var(--warn); }
.toast--danger { --toast-accent: var(--danger); }
.toast--info   { --toast-accent: var(--info); }

#toast-container {
  position: fixed;
  top: var(--s-4);
  right: var(--s-4);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  gap: var(--s-2);
  width: 320px;
  max-width: calc(100vw - 2rem);
}

/* Confirm dialog. Type colours are driven by [data-type] on the dialog, not
   by inline styles set from JavaScript, so tokens.css stays authoritative. */
#gcModal {
  display: none;
  position: fixed;
  inset: 0;
  z-index: 99999;
  background: rgba(0, 0, 0, .65);
  align-items: center;
  justify-content: center;
  padding: var(--s-4);
}
#gcModal.is-open { display: flex; }
#gcModal .dialog {
  background: var(--surface-1);
  border: 1px solid var(--rule);
  border-radius: var(--r-1);
  width: 100%;
  max-width: 420px;
  box-shadow: var(--shadow-2);
  overflow: hidden;
  --gc-accent: var(--danger);
  --gc-wash: var(--danger-bg);
}
#gcModal[data-type="warning"] .dialog { --gc-accent: var(--warn); --gc-wash: var(--warn-bg); }
#gcModal[data-type="info"]    .dialog { --gc-accent: var(--info); --gc-wash: var(--info-bg); }
#gcModal[data-type="success"] .dialog { --gc-accent: var(--ok);   --gc-wash: var(--ok-bg); }
#gcHeader {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  padding: var(--s-3) var(--s-4);
  background: var(--gc-wash);
  border-bottom: 1px solid var(--rule);
}
#gcIconWrap {
  width: 34px; height: 34px;
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 50%;
  background: var(--surface-1);
  border: 1px solid var(--rule);
  color: var(--gc-accent);
}
#gcTitle { font-size: var(--t-md); font-weight: 700; margin: 0; }
#gcSubtitle { font-size: var(--t-xs); color: var(--ink-2); margin: 0; }
#gcModal .dialog__body { padding: var(--s-4); }
#gcMessage { font-size: var(--t-base); margin: 0; line-height: 1.6; }
#gcModal .dialog__foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--s-2);
  padding: var(--s-2) var(--s-4);
  border-top: 1px solid var(--rule);
  background: var(--surface-0);
}

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: .01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: .01ms !important;
  }
}
```

- [ ] **Step 6: Reduce `style.css` to a deprecation stub**

Replace the entire contents of `app/static/css/style.css` with:

```css
/* Deprecated. Split into tokens.css, components.css and layout.css in
   commit "refactor(css): split style.css into three files". Nothing links
   this file any more; it remains only until Task 5 confirms no template
   references it, at which point it is deleted. */
```

- [ ] **Step 7: Point `base.html` at the three new files**

In `app/templates/base.html`, replace the single `style.css` link (line 35):

```html
  <link rel="stylesheet" href="{{ url_for('static', filename='css/style.css') }}">
```

with:

```html
  <link rel="stylesheet" href="{{ url_for('static', filename='css/tokens.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/components.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/layout.css') }}">
```

Do not touch the six CDN references yet. Bootstrap and Tailwind removal is Task 2, and doing both at once makes a broken page impossible to diagnose.

- [ ] **Step 8: Run the severity test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_design_tokens -v`
Expected: PASS, 6 tests.

- [ ] **Step 9: Cross-check the CSS tokens against the real database**

The unit test pins the hex values as a contract. This step confirms the contract still
matches production data. It reads the real MySQL database and writes nothing, so it does
not go through `isolated_app`.

```powershell
.\.venv\Scripts\python.exe -c @"
from app import create_app, db
from app.models import TingkatKerusakan
import re, pathlib

app = create_app()
with app.app_context():
    rows = db.session.execute(
        db.text('SELECT nama_tingkat, warna_peta FROM tingkat_kerusakan ORDER BY id')
    ).fetchall()

css = pathlib.Path('app/static/css/tokens.css').read_text(encoding='utf-8')

print(f'{len(rows)} tingkat ditemukan di database')
bad = 0
for idx, (nama, warna) in enumerate(rows, start=1):
    m = re.search(rf'--sev-{idx}\s*:\s*(#[0-9A-Fa-f]{{6}})', css)
    css_hex = m.group(1).upper() if m else '(tidak ada)'
    db_hex = (warna or '').upper()
    flag = 'OK ' if css_hex == db_hex else 'SELISIH'
    if css_hex != db_hex:
        bad += 1
    print(f'  {flag} --sev-{idx}  CSS {css_hex:9}  DB {db_hex:9}  {nama}')

print('COCOK' if bad == 0 else f'{bad} token tidak cocok dengan database')
"@
```

Expected: four rows, each `OK`, ending in `COCOK`.

If a row reports `SELISIH`, the database is the source of truth, because the map legend
already ships these colours. Update the hex in `tokens.css` **and** `EXPECTED` in
`tests/test_design_tokens.py` to the same value, rerun Step 8, and state the change in
the commit message. If the database has more or fewer than four levels, stop and raise
it: the four-colour severity scale in the design spec assumes exactly four.

- [ ] **Step 10: Run the full suite**

Run: `.\.venv\Scripts\python.exe -m unittest discover tests`
Expected: `Ran 76 tests`, `OK`, exit code 0.

- [ ] **Step 11: Confirm the new files resolve and the old one is empty**

```powershell
$ErrorActionPreference='Stop'
foreach($f in @('tokens','components','layout')){
  $p = "app\static\css\$f.css"
  "{0,-34} {1,7} bytes" -f $p, (Get-Item $p).Length
}
"style.css now {0} bytes (stub)" -f (Get-Item app\static\css\style.css).Length
$all = ([System.IO.File]::ReadAllText('app\static\css\tokens.css') +
        [System.IO.File]::ReadAllText('app\static\css\components.css') +
        [System.IO.File]::ReadAllText('app\static\css\layout.css'))
$missing = @()
foreach($t in @('--c-muted','--c-border','--c-text','--c-surface','--r-card','--r-input','--c-accent','--c-bg','--shadow-card','--c-danger','--c-ok','--c-warn','--c-info','--c-label','--c-border-sub','--sidebar-w','--focus-ring','--ease-spring','--duration-fast','--duration-normal','--duration-slow')){
  if($all -notmatch [regex]::Escape("$t`:")){ $missing += $t }
}
if($missing.Count -eq 0){ "all 21 legacy alias tokens present" } else { "MISSING: $($missing -join ', ')" }
```

Expected: three non-empty files, `style.css` under 200 bytes, and the line `all 21 legacy alias tokens present`. Any token reported missing will break a template silently, because the tests never read CSS.

- [ ] **Step 12: Commit**

```powershell
git add app/static/css/tokens.css app/static/css/components.css app/static/css/layout.css app/static/css/style.css app/templates/base.html tests/test_design_tokens.py
git commit -m "refactor(css): split style.css into tokens, components and layout

Introduce the Clinical Instrument vocabulary alongside the existing --c-*
names rather than renaming, because 883 var() references to those names live
across 28 templates and all resolve through the new alias block.

Panel shadows collapse to none; only dialog, toast and drawer keep a shadow.
--ease-spring loses its overshoot in favour of the standard curve.

Adds tests/test_design_tokens.py, six checks that pin the four severity tokens
to the hex values stored in tingkat_kerusakan.warna_peta and reject any new
chromatic colour in :root. The test reads CSS only, so it neither needs a
database nor touches production data; Step 9 cross-checks it against MySQL
once, by hand."
```

---

## Task 2: Rewrite the shell in `base.html`

The shell is inherited by 28 templates, so this wave changes all of them at once. It must be proven on its own before the per-page waves.

**Files:**
- Modify: `app/templates/base.html`
- Modify: `app/templates/components/page_header.html`
- Modify: `app/templates/components/status_badge.html`
- Modify: `app/templates/components/detail_row.html`
- Modify: `app/templates/components/empty_table_row.html`
- Modify: `app/templates/components/table_actions.html`
- Modify: `app/templates/components/kpi_card.html`
- Modify: `app/templates/components/quick_action.html`
- Modify: `app/templates/components/cv_summary.html`
- Modify: `app/templates/components/auth_card_header.html`
- Modify: `app/templates/components/auth_footer.html`
- Test: `tests/test_design_tokens.py` (extend)

**Interfaces:**
- Consumes: every token and `.panel`/`.kpi`/`.chip`/`.dl`/`.table`/`.btn`/`.control` rule from Task 1. The DOM contract `#sidebar.is-open` replaces Tailwind's `-translate-x-full`, and `#gcModal[data-type]` plus `.is-open` replace the JavaScript-set inline colours.
- Produces: nine rewritten partials. Wave A3 onward reuses their variable conventions unchanged: `ph_title` `ph_subtitle` `ph_back_url`; `badge_value`; `dr_label` `dr_value` `dr_raw`; `et_colspan`; `ta_view_url` `ta_delete_url` `ta_confirm_msg`; `kpi_title` `kpi_value` `kpi_accent` `kpi_icon_bg` `kpi_icon_color` `kpi_icon_path` `kpi_trend_label` `kpi_trend_type`; `qa_url` `qa_label` `qa_bg` `qa_color` `qa_icon_path`; `cv`; `ach_title` `ach_subtitle` `ach_icon_path` `ach_icon_fill` `ach_icon_stroke`. No caller may need editing.

- [ ] **Step 1: Add the shell-contract test**

Append to `tests/test_design_tokens.py`:

```python
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

    def test_bootstrap_css_is_gone(self):
        html = self.TEMPLATE.read_text(encoding="utf-8")
        self.assertNotIn("bootstrap@5.3.3/dist/css", html, "Bootstrap CSS masih dimuat")
        self.assertNotIn(
            "bootstrap.bundle.min.js", html, "Bootstrap JS masih dimuat dan tidak pernah dipanggil"
        )

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
```

- [ ] **Step 2: Run the shell test and confirm it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_design_tokens.TestShellContract -v`
Expected: FAIL on `test_tailwind_is_gone`.

- [ ] **Step 3: Rewrite the `<head>` of `base.html`**

Replace lines 1 to 38, from `<!DOCTYPE html>` through the closing `</head>`, with:

```html
<!DOCTYPE html>
<html lang="id">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <meta name="theme-color" content="#12161C">
  <title>{% block title %}GIS Kerusakan Jalan{% endblock %} | CNN Lhokseumawe</title>

  <link rel="stylesheet" href="{{ url_for('static', filename='css/tokens.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/components.css') }}">
  <link rel="stylesheet" href="{{ url_for('static', filename='css/layout.css') }}">

  <!-- Bootstrap Icons: icon font only, deliberately retained. Not a layout
       system, so it does not compete with the design system. -->
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.11.3/font/bootstrap-icons.min.css">

  {% block extra_css %}{% endblock %}
</head>
<body>
```

The Tailwind script, its config block, all three Google Fonts lines, and the Bootstrap CSS link are gone. The `style.css` link from Task 1 is already replaced, so do not re-add it.

- [ ] **Step 4: Replace the toast container and shell markup**

Replace lines 41 to 106, from the skip link through the closing `</nav>` of the main navigation, with:

```html
<a href="#main-content" class="skip-link">Lewati navigasi</a>

<div id="toast-container" aria-live="polite" aria-atomic="false"></div>

{% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}
<script id="flash-data" type="application/json">{{ messages | tojson }}</script>
{% endif %}{% endwith %}

{% if current_user.is_authenticated %}

{# Rail item. The number is positional, matching the 01-07 order of the
   pipeline: dashboard, lokasi, label, preprocessing, augmentasi, split,
   arsitektur, peta. #}
{% macro nav_link(href, label, active, num, icon_class) %}
<a href="{{ href }}" class="sidebar-nav-link{{ ' is-active' if active else '' }}"
   {% if active %}aria-current="page"{% endif %}>
  <span class="rail__num" aria-hidden="true">{{ num }}</span>
  <span class="nav-ico" aria-hidden="true"><i class="{{ icon_class }}"></i></span>
  <span class="sidebar-nav-link__label">{{ label }}</span>
</a>
{% endmacro %}

<div id="wrapper">

  <div id="sidebar-overlay" onclick="closeSidebar()" aria-hidden="true"></div>

  <aside id="sidebar" aria-label="Navigasi utama">
    <div class="rail__brand">
      <img src="{{ url_for('static', filename='logo/logo.png') }}"
           alt="Logo" class="rail__logo">
      <button onclick="closeSidebar()" class="rail__close" aria-label="Tutup menu">
        <i class="bi bi-x" aria-hidden="true"></i>
      </button>
    </div>

    <nav class="rail__nav" aria-label="Menu">
      {{ nav_link(url_for('dashboard.index'),      'Dashboard',      request.endpoint == 'dashboard.index', '01', 'bi bi-house-door-fill') }}
      {{ nav_link(url_for('lokasi.index'),         'Lokasi',         request.blueprint == 'lokasi',         '02', 'bi bi-geo-alt-fill') }}
      {{ nav_link(url_for('label.index'),          'Labeling Visual', request.blueprint == 'label',         '03', 'bi bi-tags-fill') }}
      {{ nav_link(url_for('preprocessing.index'),  'Preprocessing',  request.blueprint == 'preprocessing', '04', 'bi bi-sliders') }}
      {{ nav_link(url_for('augmentasi.index'),     'Augmentasi',     request.blueprint == 'augmentasi',    '05', 'bi bi-shuffle') }}
      {{ nav_link(url_for('split.index'),          'Split Data',     request.blueprint == 'split',         '06', 'bi bi-diagram-3-fill') }}
      {{ nav_link(url_for('arsitektur.index'),     'Arsitektur CNN', request.blueprint == 'arsitektur',    '07', 'bi bi-cpu-fill') }}
      {{ nav_link(url_for('peta.index'),           'Peta GIS',       request.blueprint == 'peta',          '08', 'bi bi-map-fill') }}
    </nav>
```

The original had eight nav items, not seven. The spec said `01` to `07`; numbering all eight is correct and avoids a gap.

- [ ] **Step 5: Replace the user footer, topbar, and main opening**

Replace lines 108 to 190, from the user-footer comment through the `{% endif %}` that closes the authenticated-branch check, with:

```html
    <div class="rail__user">
      <div class="rail__avatar" aria-hidden="true">
        {{ current_user.nama[:2].upper() if current_user.nama|length >= 2 else current_user.nama[0].upper() }}
      </div>
      <div class="rail__user-text">
        <p class="rail__user-name">{{ current_user.nama }}</p>
        <p class="rail__user-role">{{ current_user.role }}</p>
      </div>
      <form method="POST" action="{{ url_for('auth.logout') }}" class="rail__logout-form">
        <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
        <button type="submit" class="rail__logout" aria-label="Logout" title="Logout">
          <i class="bi bi-box-arrow-right" aria-hidden="true"></i>
        </button>
      </form>
    </div>

  </aside>

  <div class="shell__main">

    <header class="shell__header">
      <button onclick="toggleSidebar()" id="hamburger-btn"
              aria-label="Buka menu" aria-expanded="false" aria-controls="sidebar">
        <i class="bi bi-list" aria-hidden="true"></i>
      </button>

      <nav class="cnn-breadcrumb" aria-label="Alur navigasi">
        <a href="{{ url_for('dashboard.index') }}" title="Dashboard">
          <i class="bi bi-house-door" aria-hidden="true"></i>
          <span class="sr-only">Dashboard</span>
        </a>
        {% block breadcrumb %}{% endblock %}
      </nav>

      <div class="shell__header-right">
        <span class="cnn-role-badge" aria-label="Role: {{ current_user.role }}">{{ current_user.role }}</span>
        <form method="POST" action="{{ url_for('auth.logout') }}" class="rail__logout-form">
          <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
          <button type="submit" class="shell__logout" aria-label="Logout dari aplikasi">
            <i class="bi bi-box-arrow-right" aria-hidden="true"></i>
            <span>Logout</span>
          </button>
        </form>
      </div>
    </header>

    <main id="main-content" role="main" tabindex="-1">

{% else %}
<div class="auth-page">
{% endif %}

{% block content %}{% endblock %}

{% if current_user.is_authenticated %}
    </main>
  </div>
</div>
{% else %}
</div>
{% endif %}
```

- [ ] **Step 6: Replace the confirm dialog markup**

Replace lines 206 to 259, the whole `#gcModal` block, with:

```html
<div id="gcModal" role="dialog" aria-modal="true" aria-labelledby="gcTitle"
     data-type="danger" onclick="if(event.target===this)_gcClose()">
  <div class="dialog">
    <div id="gcHeader">
      <span id="gcIconWrap" aria-hidden="true">
        <i id="gcIcon" class="bi bi-exclamation-triangle-fill"></i>
      </span>
      <div>
        <p id="gcTitle">Konfirmasi</p>
        <p id="gcSubtitle">Tindakan ini memerlukan konfirmasi</p>
      </div>
    </div>

    <div class="dialog__body">
      <p id="gcMessage"></p>
    </div>

    <div class="dialog__foot">
      <button type="button" onclick="_gcClose()" class="btn btn--ghost">Batal</button>
      <button id="gcConfirmBtn" type="button" class="btn btn--primary"></button>
    </div>
  </div>
</div>
```

- [ ] **Step 7: Rewrite the confirm-dialog script**

Replace the first inline `<script>` block, lines 261 to 342, with:

```html
<script>
(function () {
  var _gcCallback = null;

  /* Colour now comes from CSS via #gcModal[data-type]; this table holds only
     the icon name. Tokens live in tokens.css and nowhere else. */
  var ICONS = {
    danger:  'bi-exclamation-triangle-fill',
    warning: 'bi-exclamation-circle-fill',
    info:    'bi-info-circle-fill',
    success: 'bi-play-circle-fill'
  };
  var CONFIRM_ICONS = {
    danger:  'bi-trash-fill',
    warning: 'bi-exclamation-triangle-fill',
    info:    'bi-check-lg',
    success: 'bi-play-fill'
  };

  function _gcModal() { return document.getElementById('gcModal'); }

  window.showConfirm = function (opts) {
    var type        = opts.type || 'danger';
    var modal       = _gcModal();

    modal.dataset.type = type;

    document.getElementById('gcTitle').textContent    = opts.title || 'Konfirmasi';
    document.getElementById('gcSubtitle').textContent = opts.subtitle || 'Tindakan ini memerlukan konfirmasi';
    document.getElementById('gcMessage').innerHTML    = opts.message || 'Lanjutkan?';

    var icon = document.getElementById('gcIcon');
    icon.className = 'bi ' + (ICONS[type] || ICONS.danger);

    var btn = document.getElementById('gcConfirmBtn');
    btn.textContent = '';
    var iEl = document.createElement('i');
    iEl.className = 'bi ' + (opts.confirmIcon || CONFIRM_ICONS[type] || CONFIRM_ICONS.danger);
    iEl.setAttribute('aria-hidden', 'true');
    btn.appendChild(iEl);
    btn.appendChild(document.createTextNode(' ' + (opts.confirmText || 'Ya, Lanjutkan')));
    btn.className = 'btn ' + (type === 'danger' ? 'btn--danger' : 'btn--primary');

    _gcCallback = opts.onConfirm || null;

    modal.classList.add('is-open');
    document.body.style.overflow = 'hidden';
    setTimeout(function () { document.getElementById('gcConfirmBtn').focus(); }, 80);
  };

  window.showConfirmForm = function (btn, title, message, type, confirmText, subtitle) {
    var form = btn.closest('form');
    showConfirm({
      type: type || 'danger',
      title: title,
      subtitle: subtitle || 'Tindakan ini tidak dapat dibatalkan',
      message: message,
      confirmText: confirmText || 'Ya, Lanjutkan',
      onConfirm: function () { form.submit(); }
    });
  };

  window._gcClose = function () {
    _gcModal().classList.remove('is-open');
    document.body.style.overflow = '';
    _gcCallback = null;
  };

  document.getElementById('gcConfirmBtn').addEventListener('click', function () {
    var cb = _gcCallback;
    _gcClose();
    if (cb) cb();
  });

  document.addEventListener('keydown', function (e) {
    if (!_gcModal().classList.contains('is-open')) return;
    if (e.key === 'Escape') _gcClose();
    if (e.key === 'Enter')  { var cb = _gcCallback; _gcClose(); if (cb) cb(); }
  });
})();
</script>
```

- [ ] **Step 8: Rewrite the sidebar toggle script**

Replace the second inline `<script>` block, lines 343 to 368, with:

```html
<script>
/* The rail is a permanent column at >=1024px and an off-canvas drawer below.
   .is-open replaces Tailwind's -translate-x-full; the CSS transition lives in
   layout.css. Leaflet maps must be told to re-measure when this runs. */
function toggleSidebar() {
  var s = document.getElementById('sidebar');
  if (s.classList.contains('is-open')) {
    closeSidebar();
  } else {
    s.classList.add('is-open');
    document.getElementById('sidebar-overlay').setAttribute('aria-hidden', 'false');
    document.body.style.overflow = 'hidden';
    document.getElementById('hamburger-btn').setAttribute('aria-expanded', 'true');
    window.dispatchEvent(new Event('resize'));
  }
}

function closeSidebar() {
  var s = document.getElementById('sidebar');
  s.classList.remove('is-open');
  document.getElementById('sidebar-overlay').setAttribute('aria-hidden', 'true');
  document.body.style.overflow = '';
  document.getElementById('hamburger-btn').setAttribute('aria-expanded', 'false');
  window.dispatchEvent(new Event('resize'));
}

document.addEventListener('keydown', function (e) {
  if (e.key === 'Escape' &&
      document.getElementById('sidebar').classList.contains('is-open')) {
    closeSidebar();
  }
});
</script>
```

The `window.dispatchEvent(new Event('resize'))` is required: `peta.js` and the GIS pages listen for resize to call Leaflet's `invalidateSize()`, and a CSS transform does not fire it on its own.

- [ ] **Step 9: Add the rail and header rules to `layout.css`**

Append:

```css
/* Rail internals */
.rail__brand {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-2);
  padding: var(--s-3) var(--s-4);
  border-bottom: 1px solid rgba(255, 255, 255, .06);
}
.rail__logo { height: 44px; width: auto; max-width: 100%; object-fit: contain; }
.rail__close {
  display: none;
  min-width: 32px; min-height: 32px;
  align-items: center; justify-content: center;
  background: none; border: 0;
  color: var(--rail-ink-dim);
  cursor: pointer;
}
.rail__nav {
  flex: 1;
  overflow-y: auto;
  padding: var(--s-2);
}
.rail__num {
  font-family: var(--font-mono);
  font-size: var(--t-xs);
  color: var(--rail-ink-dim);
  flex-shrink: 0;
  width: 20px;
}
.rail__user {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  padding: var(--s-2) var(--s-3);
  border-top: 1px solid rgba(255, 255, 255, .06);
}
.rail__avatar {
  width: 30px; height: 30px;
  flex-shrink: 0;
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  font-weight: 700;
}
.rail__user-text { min-width: 0; flex: 1; }
.rail__user-name {
  margin: 0;
  font-size: var(--t-sm);
  font-weight: 600;
  color: var(--rail-ink);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.rail__user-role {
  margin: 0;
  font-size: 10px;
  color: var(--rail-ink-dim);
  text-transform: uppercase;
  letter-spacing: .04em;
}
.rail__logout-form { margin: 0; display: contents; }
.rail__logout {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 30px; height: 30px;
  flex-shrink: 0;
  background: none; border: 0;
  color: var(--rail-ink-dim);
  cursor: pointer;
  transition: color var(--dur-1) var(--ease);
}
.rail__logout:hover { color: var(--danger); }
.rail__logout:focus-visible { outline: 2px solid var(--rail-ink); outline-offset: 2px; }

.sidebar-nav-link { color: var(--rail-ink); }
.sidebar-nav-link:hover { color: var(--rail-ink); background: var(--sidebar-hover-bg); }
.sidebar-nav-link.is-active { background: var(--rail-active); color: #fff; }
.sidebar-nav-link.is-active .rail__num { color: rgba(255, 255, 255, .8); }
.sidebar-nav-link:focus-visible { outline: 2px solid var(--rail-ink); outline-offset: -2px; }

.shell__header-right {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  margin-left: auto;
  flex-shrink: 0;
}
.shell__logout {
  display: inline-flex;
  align-items: center;
  gap: var(--s-1);
  min-height: 30px;
  background: none; border: 0;
  color: var(--danger);
  font-size: var(--t-sm);
  font-weight: 600;
  cursor: pointer;
}
.shell__logout:hover { color: #B91C1C; }
.shell__logout:focus-visible { outline: 2px solid var(--danger); outline-offset: 2px; }

@media (max-width: 1023px) {
  .rail__close { display: flex; }
}
@media (max-width: 639px) {
  .shell__logout span { display: none; }
  .cnn-role-badge { display: none; }
}
```

The `.sidebar-nav-link` rules replace the `opacity: .72` approach with explicit colours. `--rail-ink-dim` `#8A94A0` on `--rail` `#12161C` measures about 5.9:1, which passes AA for body text; the previous opacity treatment measured about 4.0:1 and failed.

- [ ] **Step 10: Rewrite the nine partials**

Replace each file's contents. Keep every variable name and the `{# ... #}` comment that documents the contract.

`app/templates/components/page_header.html`:

```html
{# Page title block. Variables: ph_title, ph_subtitle (optional), ph_back_url (optional). #}
<div class="page-header">
  {% if ph_back_url is defined and ph_back_url %}
  <a href="{{ ph_back_url }}" class="btn btn--ghost btn--sm page-header__back" aria-label="Kembali">
    <i class="bi bi-arrow-left" aria-hidden="true"></i>
  </a>
  {% endif %}
  <div class="page-header__text">
    <h1 class="page-header__title">{{ ph_title }}</h1>
    {% if ph_subtitle is defined and ph_subtitle %}
    <p class="page-header__subtitle">{{ ph_subtitle }}</p>
    {% endif %}
  </div>
</div>
```

`app/templates/components/status_badge.html`:

```html
{# Status pill. Variable: badge_value. Maps to .chip, not Bootstrap .badge,
   because Bootstrap leaves in this wave. #}
{% set _tone = {
  'primer':        'info',
  'sekunder':      'muted',
  'draft':         'muted',
  'terverifikasi': 'ok',
  'diperbaiki':    'info',
  'berat':         'danger',
  'sedang':        'warn',
  'ringan':        'ok'
} %}
<span class="chip chip--{{ _tone[badge_value | lower] | default('muted') }}">{{ badge_value }}</span>
```

`app/templates/components/detail_row.html`:

```html
{# One label/value pair. Variables: dr_label, dr_value, dr_raw (optional). #}
<div class="dl__row">
  <span class="dl__k">{{ dr_label }}</span>
  {% if dr_raw is defined and dr_raw %}
  <span class="dl__v">{{ dr_value | safe }}</span>
  {% else %}
  <span class="dl__v">{{ dr_value }}</span>
  {% endif %}
</div>
```

`app/templates/components/empty_table_row.html`:

```html
{# Empty-state row. Variable: et_colspan. #}
<tr>
  <td colspan="{{ et_colspan }}">
    <div class="cnn-empty-state" role="status">
      <i class="bi bi-inbox" aria-hidden="true"></i>
      <p>Belum ada data yang tersedia.</p>
    </div>
  </td>
</tr>
```

`app/templates/components/table_actions.html`:

```html
{# Row actions. Variables: ta_view_url (optional), ta_delete_url, ta_confirm_msg (optional). #}
<div class="table-actions">
  {% if ta_view_url is defined and ta_view_url %}
  <a href="{{ ta_view_url }}" class="btn btn--ghost btn--sm" aria-label="Lihat detail">
    <i class="bi bi-eye" aria-hidden="true"></i>
  </a>
  {% endif %}
  <form method="POST" action="{{ ta_delete_url }}">
    <input type="hidden" name="csrf_token" value="{{ csrf_token() }}">
    <button type="button" class="btn btn--ghost btn--sm btn--danger-ghost" aria-label="Hapus data ini"
            onclick="showConfirmForm(this,'Hapus Data','{{ (ta_confirm_msg if ta_confirm_msg is defined and ta_confirm_msg else 'Hapus data ini?') }}','danger','Ya, Hapus')">
      <i class="bi bi-trash" aria-hidden="true"></i>
    </button>
  </form>
</div>
```

`app/templates/components/kpi_card.html`:

```html
{# KPI tile. Variables: kpi_title, kpi_value, kpi_accent (optional),
   kpi_icon_bg, kpi_icon_color, kpi_icon_path, kpi_trend_label (optional),
   kpi_trend_type (optional: up | down | neutral).
   Dynamic values arrive as custom properties, never as inline style
   declarations, so tokens.css stays authoritative. #}
<div class="kpi" style="--kpi-accent:{{ kpi_accent if kpi_accent is defined else 'var(--accent)' }}">
  <div class="kpi__text">
    <p class="kpi__label">{{ kpi_title }}</p>
    <p class="kpi__value">{{ kpi_value }}</p>
    {% if kpi_trend_label is defined %}
    <span class="cnn-kpi-trend cnn-kpi-trend--{{ kpi_trend_type if kpi_trend_type is defined else 'neutral' }}">
      {% if kpi_trend_type == 'up' %}<i class="bi bi-arrow-up" aria-hidden="true"></i>
      {% elif kpi_trend_type == 'down' %}<i class="bi bi-arrow-down" aria-hidden="true"></i>
      {% else %}<i class="bi bi-dash" aria-hidden="true"></i>{% endif %}
      {{ kpi_trend_label }}
    </span>
    {% endif %}
  </div>
  <div class="kpi__icon" style="--kpi-icon-bg:{{ kpi_icon_bg }};--kpi-icon-color:{{ kpi_icon_color }}" aria-hidden="true">
    <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">{{ kpi_icon_path | safe }}</svg>
  </div>
</div>
```

`app/templates/components/quick_action.html`:

```html
{# Quick-action tile. Variables: qa_url, qa_label, qa_bg, qa_color, qa_icon_path.
   Hover is handled entirely in CSS via --qa-bg and --qa-color; the original
   used onmouseover to rewrite inline styles on every mouse event. #}
<a href="{{ qa_url }}" class="qa-tile" style="--qa-bg:{{ qa_bg }};--qa-color:{{ qa_color }}">
  <svg class="qa-tile__ico" viewBox="0 0 24 24" fill="none" stroke="currentColor" aria-hidden="true">{{ qa_icon_path | safe }}</svg>
  <span class="qa-tile__label">{{ qa_label }}</span>
</a>
```

`app/templates/components/cv_summary.html`:

```html
{# Ringkasan K-Fold CV. Butuh variabel: cv (dict dari metrics_service.cv_summary)
   dan KELAS. Colour arrives as a custom property, not as an inline style. #}
{% if cv %}
<section class="panel cv-summary">
  <div class="panel__head">
    <span>Hasil {{ cv.per_fold | length }}-Fold Cross Validation</span>
    <span class="panel__head-note">{{ cv.n }} foto, tiap foto diprediksi model yang tidak melihatnya saat training</span>
  </div>
  <div class="panel__body">
    <div class="grid grid--4">
      {% for label, value, color in [
          ('Akurasi (rata-rata ± std)', cv.akurasi ~ '% ± ' ~ cv.std, 'var(--sev-4)'),
          ('Macro-F1', cv.macro_f1 ~ '%', 'var(--accent)'),
          ('Baseline kelas mayoritas', cv.baseline ~ '%', 'var(--ink-2)'),
          ('Selisih dari baseline', ('+' if cv.selisih_baseline >= 0 else '') ~ cv.selisih_baseline ~ ' poin', 'var(--sev-3)')
      ] %}
      <div class="cv-summary__stat">
        <p class="cv-summary__value" style="--stat-color:{{ color }}">{{ value }}</p>
        <p class="cv-summary__label">{{ label }}</p>
      </div>
      {% endfor %}
    </div>

    <div class="table-wrap">
      <table class="table table--dense">
        <thead>
          <tr>
            <th scope="col">Kelas</th>
            <th scope="col" class="table__num">Precision</th>
            <th scope="col" class="table__num">Recall</th>
            <th scope="col" class="table__num">F1</th>
          </tr>
        </thead>
        <tbody>
          {% for k in KELAS %}
          <tr>
            <td><span class="chip" style="--chip-color:{{ k.warna }}">{{ k.nama }}</span></td>
            <td class="table__num">{{ cv.precision[k.key] }}%</td>
            <td class="table__num">{{ cv.recall[k.key] }}%</td>
            <td class="table__num">{{ cv.f1[k.key] }}%</td>
          </tr>
          {% endfor %}
        </tbody>
      </table>
    </div>

    <p class="cv-summary__note">
      Salah prediksi {{ cv.kesalahan.total }} foto: {{ cv.kesalahan.bersebelahan }} ke kelas bersebelahan, {{ cv.kesalahan.jauh }} melompat jauh.
      {% if cv.cross_entropy is not none %}&nbsp;|&nbsp; Cross-entropy {{ cv.cross_entropy }} (acak 4 kelas ≈ 1.386){% endif %}
      &nbsp;|&nbsp; Akurasi per fold:
      {% for f in cv.per_fold %}{{ f.akurasi }}%{{ ', ' if not loop.last }}{% endfor %}
    </p>
  </div>
</section>
{% endif %}
```

`app/templates/components/auth_card_header.html`:

```html
{# Auth card header. Variables: ach_title, ach_subtitle, ach_icon_path,
   ach_icon_fill (optional), ach_icon_stroke (optional). #}
<div class="auth-card__head">
  <div class="auth-card__ico" aria-hidden="true">
    <svg viewBox="0 0 24 24"
         fill="{{ ach_icon_fill if ach_icon_fill is defined else 'currentColor' }}"
         {% if ach_icon_stroke is defined and ach_icon_stroke %}stroke="currentColor"{% endif %}>
      {{ ach_icon_path | safe }}
    </svg>
  </div>
  <h1 class="auth-card__title">{{ ach_title }}</h1>
  <p class="auth-card__subtitle">{{ ach_subtitle }}</p>
</div>
```

`app/templates/components/auth_footer.html`:

```html
<p class="auth-card__foot">Kota Lhokseumawe &mdash; Sistem GIS Kerusakan Jalan berbasis CNN</p>
```

- [ ] **Step 11: Add the new component rules**

Append to `app/static/css/components.css`:

```css
/* Page header */
.page-header { display: flex; align-items: center; gap: var(--s-2); margin-bottom: var(--s-4); }
.page-header__back { flex-shrink: 0; }
.page-header__text { min-width: 0; }
.page-header__title {
  margin: 0;
  font-size: var(--t-xl);
  font-weight: 700;
  letter-spacing: -.015em;
  color: var(--ink-1);
}
.page-header__subtitle { margin: 0; font-size: var(--t-sm); color: var(--ink-2); }

/* KPI */
.kpi__text { flex: 1; min-width: 0; }
.kpi__icon {
  width: 32px; height: 32px;
  flex-shrink: 0;
  border-radius: var(--r-1);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--kpi-icon-bg, var(--accent-wash));
  color: var(--kpi-icon-color, var(--accent));
}
.kpi__icon svg { width: 18px; height: 18px; }

/* Quick-action tile. The original rewrote inline styles on every mouse
   event; hover is pure CSS. */
.qa-tile {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  padding: var(--s-2) var(--s-3);
  border: 1px solid var(--rule);
  border-left: 2px solid var(--qa-color, var(--accent));
  border-radius: var(--r-1);
  background: var(--qa-bg, var(--surface-1));
  color: var(--qa-color, var(--accent));
  text-decoration: none;
  transition: background var(--dur-1) var(--ease), color var(--dur-1) var(--ease);
}
.qa-tile:hover { background: var(--qa-color, var(--accent)); color: #fff; }
.qa-tile:hover .qa-tile__ico { color: #fff; }
.qa-tile__ico { width: 16px; height: 16px; flex-shrink: 0; }
.qa-tile__label { font-size: var(--t-sm); font-weight: 600; }

/* CV summary */
.cv-summary__stat { text-align: center; padding: var(--s-2); border: 1px solid var(--rule); border-radius: var(--r-1); }
.cv-summary__value {
  margin: 0;
  font-family: var(--font-mono);
  font-variant-numeric: tabular-nums;
  font-size: var(--t-lg);
  font-weight: 700;
  color: var(--stat-color, var(--ink-1));
}
.cv-summary__label { margin: 0; font-size: 10px; color: var(--ink-2); }
.cv-summary__note { margin: var(--s-2) 0 0; font-size: var(--t-sm); color: var(--ink-2); }
.panel__head-note { font-size: var(--t-xs); font-weight: 400; letter-spacing: 0; text-transform: none; color: var(--ink-3); }

/* Table row actions */
.table-actions { display: flex; gap: var(--s-1); flex-wrap: wrap; }
.btn--danger-ghost { color: var(--danger); border-color: var(--rule); }
.btn--danger-ghost:hover { background: var(--danger); color: #fff; border-color: var(--danger); }

.table--dense td { height: 26px; }
.table--dense thead th { font-size: 10px; }

.empty-cell { padding: var(--s-6) 0; text-align: center; color: var(--ink-3); }

/* Auth card */
.auth-card__head { padding: var(--s-6) var(--s-8); text-align: center; background: var(--ink-1); }
.auth-card__ico {
  width: 48px; height: 48px;
  margin: 0 auto var(--s-3);
  border-radius: 50%;
  background: var(--accent);
  color: #fff;
  display: flex;
  align-items: center;
  justify-content: center;
}
.auth-card__ico svg { width: 24px; height: 24px; }
.auth-card__title { margin: 0; font-size: 18px; font-weight: 600; color: #fff; }
.auth-card__subtitle { margin: 4px 0 0; font-size: var(--t-sm); color: rgba(255, 255, 255, .72); }
.auth-card__foot { margin-top: var(--s-5); text-align: center; font-size: var(--t-xs); color: rgba(255, 255, 255, .72); }
```

- [ ] **Step 12: Run the shell contract test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_design_tokens -v`
Expected: PASS, 15 tests (6 token checks plus 9 shell-contract checks).

- [ ] **Step 13: Run the full suite**

Run: `.\.venv\Scripts\python.exe -m unittest discover tests`
Expected: `Ran 76 tests`, `OK`, exit code 0.

- [ ] **Step 14: Verify the audit counters**

```powershell
$files = (Get-ChildItem app\templates -Recurse -File -Include *.html | Where-Object { $_.FullName -notlike '*\landing\*' }).FullName
$inl = 0
foreach($f in $files){ $inl += ([regex]::Matches((Get-Content $f -Raw),'style="([^"]*)"')).Count }
"inline style attributes remaining: $inl  (base.html should be 0, total was 831)"
$tw = 0
foreach($f in $files){ $tw += ([regex]::Matches((Get-Content $f -Raw),'(cdn\.tailwindcss|tailwind\.config|-translate-x-full|lg:hidden|lg:relative|z-\[9999\])')).Count }
"Tailwind references remaining: $tw  (expected 0)"
$bs = 0
foreach($f in $files){ $bs += ([regex]::Matches((Get-Content $f -Raw),'bootstrap@5\.3\.3/dist/(css|js)')).Count }
"Bootstrap css/js references remaining: $bs  (expected 0)"
```

Expected: `base.html` contributes 0 inline styles, Tailwind 0, Bootstrap CSS/JS 0. The overall inline count will still be high; Waves A3 to A5 reduce it.

- [ ] **Step 15: Check the pages by hand**

The suite cannot see layout. Start the app and check each of these. This is the only way to catch Review Focus items 1 and 2.

```powershell
.\.venv\Scripts\python.exe -m flask --app app:create_app run --port 5000
```

Log in, then verify:

| Check | Expected |
|---|---|
| Rail at 1440px | Permanent left column, numbers `01` to `08` visible, no scrollbar |
| Rail item contrast | Inactive label legible; sample the computed colour, it must be at least 4.5:1 on `#12161C` |
| Active item | Filled `--rail-active` background with full-opacity white text |
| Breadcrumb | Home icon plus `sr-only` text; no visible stray "Dashboard" |
| Toast | Trigger any flash action; the toast appears top-right with a coloured left edge, and the browser console is free of errors |
| Confirm dialog | Click delete on any row; the dialog opens with correct type colour, focus lands on the confirm button, `Esc` closes it, `Enter` confirms |
| Drawer at 390px | Hamburger visible, rail off-screen, tapping it slides the rail in, overlay dismisses it |
| Role badge and logout | Both visible at 1440px; the logout label hides below 640px but the button stays |
| All 10 partials | `page_header` on any listing page, `status_badge` on a lokasi row, `detail_row` on `lokasi/detail`, `empty_table_row` on an empty table, `table_actions` on a row, `kpi_card` and `quick_action` on `dashboard`, `cv_summary` on `arsitektur/detail`, `auth_card_header` on `/auth/login` |

Note that `kpi_card` and `quick_action` were referenced by zero templates before this wave, so they are not yet rendered anywhere. Render them once on the dashboard in this wave to confirm they are not broken, or accept that Wave A5 is their first real test.

- [ ] **Step 16: Commit**

```powershell
git add app/templates/base.html app/templates/components/ app/static/css/layout.css app/static/css/components.css tests/test_design_tokens.py
git commit -m "feat(ui): rewrite shell on the Clinical Instrument design system

Removes the Tailwind Play CDN, Bootstrap CSS and Google Fonts from base.html.
Bootstrap Icons stays: it is an icon font, not a layout system.

The rail is numbered 01-08 following the pipeline order, and inactive items now
use explicit colours instead of opacity .72, which measured about 4.0:1 on the
rail background and failed WCAG AA.

toggleSidebar now flips .is-open instead of Tailwind's -translate-x-full, and
dispatches a resize event so Leaflet re-measures the map. showConfirm now sets
data-type and lets CSS pick the colour, so tokens.css stays the single source
of truth.

Rewrites all ten partials onto .panel, .kpi, .chip, .dl, .table and .btn,
keeping every caller variable name unchanged. cv_summary, kpi_card and
quick_action now pass dynamic values as custom properties."
```

---

## Task 3: Map the shared vocabulary onto the listing pages

`page_header`, `status_badge`, `detail_row`, `empty_table_row`, and `table_actions` are the five partials used across the listing pages, so Wave A3 is mostly mechanical once the components exist.

**Files:**
- Modify: `app/templates/lokasi/index.html`
- Modify: `app/templates/augmentasi/index.html`
- Modify: `app/templates/split/index.html`
- Modify: `app/templates/arsitektur/index.html`
- Modify: `app/templates/preprocessing/index.html`
- Modify: `app/templates/label/index.html`
- Modify: `app/templates/evaluasi/index.html`
- Modify: `app/templates/auth/login.html`
- Modify: `app/templates/auth/register.html`

**Interfaces:**
- Consumes: everything from Tasks 1 and 2.
- Produces: the Bootstrap-to-new-vocabulary mapping used again in Tasks 4 and 5. Record it in the commit message.

- [ ] **Step 1: Write the mapping test**

Create `tests/test_no_bootstrap_classes.py`:

```python
"""Menjaga agar kelas Bootstrap tidak tersisa di template internal.

Bootstrap CSS keluar di Task 2. Kelas yang masih tertinggal tidak akan
bergaya, dan grid `row`/`col-*` yang kehilangan makna membuat form kehilangan
tata letak kolomnya tanpa error. Uji ini memindai markup secara statis.
"""

import re
import unittest
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parent.parent / "app" / "templates"

# Kelas Bootstrap yang tidak punya padanan di design system baru.
FORBIDDEN = [
    # grid
    "row", "col-1", "col-2", "col-3", "col-4", "col-5", "col-6",
    "col-7", "col-8", "col-9", "col-10", "col-11", "col-12",
    "col-sm-1", "col-sm-2", "col-sm-3", "col-sm-4", "col-sm-6",
    "col-md-1", "col-md-2", "col-md-3", "col-md-4", "col-md-6", "col-md-8",
    "col-lg-2", "col-lg-3", "col-lg-4", "col-lg-6",
    "container", "container-fluid", "g-2", "g-3", "g-4",
    # komponen
    "card", "card-body", "card-header", "card-title", "card-footer",
    "form-control", "form-control-sm", "form-label", "form-select",
    "form-floating", "form-check", "form-check-input", "form-check-label",
    "form-text", "form-group", "input-group", "invalid-feedback", "valid-feedback",
    "table-responsive", "table-sm", "table-striped", "table-hover", "table-bordered",
    "alert", "alert-danger", "alert-warning", "alert-info", "alert-success",
    "badge", "list-group", "list-group-item", "nav", "navbar", "dropdown-menu",
    "modal", "spinner-border", "pagination", "offcanvas", "accordion", "tooltip",
    "btn-close", "visually-hidden",
    # utilitas yang sering tertinggal
    "d-flex", "d-block", "d-none", "d-grid", "d-inline-flex",
    "justify-content-between", "justify-content-end", "justify-content-center",
    "align-items-center", "align-items-start", "align-self-center",
    "flex-column", "flex-wrap", "flex-shrink-0", "flex-grow-1",
    "text-center", "text-end", "text-muted", "text-danger", "text-success",
    "fw-bold", "fw-normal", "fw-semibold", "fs-5", "fs-6",
    "mb-0", "mb-1", "mb-2", "mb-3", "mb-4", "me-1", "me-2", "ms-1", "ms-2",
    "mt-1", "mt-2", "mt-3", "p-0", "p-1", "p-2", "p-3",
    "w-100", "w-50", "h-100", "min-w-0", "rounded", "rounded-circle",
    "shadow-sm", "shadow", "border", "border-0", "overflow-hidden",
    "no-underline", "cursor-pointer", "sticky-top",
]

TARGETS = [
    "lokasi/index.html", "augmentasi/index.html", "split/index.html",
    "arsitektur/index.html", "preprocessing/index.html", "label/index.html",
    "evaluasi/index.html", "auth/login.html", "auth/register.html",
]


def class_tokens(html):
    out = set()
    for match in re.finditer(r'class="([^"]*)"', html):
        for token in match.group(1).split():
            token = token.split("{")[0].strip()
            if token:
                out.add(token)
    return out


class TestNoBootstrapClasses(unittest.TestCase):
    def test_targets_exist(self):
        for rel in TARGETS:
            self.assertTrue((TEMPLATES / rel).exists(), f"{rel} tidak ada")

    def test_no_bootstrap_classes(self):
        for rel in TARGETS:
            html = (TEMPLATES / rel).read_text(encoding="utf-8")
            found = sorted(class_tokens(html) & set(FORBIDDEN))
            self.assertEqual(
                found, [],
                f"{rel} masih memakai kelas Bootstrap: {', '.join(found)}",
            )

    def test_bootstrap_responsive_helpers_gone(self):
        """`d-none d-md-block` dan sejenisnya tidak punya padanan; pakai .is-* atau media query CSS."""
        for rel in TARGETS:
            html = (TEMPLATES / rel).read_text(encoding="utf-8")
            for prefix in ("d-sm-", "d-md-", "d-lg-", "d-xl-", "d-none d-",
                           "visible", "invisible", "float-"):
                self.assertNotIn(
                    prefix, html,
                    f"{rel} masih memakai helper responsif Bootstrap {prefix}",
                )

    def test_landing_untouched(self):
        """Landing_page berdiri sendiri dan tidak boleh ikut berubah."""
        landing = TEMPLATES / "landing" / "index.html"
        html = landing.read_text(encoding="utf-8")
        self.assertIn("cdn.tailwindcss.com", html,
                      "landing harus tetap memakai Tailwind sendiri; jangan sentuh")
        self.assertNotIn("{% extends", html, "landing tidak mewarisi base.html")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_no_bootstrap_classes -v`
Expected: FAIL on `test_no_bootstrap_classes`, listing the Bootstrap classes still present.

- [ ] **Step 3: Apply the mapping**

For each of the nine templates, apply this table. Work one file at a time and re-read it after editing; these files are small but the counts are not.

| Bootstrap | Pengganti | Catatan |
|---|---|---|
| `row` + `col-*` | `.grid` + `.grid--2/3/4`, atau `.grid--auto` | `col-6 col-md-3` menjadi `.grid--4`; `col-6` saja menjadi `.grid--2` |
| `g-2`, `g-3`, `g-4` | `gap` bawaan `.grid` | bawaan 12px; untuk 8px tambahkan `style="--gap:8px"` |
| `container`, `container-fluid` | tidak ada | `#main-content` sudah memberi padding |
| `card`, `card-body` | `.panel`, `.panel__body` | |
| `card-header` | `.panel__head` | |
| `form-control`, `form-control-sm` | `.control` | |
| `form-label` | `.field__label` | bungkus dengan `.field` |
| `form-select` | `.control` + `<select>` | |
| `form-floating` | tidak ada | ganti `.field` biasa dengan `<label>` di atas |
| `form-check-input`, `form-check-label` | `<input type=checkbox class=control>` + `<span>` | |
| `form-text` | `.hint` | |
| `invalid-feedback` | `.error-text` | |
| `table-responsive` | `.table-wrap` | |
| `table`, `table-sm`, `table-hover` | `.table`, opsional `.table--dense` | |
| `alert alert-danger` | `.error-text` atau `.panel` dengan border kiri | |
| `badge` | `.chip` + `.chip--ok/warn/danger/info/muted` | |
| `list-group-item` | `.dl__row` | |
| `btn`, `btn-sm` | `.btn`, `.btn--sm` | |
| `btn-primary`, `btn-cnn-primary` | `.btn--primary` | |
| `btn-outline-secondary` | `.btn--ghost` | |
| `btn-outline-danger` | `.btn--ghost .btn--danger-ghost` | |
| `d-flex`, `align-items-center`, `gap-2` | `.stack` atau flex utilitas baru | tambahkan ke `layout.css` bila perlu |
| `justify-content-between` | `justify-between` | tambahkan ke `layout.css` |
| `text-muted` | warna dari `.hint` atau `.dl__k` | |
| `fw-bold` | `font-weight:600` via kelas semantik | |
| `mb-0` … `mb-4` | jarak dari `.stack` atau `.page-header` | |
| `w-100` | `width:100%` pada `.table` | |
| `text-center` | `text-center` | tambahkan ke `layout.css` |
| `no-underline` | `text-decoration:none` | |
| `shadow-sm` | tidak ada | panel tidak memakai bayangan |
| `rounded`, `rounded-circle` | `.r-1`, atau `border-radius:50%` | |

Add whichever small utilities the mapping actually needs to `layout.css`, rather than inventing a utility framework:

```css
/* Utilities used by the listing and form pages. Deliberately few. */
.flex { display: flex; }
.items-center { align-items: center; }
.justify-between { justify-content: space-between; }
.justify-end { justify-content: flex-end; }
.text-center { text-align: center; }
.text-mono { font-family: var(--font-mono); font-variant-numeric: tabular-nums; }
.full-width { width: 100%; }
.truncate { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
```

Do not add a spacing scale of margin and padding utilities. That is how the current design got into trouble: `style.css` has 751 lines partly because every one-off spacing need became a token or a class. Use `.stack` and `.grid` gaps instead, and add a spacing utility only when a layout genuinely cannot be expressed with a gap.

- [ ] **Step 4: Remove inline styles from the nine templates**

For each of the nine files, delete every static `style="..."`. Where the value is dynamic, convert it:

```html
<!-- before -->
<div style="background:{{ t.warna_peta }};color:#fff">

<!-- after -->
<span class="chip" style="--chip-color:{{ t.warna_peta }}">{{ t.nama }}</span>
```

```html
<!-- before -->
<div style="width:{{ pct }}%">

<!-- after -->
<div class="meter"><span style="width:{{ pct }}%"></span></div>
```

`width` is the one property that legitimately stays inline when it is a runtime number, because it is data rather than styling. Everything else moves to CSS.

- [ ] **Step 5: Run the mapping test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_no_bootstrap_classes -v`
Expected: PASS, 4 tests.

If `test_landing_untouched` fails, a previous task touched `landing/index.html`. Restore it with `git checkout HEAD -- app/templates/landing/index.html` before continuing.

- [ ] **Step 6: Run the full suite**

Run: `.\.venv\Scripts\python.exe -m unittest discover tests`
Expected: `Ran 76 tests`, `OK`, exit code 0.

- [ ] **Step 7: Check the nine pages by hand**

Log in and open each page at 1440px and at 390px:

| Page | Check |
|---|---|
| `/lokasi` | Table renders, `status_badge` chip is coloured, row actions work, delete opens the dialog |
| `/augmentasi` | Listing and any config link render |
| `/split` | Listing renders, numeric columns are right-aligned and monospace |
| `/arsitektur` | Listing renders |
| `/preprocessing` | Listing renders |
| `/label` | Listing renders, config link works |
| `/evaluasi` | The heaviest Bootstrap user here, 45 class instances; check every table and form |
| `/auth/login` | Fields align, CSRF hidden input present, submit works, `auth_card_header` and `auth_footer` render |
| `/auth/register` | Password strength meter renders, role radio group works |

At 390px confirm no page scrolls horizontally. A page that does has a fixed pixel width somewhere that should be fluid.

- [ ] **Step 8: Commit**

```powershell
git add app/templates/lokasi/index.html app/templates/augmentasi/index.html app/templates/split/index.html app/templates/arsitektur/index.html app/templates/preprocessing/index.html app/templates/label/index.html app/templates/evaluasi/index.html app/templates/auth/login.html app/templates/auth/register.html app/static/css/layout.css tests/test_no_bootstrap_classes.py
git commit -m "feat(ui): move listing pages onto the new vocabulary

Maps 69 distinct Bootstrap classes onto .grid, .panel, .control, .table,
.chip and .btn across the nine listing and auth pages. The heaviest is
evaluasi/index.html with 45 Bootstrap class instances.

Dynamic values that were inline styles become custom properties, except
runtime widths, which stay inline because they are data rather than styling.

landing/index.html is untouched and still carries its own Tailwind."
```

---

## Task 4: Map the form pages

**Files:**
- Modify: `app/templates/lokasi/create.html`
- Modify: `app/templates/split/form.html`
- Modify: `app/templates/arsitektur/form.html`
- Modify: `app/templates/augmentasi/config_form.html`
- Modify: `app/templates/preprocessing/config_form.html`
- Modify: `app/templates/klasifikasi/upload.html`

**Interfaces:**
- Consumes: Tasks 1 to 3, including the vocabulary mapping recorded in Task 3's commit message.
- Produces: nothing new. Task 5 reuses the same mapping.

- [ ] **Step 1: Extend the mapping test to the form pages**

In `tests/test_no_bootstrap_classes.py`, extend `TARGETS`:

```python
TARGETS += [
    "lokasi/create.html", "split/form.html", "arsitektur/form.html",
    "augmentasi/config_form.html", "preprocessing/config_form.html",
    "klasifikasi/upload.html",
]
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_no_bootstrap_classes -v`
Expected: FAIL, listing Bootstrap classes in the six form templates.

- [ ] **Step 3: Rewrite the six forms**

Apply the Task 3 mapping. Two structures need care:

`form-floating` (21 uses across the codebase) has no equivalent. A floating label puts the label inside the control's box; the new `.field` puts it above. Convert each one to:

```html
<div class="field">
  <label class="field__label" for="nama">Nama jalan</label>
  <input class="control" type="text" id="nama" name="nama"
         value="{{ lokasi.nama or '' }}" required>
  {% if lokasi.nama_errors %}<p class="error-text">{{ lokasi.nama_errors[0] }}</p>{% endif %}
</div>
```

Preserve every `name=` and every `id=` exactly. The `for` and `id` pairing is new and is what makes the label clickable and screen-reader friendly.

Radio groups, used by `arsitektur/form.html` and `klasifikasi/upload.html`:

```html
<fieldset class="field">
  <legend class="field__label">Model</legend>
  <label class="radio-card">
    <input type="radio" name="model_type" value="mobileNetV2"
           {% if cfg.model_type == 'mobileNetV2' %}checked{% endif %}>
    <span>MobileNetV2</span>
  </label>
</fieldset>
```

Add to `components.css`:

```css
.radio-card {
  display: flex;
  align-items: center;
  gap: var(--s-2);
  padding: var(--s-2) var(--s-3);
  border: 1px solid var(--rule);
  border-radius: var(--r-1);
  font-size: var(--t-base);
  cursor: pointer;
}
.radio-card:has(input:checked) { border-color: var(--accent); background: var(--accent-wash); }
.radio-card input { accent-color: var(--accent); }
fieldset.field { border: 0; margin: 0; padding: 0; }
```

- [ ] **Step 4: Remove inline styles from the six forms**

Same rule as Task 3 Step 4. `preprocessing/config_form.html` alone carries 48 inline styles and 2 dynamic ones.

- [ ] **Step 5: Run the mapping test**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_no_bootstrap_classes -v`
Expected: PASS, 4 tests, now covering 15 target files.

- [ ] **Step 6: Run the full suite**

Run: `.\.venv\Scripts\python.exe -m unittest discover tests`
Expected: `Ran 76 tests`, `OK`, exit code 0.

- [ ] **Step 7: Check the six forms by hand**

For each form, at 1440px and 390px:

| Check | Why it matters |
|---|---|
| Every field still submits | A renamed `name` breaks the endpoint silently; the suite will not catch it |
| Validation errors still render | `.error-text` replaced `invalid-feedback`; the messages come from server-side validators |
| Clicking a label focuses its input | New `for`/`id` pairing; if wrong, keyboard users cannot reach the field |
| Radio selection is visibly marked | `:has(input:checked)` is unsupported in older browsers; if it fails, add a `.is-checked` class from JS as a fallback |
| Dropzone in `klasifikasi/upload.html` renders | It kept its `.cnn-dropzone-*` classes but lost Bootstrap's grid around it |
| Submit button is reachable and labelled | `.btn--primary` replaced `btn-primary` |

Confirm a real submission round-trips: create a lokasi, edit it, and confirm the change persists. These endpoints are not covered by the suite for field names.

- [ ] **Step 8: Commit**

```powershell
git add app/templates/lokasi/create.html app/templates/split/form.html app/templates/arsitektur/form.html app/templates/augmentasi/config_form.html app/templates/preprocessing/config_form.html app/templates/klasifikasi/upload.html app/static/css/components.css tests/test_no_bootstrap_classes.py
git commit -m "feat(ui): move form pages onto the new vocabulary

Converts 21 form-floating groups to .field with an explicit label and id pair,
which makes labels clickable and screen-reader addressable, neither of which
Bootstrap's floating labels provided.

Adds .radio-card with a :has(input:checked) selected state and a label-wrapped
input, so the whole tile is a hit target.

Every name= and id= is preserved: these are endpoint contracts, and the test
suite does not verify them."
```

---

## Task 5: Map the dense and visual pages, then close out

**Files:**
- Modify: `app/templates/dashboard/index.html`
- Modify: `app/templates/arsitektur/detail.html`
- Modify: `app/templates/preprocessing/hasil.html`
- Modify: `app/templates/split/detail.html`
- Modify: `app/templates/arsitektur/evaluasi.html`
- Modify: `app/templates/arsitektur/gis.html`
- Modify: `app/templates/peta/index.html`
- Modify: `app/templates/lokasi/detail.html`
- Modify: `app/templates/klasifikasi/hasil.html`
- Modify: `app/templates/label/index.html`
- Modify: `app/templates/label/config_form.html`
- Modify: `app/templates/label/edit.html`
- Modify: `app/templates/label/review.html`
- Delete: `app/static/css/style.css`

**Interfaces:**
- Consumes: everything from Tasks 1 to 4.
- Produces: the final state. After this task the inline-style count is zero across all 28 internal templates.

- [ ] **Step 1: Extend the mapping test to the whole internal set**

In `tests/test_no_bootstrap_classes.py`, replace `TARGETS` with a directory walk so nothing can be missed:

```python
def internal_templates():
    return sorted(
        p for p in TEMPLATES.rglob("*.html")
        if "landing" not in p.parts and "components" not in p.parts
    )


class TestNoBootstrapClassesEverywhere(unittest.TestCase):
    def test_no_bootstrap_classes_in_any_internal_template(self):
        offenders = {}
        for path in internal_templates():
            found = sorted(class_tokens(path.read_text(encoding="utf-8")) & set(FORBIDDEN))
            if found:
                offenders[str(path.relative_to(TEMPLATES))] = found
        self.assertEqual(
            offenders, {},
            "kelas Bootstrap tersisa:\n" + "\n".join(
                f"  {k}: {', '.join(v)}" for k, v in offenders.items()
            ),
        )

    def test_no_tailwind_in_any_internal_template(self):
        offenders = []
        for path in internal_templates():
            html = path.read_text(encoding="utf-8")
            if re.search(r"cdn\.tailwindcss|tailwind\.config|-translate-x-full"
                         r"|lg:(hidden|relative|flex-shrink-0|translate-x-0|p-6)"
                         r"|z-\[9999\]|max-w-\[calc", html):
                offenders.append(str(path.relative_to(TEMPLATES)))
        self.assertEqual(offenders, [], f"referensi Tailwind tersisa: {offenders}")
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_no_bootstrap_classes -v`
Expected: FAIL, listing the remaining templates.

- [ ] **Step 3: Rewrite `dashboard/index.html`**

806 lines and 456 lines of embedded CSS, 84 old-token `var()` uses, 24 Bootstrap class instances, and it hosts `kpi_card` and `quick_action` for the first time. Work top to bottom:

1. `dmg-*` classes: keep the names, they are page-local and Phase B will move them to a file. Only remap their token references from `--c-*` to the new vocabulary where the old token was remapped in Task 1.
2. `db-*` classes: same.
3. `kpi-card`, `kpi-label`, `kpi-value`, `kpi-meta`, `kpi-top`, `kpi-ico`, `kpi-grid`: these duplicate `.kpi`. Replace with the partial and delete the duplicates, so `.kpi` has one definition.
4. Bootstrap classes: apply the Task 3 mapping.
5. Inline styles: 23 instances, 2 dynamic. Convert the dynamic ones to custom properties.
6. Embedded `<style>`: leave in place. Phase B moves it. Removing it now would strip the page of its entire stylesheet.

Check afterwards that `dmg-*` and `db-*` still resolve. They are defined in that page's own `<style>`, which this task does not touch, so they must.

- [ ] **Step 4: Rewrite `arsitektur/detail.html`**

812 lines, 108 lines of embedded CSS, 126 old-token uses, 112 inline styles, 44 Bootstrap class instances, plus `cm-*`, `ev-*`, `popup-*` and `gis-*` usage and a Chart.js chart.

The `cm-*` classes become `.matrix`:

```html
<div class="table-wrap">
  <table class="matrix">
    <thead>
      <tr>
        <th class="matrix__corner">Kelas</th>
        {% for k in KELAS %}<th>{{ k.nama }}</th>{% endfor %}
      </tr>
    </thead>
    <tbody>
      {% for row in confusion %}
      <tr>
        <th scope="row" class="matrix__row-label">{{ row.label }}</th>
        {% for cell in row.cells %}
        <td class="matrix__cell{% if cell.diagonal %} matrix__cell--hi{% endif %}{% if cell.value < threshold %} matrix__cell--low{% endif %}">
          {{ cell.value }}
        </td>
        {% endfor %}
      </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

Keep the Chart.js `extra_js` block and its canvas `id` unchanged; the chart is functional code, not styling.

- [ ] **Step 5: Rewrite `preprocessing/hasil.html`**

616 lines and 114 inline styles, the highest count in the codebase. It is a thumbnail grid.

```html
<div class="thumb-grid">
  {% for item in hasil %}
  <figure class="thumb">
    <img src="{{ url_for('static', filename='uploads/preprocessed/' ~ item.nama) }}"
         alt="{{ item.label }}" loading="lazy" class="thumb__img">
    <figcaption class="thumb__meta">
      <span class="thumb__stage">{{ item.tahap }}</span>
      <span class="thumb__size thumb__size--{{ item.kategori }}">{{ item.dimensi }}</span>
    </figcaption>
  </figure>
  {% endfor %}
</div>
```

Add to `components.css`:

```css
.thumb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--s-3);
}
.thumb { margin: 0; border: 1px solid var(--rule); border-radius: var(--r-1); overflow: hidden; background: var(--surface-1); }
.thumb__img { display: block; width: 100%; height: 96px; object-fit: cover; }
.thumb__meta {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--s-1);
  padding: var(--s-1) var(--s-2);
  font-size: 10px;
  color: var(--ink-2);
  border-top: 1px solid var(--rule);
}
.thumb__stage { font-family: var(--font-mono); overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.thumb__size--sm { color: var(--sev-4); }
.thumb__size--md { color: var(--sev-3); }
.thumb__size--lg { color: var(--sev-2); }
```

The grid is fluid by construction, which is what keeps the page free of horizontal scroll at 390px.

- [ ] **Step 6: Rewrite the remaining nine templates**

`split/detail.html`, `arsitektur/evaluasi.html`, `arsitektur/gis.html`, `peta/index.html`, `lokasi/detail.html`, `klasifikasi/hasil.html`, and the four `label/*` templates. Apply the Task 3 mapping, remove static inline styles, convert dynamic ones to custom properties. Leave every embedded `<style>` block in place for Phase B.

`peta/index.html` and `arsitektur/gis.html` keep their Leaflet `extra_css` and `extra_js` blocks untouched. Confirm the element ids `peta.js` reads are all still present: `#map`, `#map-skeleton`, `#map-error`, `#map-error-msg`, `#filterStatus`, `#btnFilter`.

- [ ] **Step 7: Verify the Leaflet resize hook**

`peta/index.html` and `arsitektur/gis.html` must re-measure when the drawer opens. `base.html` dispatches a `resize` event from `toggleSidebar`, so add to each page's `extra_js`:

```html
<script>
window.addEventListener('resize', function () {
  if (window._cnnMap) window._cnnMap.invalidateSize();
});
</script>
```

Adjust the variable name to whatever the page already uses for its map instance. If it stores the map in a local `var` inside an IIFE, expose it on `window` first.

- [ ] **Step 8: Run both guard test files and confirm they pass**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_design_tokens tests.test_no_bootstrap_classes -v`
Expected: PASS, 21 tests (6 token, 9 shell-contract, 4 listing, 2 directory-wide).

This is the first point where the directory-wide checks apply to all 28 internal
templates. Both `test_no_bootstrap_classes_in_any_internal_template` and
`test_no_tailwind_in_any_internal_template` must be green. A failure here lists every
offending file and the exact classes, so work down the list rather than guessing.

- [ ] **Step 9: Delete `style.css`**

```powershell
git rm app/static/css/style.css
```

Then confirm nothing references it:

```powershell
$hits = @(rg -n "css/style\.css" app/ 2>$null)
if ($hits.Count -eq 0) { "no references to style.css remain" } else { $hits }
```

- [ ] **Step 10: Run the final inline-style audit**

```powershell
$files = (Get-ChildItem app\templates -Recurse -File -Include *.html | Where-Object { $_.FullName -notlike '*\landing\*' }).FullName
$static = 0; $dynamic = 0
foreach($f in $files){
  foreach($m in [regex]::Matches((Get-Content $f -Raw),'style="([^"]*)"')){
    if($m.Groups[1].Value -match '\{%'){ $dynamic++ } else { $static++ }
  }
}
"static inline styles : $static   (target 0, was 779)"
"dynamic inline styles: $dynamic   (52 value-carrying custom properties expected)"
```

Expected: `static inline styles : 0`. The dynamic count should be at most 52 and every one must be a custom property or a runtime width. Verify none is a style declaration:

```powershell
$bad = @()
$files = (Get-ChildItem app\templates -Recurse -File -Include *.html | Where-Object { $_.FullName -notlike '*\landing\*' }).FullName
foreach($f in $files){
  foreach($m in [regex]::Matches((Get-Content $f -Raw),'style="([^"]*\{\%[^"]*)"')){
    foreach($decl in ($m.Groups[1].Value -split ';')){
      if($decl -match '\{%' -and $decl -notmatch '^\s*--'){ $bad += "$($f.Replace('D:\flask\cnn_jalan\','')): $decl" }
    }
  }
}
if($bad.Count -eq 0){ "every dynamic inline style is a custom property" } else { $bad }
```

- [ ] **Step 11: Run the whole suite one final time**

Run: `.\.venv\Scripts\python.exe -m unittest discover tests`
Expected: `Ran 76 tests`, `OK`, exit code 0.

- [ ] **Step 12: Check all 28 pages by hand**

At 1440px, 1024px, and 390px, every internal page. Per page:

| Check | Fails visibly when |
|---|---|
| Page renders with no console error | A JS id was renamed |
| No horizontal scroll on `body` at 390px | A fixed pixel width survived |
| Tables scroll inside `.table-wrap` | The wrapper is missing, so the whole page scrolls |
| Matrix diagonal is highlighted | `.matrix__cell--hi` did not apply |
| Leaflet map fills its container and re-measures on drawer open | `invalidateSize` is not wired |
| Chart.js charts render | The canvas `id` or its `extra_js` was disturbed |
| KPI numbers are monospace and right-aligned | `tabular-nums` is not applied |
| Severity colours match the map legend | A chip lost its `--chip-color` |

This is the only verification that catches Review Focus item 5, and it cannot be shortened.

- [ ] **Step 13: Verify the landing page is byte-identical**

```powershell
git diff HEAD --stat -- app/templates/landing/index.html
```

Expected: empty output. If it is not empty, `git checkout HEAD -- app/templates/landing/index.html` and find which task touched it.

- [ ] **Step 14: Commit**

```powershell
git add app/templates/ app/static/css/ tests/
git commit -m "feat(ui): move dense and visual pages onto the new vocabulary

Completes the mapping across the thirteen remaining templates, including
dashboard/index.html with 456 lines of page CSS, arsitektur/detail.html with
812 lines and a Chart.js chart, and preprocessing/hasil.html with 114 inline
styles converted to a fluid thumbnail grid.

Confusion matrices become .matrix with a sticky row label and a highlighted
diagonal. Leaflet pages re-measure on the resize event that toggleSidebar
dispatches, so the map fills the container when the drawer opens.

Deletes app/static/css/style.css; its 57 live classes moved to components.css
and layout.css in the Task 1 split, and nothing references it.

Static inline style attributes across the 28 internal templates: 779 down to 0."
```

---

## Phase A Acceptance

- [ ] `.\.venv\Scripts\python.exe -m unittest discover tests` reports `Ran 76 tests` and `OK`
- [ ] `rg 'cdn.tailwindcss|bootstrap@5.3.3/dist|fonts.googleapis' app/templates/base.html` is empty
- [ ] Static inline `style` count across the 28 internal templates is 0
- [ ] Every remaining dynamic inline style is a custom property or a runtime width
- [ ] `git diff HEAD --stat -- app/templates/landing/index.html` is empty
- [ ] `app/static/css/style.css` no longer exists
- [ ] `rg -c -- '--c-' app/templates/` reports 0, meaning the legacy alias block can be deleted in Phase B
- [ ] All 28 pages verified by hand at 1440px, 1024px, and 390px
- [ ] No text below 4.5:1 contrast
- [ ] No horizontal page scroll at 390px
- [ ] Toast, confirm dialog, and drawer work in the browser, with the console free of errors

## Then: Phase B

Phase A must be complete and accepted first. Phase B is specified in the design document under `Migration Waves`, waves B1 to B4, and is not detailed here. Its first step is deleting the legacy alias block from `tokens.css` once the acceptance criterion above reports 0 references, which retires the last of the 883 old-token uses.
