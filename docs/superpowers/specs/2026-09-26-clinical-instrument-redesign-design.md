# Redesign Tampilan: Clinical Instrument

## Status

Disetujui 2026-09-26. Belum ada implementasi.

## Goal

Mengganti tampilan aplikasi dari kondisi yang teridentifikasi sebagai AI-slop menjadi satu
sistem desain bernuansa *clinical instrument* yang akademis, terstruktur, minimalis, dan
responsif, tanpa mengubah satu pun perilaku aplikasi.

## Context

Audit terhadap `app/templates/` dan `app/static/` pada 2026-09-26 mengukur enam penyebab.
Semuanya terverifikasi lewat penghitungan, bukan perkiraan.

### 1. Tiga sistem CSS bertarung

`base.html` memuat enam referensi eksternal:

| # | Aset | Catatan |
|---|------|---------|
| 1 | `cdn.tailwindcss.com` (Tailwind **Play** CDN) | Bukan untuk produksi menurut dokumentasi Tailwind |
| 2 | `preconnect fonts.googleapis.com` | - |
| 3 | `preconnect fonts.gstatic.com` | - |
| 4 | `fonts.googleapis.com/css2?family=Inter` | Webfont |
| 5 | `cdn.jsdelivr.net/.../bootstrap@5.3.3.min.css` | - |
| 6 | `cdn.jsdelivr.net/.../bootstrap-icons@1.11.3` | Icon font |

`tailwind.config` di `base.html` menyetel `corePlugins: { preflight: false }`, dengan
komentar yang mengakui hal itu secara eksplisit: *"preflight disabled so Bootstrap
coexists"*. Itu band-aid, bukan keputusan desain.

Ditambah `app/static/css/style.css` (751 baris, 25.914 byte) yang tidak pernah menggantikan
kedua sistem di atas, melainkan menjadi sistem ketiga yang bertentangan. **Koreksi terhadap
dugaan awal:** `style.css` ternyata bukan warisan yang mati. Isinya memuat 57 kelas yang
masih hidup dan dipakai, antara lain `.cnn-kpi-card`, `.cnn-breadcrumb`, `.cnn-empty-state`,
`.cnn-dropzone`, `.cnn-status-*`, `.sidebar-nav-link`, dan keluarga `.auth-*` sekitar 30
kelas. Semuanya ditulis tangan dan arahnya sudah benar. Berkas ini dipecah, bukan dibuang.

### 2. Dua sistem grid dalam satu dokumen

`row`, `col-6`, `col-md-3`, `col-sm-4` (grid Bootstrap) dipakai berdampingan dengan
`flex`, `h-screen`, `p-4`, `lg:p-6` (utility Tailwind) di template yang sama.

### 3. Token ada tapi tidak dipakai

`style.css` mendefinisikan palet slate/sky yang layak (`:root` baris 2 sampai 48). Terhadap
palet itu, **831 atribut `style="..."` inline** tersebar di 40 template. Distribusi teratas:

| Template | Baris | Inline |
|----------|------:|-------:|
| `preprocessing/hasil.html` | 616 | 114 |
| `arsitektur/detail.html` | 812 | 112 |
| `split/detail.html` | 323 | 52 |
| `preprocessing/config_form.html` | 361 | 48 |
| `peta/index.html` | 429 | 46 |
| `arsitektur/gis.html` | 425 | 43 |
| `arsitektur/form.html` | 365 | 38 |
| `preprocessing/index.html` | 195 | 38 |
| `base.html` | 371 | 36 |

### 3b. Lapis kelima yang tidak terlihat di inventaris awal

Penghitungan lanjutan menemukan bahwa **1.158 baris CSS tertanam sebagai blok `<style>`
di dalam 15 template**, di luar `style.css` dan di luar inline style. Tidak ada satu pun
dari baris itu yang berada di stylesheet.

| Template | Baris CSS tertanam |
|----------|-------------------:|
| `dashboard/index.html` | 456 |
| `arsitektur/detail.html` | 108 |
| `arsitektur/evaluasi.html` | 99 |
| `arsitektur/gis.html` | 78 |
| `split/form.html` | 58 |
| `split/index.html` | 57 |
| `split/detail.html` | 55 |
| `arsitektur/form.html` | 55 |
| `arsitektur/index.html` | 71 |
| `peta/index.html` | 56 |
| `preprocessing/config_form.html` | 45 |
| `auth/login.html`, `auth/register.html` | 7 masing-masing |
| `lokasi/detail.html`, `preprocessing/hasil.html` | 3 masing-masing |

Jadi CSS proyek terdiri dari lima lapis, bukan tiga:

| Lapis | Isi | Perlakuan |
|-------|-----|-----------|
| 1 | `style.css`, 751 baris, 57 kelas hidup | Dipecah menjadi tiga berkas, isi dipertahankan |
| 2 | `<style>` di 15 template, 1.158 baris | **Phase B** |
| 3 | Inline `style="..."`, 831 atribut | Phase A, target 0 |
| 4 | Bootstrap CSS dari CDN, 160 kelas | Phase A, dibuang |
| 5 | Tailwind Play CDN, 10 kelas | Phase A, dibuang |

### 3c. Komponen per halaman yang layak dipromosikan

Dari 122 kelas berawalan halaman, **23 dipakai di lebih dari satu template**, dalam empat
keluarga yang jelas. Ini kode yang sudah ada dan arahnya sudah benar, jadi tugasnya memindahkannya
ke layer komponen, bukan menulis ulang:

| Keluarga | Jumlah | Konsumen |
|----------|-------:|----------|
| `popup-*` | 4 | `arsitektur/detail`, `arsitektur/gis`, `peta/index` |
| `cm-*` | 8 | `arsitektur/detail`, `arsitektur/evaluasi` |
| `gis-stat*`, `gis-legend`, `gis-filter`, `gis-dot` | 6 | `arsitektur/detail`, `arsitektur/gis` |
| `ev-*` | 5 | `arsitektur/detail`, `arsitektur/evaluasi` |

Sembilan puluh sembilan kelas lainnya benar-benar lokal per halaman dan di Phase B pindah ke
`app/static/css/pages/`.

### 4. Sistem komponen ada di atas kertas saja

`templates/components/` berisi 10 partial. Empat tidak dipakai template mana pun:
`kpi_card`, `quick_action`, `auth_card_header`, `auth_footer`. `page_header` dipakai
25 template; sisanya hanya 1 sampai 2.

### 5. Bootstrap JS adalah beban mati

- `new bootstrap.Modal|Dropdown|Tooltip|Toast|Offcanvas` : **0 kemunculan**
- `data-bs-*` : **1 kemunculan** (`evaluasi/index.html`)
- `bootstrap.bundle.min.js` dimuat, tidak pernah dipanggil

### 6. Proporsi keseluruhan

- 40 template total; 39 internal; 1 landing
- 29 template mewarisi `base.html`; 10 partial; 1 landing **mandiri**
- 304 pemakaian kelas Tailwind, 380 pemakaian kelas Bootstrap, 69 kelas Bootstrap berbeda
- 190 instans `<i class="bi bi-*">` (81 nama berbeda)
- 31 blok `<script>` inline, 38 handler `onclick`/`onchange`/`onsubmit` inline
- `Material Symbols` hanya di landing (13 kemunculan)

### Temuan yang menyederhanakan arsitektur

**`landing/index.html` tidak mewarisi `base.html`.** Ia punya `<!DOCTYPE html>` sendiri dan
6 referensi CDN sendiri. Konsekuensinya, menunda landing tidak berbahaya: membuang Tailwind
dari shell tidak akan merusaknya. Kedua dokumen benar-benar independen.

---

## Scope

Pekerjaan dipecah dua fase. **Phase A** memperbaiki tampilan dan menghapus sistem yang
bersaingan. **Phase B** mengonsolidasikan CSS per halaman. Pemisahan ini disengaja: CSS
yang tertanam di template sudah ditulis tangan dan sebagian besar arahnya sudah sesuai,
jadi itu pekerjaan maintainability, bukan perbaikan tampilan. Phase A menghasilkan
perubahan yang langsung bisa dinilai, sementara Phase B bisa jadi PR terpisah.

### Phase A, in scope

1. `app/static/css/style.css` dipecah menjadi `tokens.css`, `components.css`, `layout.css`.
   Isi 57 kelas yang hidup dipertahankan dan dipindahkan, bukan ditulis ulang.
2. Bootstrap CSS dan Tailwind Play CDN dibuang dari `base.html`. Bootstrap Icons tetap,
   dengan alasan di bagian Non-goal.
3. `base.html` ditulis ulang: shell, rail bernomor, header, breadcrumb, main, dialog, drawer
4. Dua blok inline JS di `base.html` ditulis ulang, karena `toggleSidebar` memut class
   Tailwind dan `showConfirm` menyetel warna dialog langsung dari JS
5. 10 partial di `templates/components/`
6. 28 template internal, dari inline style dan kelas Bootstrap/Tailwind ke kosakata baru
7. 831 atribut inline style menjadi 0

### Phase B, in scope

1. Ekstraksi 1.158 baris `<style>` dari 15 template ke `app/static/css/pages/`
2. Promosi empat keluarga reusable (`popup-*`, `cm-*`, `gis-stat*`, `ev-*`) ke
   `components.css`
3. Konsolidasi 99 kelas yang tersisa menjadi lokal per halaman

### Out of scope, kedua fase

- **`landing/index.html`** : tidak disentuh, atas dasar temuan di atas
- Route, controller, model, service, dan seluruh kode Python
- `name=` field form, target `url_for`, dan nilai `data-*` yang dibaca JS
- **`TODO.md`** dan 21 file yang ditandai JANGAN DIUBAH di dalamnya
- Migrasi ke build tool CSS (Node, webpack, vite). Tetap CSS statis yang di-link langsung
- Dark mode
- Mengganti Bootstrap Icons dengan inline SVG

### Non-goal yang disengaja

**Bootstrap Icons tetap.** 190 instans, 81 nama. Ia adalah icon font, bukan sistem layout,
jadi tidak bersaing dengan design system. Menulis 81 SVG tangan memperbesar diff tanpa
nilai desain yang sebanding. Blueprint untuk pekerjaan ini ada di bagian Tindak Lanjut.

---

## Design Tokens

Berkas: `app/static/css/tokens.css`. Satu blok `:root`. Tidak ada token yang di-override di
luar berkas ini, termasuk oleh inline style.

### Warna

Permukaan dan tinta:

| Token | Nilai | Pemakaian |
|-------|-------|------------|
| `--surface-0` | `#F4F6F8` | Latar halaman |
| `--surface-1` | `#FFFFFF` | Isi panel dan kartu |
| `--surface-2` | `#E8ECF0` | Kepala panel, `thead` tabel, chip |
| `--surface-3` | `#D3D9E0` | Garis hairline, placeholder |
| `--ink-1` | `#12161C` | Teks utama, rail |
| `--ink-2` | `#5F6B7A` | Teks sekunder, label |
| `--ink-3` | `#8794A3` | Teks redam, placeholder |
| `--rule` | `#D3D9E0` | Garis hairline 1px |
| `--rule-strong` | `#B7C1CC` | Garis tegas, border kontrol |

Aksen tunggal:

| Token | Nilai |
|-------|-------|
| `--accent` | `#0F4C81` |
| `--accent-hover` | `#0B3A66` |
| `--accent-ink` | `#FFFFFF` |
| `--accent-wash` | `#EAF1F7` |

Rail gelap:

| Token | Nilai |
|-------|-------|
| `--rail` | `#12161C` |
| `--rail-ink` | `#E7EBEF` |
| `--rail-ink-dim` | `#8A94A0` |
| `--rail-active` | `#0F4C81` |

Status:

| Token | Nilai | Pasangan latar |
|-------|-------|-----------------|
| `--ok` | `#059669` | `#ECFDF5` |
| `--warn` | `#D97706` | `#FFFBEB` |
| `--danger` | `#DC2626` | `#FEF2F2` |
| `--info` | `#0284C7` | `#E0F2FE` |

**Severity: sumbernya database, bukan preferensi.** Empat token ini adalah
`tingkat_kerusakan.warna_peta` yang sudah ada dan sudah dipakai di peta:

| Token | Nilai | Tingkat |
|-------|-------|---------|
| `--sev-1` | `#E53E3E` | Rusak Berat |
| `--sev-2` | `#F97316` | Rusak Ringan |
| `--sev-3` | `#F59E0B` | Sedang |
| `--sev-4` | `#10B981` | Baik |

Masing-masing punya pasangan `--sev-N-bg`, versi desaturasi sekitar 12 persen untuk latar
chip.

Klausul yang mengikat: **tidak ada warna kromatik lain yang boleh ditambahkan** di luar tabel
di atas. Kalau sebuah elemen butuh warna dan tidak ada tokennya, itu berarti komponennya
belum ada, bukan berarti token baru diperlukan. Klausul inilah yang menjaga palet tetap
empat warna dan membuat UI bermakna secara akademis, bukan dekoratif.

### Tipografi

Famili:

```
--font-ui:    system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", sans-serif
--font-mono:  ui-monospace, "Cascadia Mono", "SF Mono", Menlo, Consolas, monospace
```

**Inter dibuang dan tidak diganti webfont.** Alasannya ketersediaan, bukan estetika.
Aplikasi ini dipakai untuk presentasi, dan `fonts.googleapis.com` adalah request
render-blocking ke pihak ketiga yang tidak bisa diasumsikan tersedia. Pada 13.5px,
`system-ui` juga lebih tajam untuk tabel padat daripada Inter, dan ini menghapus 3 dari 6
referensi CDN.

Skala, dengan kepadatan *instrument* yang dipilih:

| Token | Ukuran | Pemakaian |
|-------|-------:|------------|
| `--t-xs` | 10.5px | Label uppercase, letter-spacing `.08em` |
| `--t-sm` | 12px | Meta, sel sekunder, badge |
| `--t-base` | 13.5px | Body dan sel tabel |
| `--t-md` | 15px | Subjudul, judul dialog |
| `--t-lg` | 18px | Judul panel |
| `--t-xl` | 22px | Judul halaman |
| `--t-metric` | 30px | Nilai KPI |

Aturan angka: setiap nilai KPI, setiap kolom numerik tabel, setiap Confusion Matrix, dan
setiap path atau field yang menyerupai kode memakai `--font-mono` dengan
`font-variant-numeric: tabular-nums`. Digit harus sejajar dalam kolom. Inilah yang
menghasilkan rasa instrument, dan sifatnya fungsional, bukan hiasan.

### Spasi, radius, dan gerak

Kelipatan 4: `--s-1` 4px sampai `--s-6` 24px, lalu `--s-8` 32px, `--s-10` 40px, `--s-12` 48px.
Default `--gap: 12px`.

Radius hanya `--r-1: 3px` dan `--r-2: 5px`. Tidak ada radius lebih besar. Lingkaran penuh
hanya untuk `.meter` dan avatar.

Bayangan hanya ada dua, dan hanya untuk overlay mengambang:

| Token | Nilai | Pemakaian |
|-------|-------|------------|
| `--shadow-1` | `0 1px 2px rgba(18,22,28,.06)` | Dialog, toast, drawer |
| `--shadow-2` | `0 8px 28px rgba(18,22,28,.14)` | Dialog pada state terangkat |

Panel, kartu, dan tabel **tidak** memakai bayangan. Mereka dibedakan oleh garis 1px
`--rule`. Ini perpindahan anti-slop terbesar: `style.css` lama mendefinisikan lima bayangan
(`--shadow-card` sampai `--shadow-xl`) yang dipakai luas, dan itulah yang membuat setiap
kartu tampak berbunga.

Gerak: `--dur-1: 120ms`, `--dur-2: 180ms`, `--ease: cubic-bezier(.2,0,.2,1)`. Tidak ada
spring atau bounce, sementara `style.css` lama punya
`--ease-spring: cubic-bezier(.34,1.56,.64,1)`.

`@media (prefers-reduced-motion: reduce)` menonaktifkan seluruh transisi dan animasi.

---

## Components

Berkas: `app/static/css/components.css`.

| Kelas | Ringkas |
|-------|---------|
| `.panel` | Permukaan 1, radius 3, border 1px `--rule`. Tanpa bayangan. |
| `.panel__head` | Latar `--surface-2`, tinggi 32px, label `--t-xs` uppercase dengan tracking. |
| `.panel__body` | Padding `--s-3` atau 12px. |
| `.kpi` | Border kiri aksen 2px lewat `inset 2px 0 0 var(--kpi-accent, var(--accent))`. |
| `.kpi--lead` | Latar `--accent`, teks `--accent-ink`, untuk satu metrik utama per halaman. |
| `.kpi__label` | `--t-xs` uppercase. |
| `.kpi__value` | `--t-metric`, mono, tabular. |
| `.kpi__unit` | `--t-xs`. |
| `.grid`, `.grid--2`, `--3`, `--4` | `display:grid` dengan `gap: var(--gap)`. Varian `--auto` memakai `repeat(auto-fit, minmax(200px,1fr))`. |
| `.stack` | Alur vertikal, `gap` dari `--gap`. |
| `.field` | Label, kontrol, dan hint atau error. |
| `.control` | Input, select, textarea. Border 1px `--rule-strong`, radius 3, tinggi 30px. |
| `.control:focus-visible` | `outline: 2px solid var(--accent)` dengan `outline-offset: 1px`. |
| `.hint`, `.error-text` | `--t-sm` dalam `--ink-3` atau `--danger`. |
| `.btn` | Tinggi 30px, radius 3, `--t-sm` weight 600, padding `0 12px`. |
| `.btn--primary` | Latar `--accent`, teks putih. |
| `.btn--ghost` | Border 1px `--rule-strong`, latar transparan. |
| `.btn--danger` | Latar `--danger`, teks putih. |
| `.table` | `width:100%`, `border-collapse:collapse`, `--t-base`. |
| `.table thead th` | Sticky `top:0`, `--surface-2`, `--t-xs` uppercase, border bawah 1px `--ink-1`. |
| `.table td` | Tinggi 30px, border bawah 1px `--rule`. |
| `.table__num` | `text-align:right`, mono, tabular. |
| `.table__key` | Kolom pertama sticky saat `.table-wrap` menggulir. |
| `.table-wrap` | `overflow-x:auto` dan `max-width:100%`. |
| `.chip` | Padding `1px 6px`, radius 3, `--t-xs` weight 600, teks putih. |
| `.chip--sev1` sampai `sev4` | Latar `--sev-N`. |
| `.chip--ok`, `--warn`, `--danger`, `--info` | Latar token status. |
| `.meter` | Tinggi 8px, radius penuh, `display:flex`, `overflow:hidden`. |
| `.dl`, `.dl__k`, `.dl__v` | Definition list padat, menggantikan pola `detail_row`. |
| `.rail`, `.rail__item`, `.rail__num` | Latar `--rail`, item tinggi 30px, nomor dua digit mono. |
| `.drawer` | Off-canvas, untuk lebar di bawah 1024px. |
| `.toast` | Restyle dari `toast.js` yang sudah ada. |
| `.dialog` | Restyle dari `#gcModal`. |

### Matriks perbandingan angka

Confusion Matrix, confusion matrix per fold, dan tabel Similaritas Patch bukan tabel biasa.
Selnya adalah nilai numerik dalam grid padat yang harus bisa dibandingkan secara diagonal dan
sejajar secara horizontal. Untuk ketiganya: `.matrix` dengan `.matrix__row-label` sticky di
kiri, `.matrix__cell` mono tabular, `.matrix__cell--hi` untuk diagonal, dan
`.matrix__cell--low` untuk nilai di bawah ambang. Grid tanpa gutter, border 1px `--rule`.

---

## Shell

`base.html`.

### Dibuang

Script Tailwind beserta blok `tailwind.config`, Bootstrap CSS, Google Fonts (3 baris), inline
`style` pada `<body>`, `<nav>`, dan `<header>`, serta komentar banner dekoratif berbentuk
garis kotak.

### Dipertahankan karena load-bearing

| ID atau kelas | Dibaca oleh |
|---------------|-------------|
| `#toast-container` | `toast.js:21` |
| `.tw-progress-bar` | `toast.js:58` |
| `#flash-data` | `toast.js:88` |
| `#sidebar`, `#sidebar-overlay` | inline script `base.html:347,361` |
| `#hamburger-btn` dengan `aria-expanded` | idem |
| `#main-content` | skip-link |
| `#gcModal`, `#gcHeader` | dialog konfirmasi |
| `#map`, `#map-skeleton`, `#map-error`, `#map-error-msg` | `peta.js:12` sampai `27` |
| `#filterStatus`, `#btnFilter` | `peta.js:33,79` |

### Blok yang tetap

`{% block extra_css %}` dan `{% block extra_js %}`. Leaflet (`peta/index.html`,
`arsitektur/gis.html`) dan Chart.js (`arsitektur/detail.html`, `lokasi/detail.html`,
`split/detail.html`) dimuat lewat sini. Keduanya pustaka fungsional, bukan sistem gaya, dan
tidak bertentangan dengan keputusan ini.

### Rail

Bernomor `01` sampai `07`, mengikuti urutan alur kerja: Dashboard, Lokasi, Labeling,
Preprocessing, Split, Arsitektur, Peta GIS. Tinggi item 30px. Item aktif memakai latar
`--rail-active` dengan teks penuh, bukan `opacity`, sebab `style.css` lama memakai
`opacity:.72` untuk item non-aktif dan itu membuat label nav gagal kontras WCAG AA.

---

## Kebijakan Inline Style

Target: **831 menjadi 0** untuk atribut `style="..."` yang statis.

**52 atribut berisi ekspresi Jinja tidak dapat dihapus** dan tidak boleh dihapus. Aturannya
adalah memindahkan nilai dinamis ke custom property, memakai pola yang sudah ada di codebase
ini: `--dmg-color`, `--kpi-accent`, `--fc`, `--cm-opacity`, dan `--qa-bg` sudah dipakai di
6 partial dan beberapa template.

```html
<div style="background:{{ t.warna_peta }};color:#fff">
```

menjadi

```html
<div class="chip chip--sev" style="--chip-color:{{ t.warna_peta }}">
```

dengan aturan di `components.css`:

```css
.chip--sev { background: var(--chip-color, var(--sev-1)); }
```

Sifat penting: yang dipindahkan ke markup adalah **nilai**, bukan **gaya**. Aturan ini
menjaga agar token tetap punya satu-satunya sumber kebenaran di `tokens.css`.

Daftar properti yang muncul pada inline style dinamis, untuk menyiapkan penulisan ulang:
`color` (26), `background` (25), `font-size` (12), `border-radius` (12), `width` (10),
`height` (9), `font-weight` (9), `flex-shrink` (7), `display` (6), `border` (4),
`padding` (3), `align-items` (3), `gap` (3), `transition` (3). Semuanya harus berakhir di
`components.css` sebagai properti CSS, bukan sebagai inline.

---

## Migration Waves

### Phase A

Setiap gelombang adalah satu commit. Perintah
`.\.venv\Scripts\python.exe -m unittest discover tests` dijalankan setelah tiap gelombang
(76 test, hasil `OK` diharapkan). Tidak ada perubahan logika, jadi test harus tetap hijau.
Kalau tidak, itu bug, bukan alasan untuk memperbarui test.

| # | Isi | File | Alasan urutan |
|---|-----|-----:|--------------|
| A1 | Pecah `style.css`, tulis `tokens.css` | `style.css` jadi 3 berkas | Semua gelombang berikutnya memakai token. Harus lebih dulu. |
| A2 | Shell | `base.html` + 2 blok inline JS + 10 partial | Rail, header, dialog, drawer. MemperChanging 28 template sekaligus lewat warisan shell, jadi harus proven lebih dulu. |
| A3 | Halaman listing | `lokasi/index`, `augmentasi/index`, `split/index`, `arsitektur/index`, `preprocessing/index`, `label/index`, `evaluasi/index`, `auth/login`, `auth/register` | Risiko rendah dan repetitif. Memvalidasi `.table` dan `.control` di dunia nyata. |
| A4 | Form | `lokasi/create`, `split/form`, `arsitektur/form`, `augmentasi/config_form`, `preprocessing/config_form`, `klasifikasi/upload` | Padat field. Memvalidasi `.field` dan `.control`. |
| A5 | Padat dan visual | `dashboard/index` (806 baris), `arsitektur/detail` (812 baris), `preprocessing/hasil` (616 baris, 114 inline), `split/detail`, `arsitektur/evaluasi`, `arsitektur/gis`, `peta/index`, `lokasi/detail`, `klasifikasi/hasil`, `label/{index,config_form,edit,review}` | Membawa Leaflet, Chart.js, dan grid thumbnail. Paling berisiko, dikerjakan terakhir. |

Checkpoint persetujuan user setelah A2 dan setelah A3.

### Phase B

| # | Isi | File |
|---|-----|-----:|
| B1 | Promosi komponen reusable | `cm-*` (8), `popup-*` (4), `gis-stat*` (6), `ev-*` (5) ke `components.css` |
| B2 | Ekstraksi per halaman | 15 blok `<style>` ke `app/static/css/pages/`, mulai `dashboard` (456 baris) |
| B3 | Ekstraksi sisa | 14 template sisanya, hapus blok `<style>` dari template |
| B4 | Rambut dan audit | Hapus sisa `style.css` lama, jalankan verification penuh |

Phase A harus selesai dan disetujui sebelum Phase B dimulai. Phase B tidak mengubah
tampilan, jadi setiap gelombangnya bisa direview tanpa persetujuan visual.

---

## Aksesibilitas

Tidak ada baseline aksesibilitas baru. Ini adalah minimum yang harus bertahan, dan beberapa
perlu diperbaiki.

- **Skip link** dipertahankan, mengarah ke `#main-content`.
- **Focus-visible** pada semua kontrol: `outline: 2px solid var(--accent)`. `style.css` lama
  punya `--focus-ring` via `box-shadow`; diganti `outline` karena tidak tertutup elemen
  bersebelahan.
- **Kontras teks navigasi**: `opacity` untuk item non-aktif diganti warna eksplisit.
- **Sticky `thead`** dengan `z-index` dan latar opaque, supaya tidak tembus pandang saat tabel
  digulir.
- **Target sentuh** minimal 30px pada kontrol. Di bawah 1024px, rail menjadi drawer penuh,
  bukan rail 240px yang diperkecil.
- **`prefers-reduced-motion`** dihormati.
- Ikon dekoratif memakai `aria-hidden="true"`. Ikon yang membawa makna memakai teks
  `<span class="visually-hidden">`, dan kelas `.visually-hidden` harus ada di `layout.css`.

## Responsif

| Breakpoint | Perilaku |
|-----------|----------|
| `>=1280px` | Rail 240px permanen, konten penuh. |
| `1024` sampai `1279px` | Rail 200px, grid KPI 3 kolom. |
| `<1024px` | Rail menjadi `.drawer` off-canvas, dibuka `#hamburger-btn`, ditutup oleh `#sidebar-overlay` atau `Esc`. Fokus dikurung selama terbuka. Grid KPI 2 kolom. |
| `<640px` | Rail drawer penuh. Grid 1 kolom. Tabel memakai `.table-wrap` dengan scroll horizontal dan kolom pertama sticky, **bukan** card-stacking, karena card-stacking merusak perbandingan antar-baris yang justru menjadi alasan tabel ada. |

Leaflet di `peta/index.html` dan `arsitektur/gis.html` harus dipanggil `invalidateSize()`
pada `resize` dan saat drawer dibuka, karena kontainer berubah lebar.

---

## Verification

Sebelum dianggap selesai:

1. `.\.venv\Scripts\python.exe -m unittest discover tests` menghasilkan `Ran 76 tests ... OK`
2. `rg -c 'style="' app/templates/` menghasilkan `0` untuk setiap template internal
3. `rg 'cdn.tailwindcss|bootstrap' app/templates/base.html` kosong
4. `rg 'class="[^"]*\b(flex|hidden|items-center|gap-|w-full|bg-[a-z]+-[0-9])' app/templates/`
   tidak bersisa di 28 template internal
5. 28 template internal dibuka di browser pada lebar 1440px, 1024px, dan 390px
6. `landing/index.html` diverifikasi tidak berubah. Karena sudah mandiri, isinya harus
   identik dengan `git show HEAD:app/templates/landing/index.html`
7. Toast, dialog konfirmasi, dan drawer diuji secara interaktif. Ketiganya punya JS yang
   membaca ID, jadi regresi di sini tidak ditangkap test Python

## Acceptance Criteria

- [ ] 831 menjadi 0 untuk inline style statis; 52 inline style dinamis menjadi custom property
- [ ] `base.html` memuat nol Tailwind, nol Bootstrap CSS, nol Google Fonts
- [ ] `landing/index.html` tidak berubah
- [ ] 28 template internal memakai hanya kelas dari `tokens.css`, `components.css`, dan `layout.css`
- [ ] Tidak ada warna kromatik di luar empat warna severity
- [ ] Tidak ada bayangan pada panel, kartu, atau tabel; hanya pada dialog, toast, dan drawer
- [ ] 76 test hijau
- [ ] Semua halaman terbaca di 390px tanpa scroll horizontal pada `body`
- [ ] Tidak ada warna teks di bawah rasio kontras WCAG AA 4.5:1

## Tindak Lanjut, di luar scope ini

1. **Bootstrap Icons menjadi inline SVG.** 81 nama ikon. Menghapus CDN terakhir dan
   memungkinkan ikon dua warna.
2. **Dark mode.** Memerlukan paruh kedua token (`--surface-*`, `--ink-*`, `--rule`) plus audit
   kontras tersendiri.
3. **Landing publik.** Setelah design language ini terbukti di 28 template, `landing` bisa
   dibangun ulang dengan token yang sama, bukan dengan Tailwind terpisah seperti sekarang.
4. **`style.css` lama** dihapus di Gelombang 1, tidak ditinggalkan sebagai dead code.
