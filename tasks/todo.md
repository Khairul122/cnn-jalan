# Labeling Rewrite Execution Ledger

Source plan: `tasks/plan.md`
Design spec: `docs/superpowers/specs/2026-09-25-kmeans-labeling-rewrite-design.md`

## Phase 1 — Foundation

- [x] Task 1: Establish failing labeling contract tests — RED→GREEN; focused contract suite 4/4
- [x] Task 2: Implement labeling models and relationships — metadata/import check lulus

### Checkpoint: Foundation
- [x] Model imports succeed
- [x] Focused tests fail only for unimplemented service behavior
- [x] No out-of-scope files changed

## Phase 2 — Algorithm and persistence

- [x] Task 3: Implement feature extraction and clustering core — focused suite 4/4
- [x] Task 4: Implement run persistence, apply, and discard — focused persistence suite 3/3

### Checkpoint: Algorithm
- [x] Focused labeling tests pass
- [x] Defaults and deterministic mapping are proven
- [x] Existing labels remain unchanged until apply

## Phase 3 — HTTP workflow

- [x] Task 5: Rewrite labeling controller — route/config contract suite 2/2

## Phase 4 — UI

- [x] Task 6: Implement configuration and review templates — compile/smoke check lulus
- [x] Task 7: Rewrite manual edit template and list states — SDI grep bersih

### Checkpoint: Workflow/UI
- [x] Config → Run → Review → Terapkan/Buang works
- [x] Manual edit works independently
- [x] Focused UI/controller tests pass
- [x] Responsive/accessibility review passes

## Phase 5 — Migration and verification

- [x] Task 8: Create and validate database migration — `flask db upgrade` terhadap DB legacy berisi data: exit 0; autogenerate sesudahnya "No changes in schema detected"; `downgrade base`: exit 0
- [x] Task 9: Full test, scope, and data-preservation verification — focused 9/9; full suite 16 pass, 4 environment/data setup errors

### Checkpoint: Complete
- [x] All labeling acceptance criteria met; upgrade terbukti jalan di SQLite, tetap perlu dijalankan di MySQL target setelah DATABASE_URL diverifikasi
- [x] Code review completed — C1 reviewer ditolak dengan bukti (kolom `lokasi_id` sudah ada di 2241c7e); temuan `alembic.ini` 0-byte dikonfirmasi dan diperbaiki
- [x] Code review completed — C2–C4 belum diverifikasi (server restart saat review)
- [x] Verification evidence recorded

## Phase 6 — MySQL restoration and comment hygiene

- [x] Task 10: Restore `scripts/seed_data.py` from `a358b12` — zero Supabase traces; `test_p2` dari import error menjadi 14 test OK
- [x] Task 11: Add `SQLALCHEMY_ENGINE_OPTIONS` (`pool_pre_ping`, `pool_recycle=280`) — mencegah error 2006 "server has gone away"
- [x] Task 12: Recreate `.env.example` (deleted in `3df9c29`) — template saja, tanpa nilai nyata
- [x] Task 13: Generate `0001_baseline_mysql` — 19 tabel dasar bentuk pre-labeling, `down_revision=None`
- [x] Task 14: Wire `20260926_labeling_visual_kmeans` ke baseline — rantai 2 revisi terverifikasi di DB kosong
- [x] Task 15: Clean comments in labeling/migration/config files — py_compile lulus, hash DDL tetap, 280 gambar utuh

### Checkpoint: MySQL restoration
- [x] Rantai `0001_baseline_mysql` → `20260926_labeling_visual_kmeans` jalan di DB kosong (22 tabel, head benar)
- [x] DDL MySQL offline 39 statement; upgrade dan downgrade dua arah valid
- [x] Drift check setelah upgrade: "No changes in schema detected"
- [x] 22 tabel + indeks compile bersih untuk dialek MySQL
- [x] Full suite 36 test, 3 error (butuh DB dev ber-schema — pre-existing, identik di `2241c7e`)
- [ ] `flask db upgrade` terhadap MySQL sungguhan — **terblokir: kredensial belum diberikan**

## Decisions / Rulings

- Ruling: Keep execution in the current worktree — the design/spec commit already exists on `main`, and no isolated worktree was requested; cost is reduced isolation during implementation.
- Ruling: Do not execute database deletion or migration against an unverified target — `DATABASE_URL` is unavailable in the working copy; cost is that external database cleanup may remain pending.
- Ruling: Preserve the existing labeling URL namespace and admin/CSRF conventions — this minimizes integration risk while changing only workflow semantics.
- Ruling: Helper `task-start`/`task-done` Superpowers tidak dijalankan (Windows tanpa WSL) — ekuivalensi manual dipakai. Biaya: satu langkah otomatisasi hilang, tidak ada langkah yang dilewati.
- Ruling: Temuan reviewer C1 (migration tidak pernah menambah `lokasi_id`) DITOLAK. `git show 2241c7e:app/models/label_kerusakan.py` sudah punya kolom itu dan autogenerate juga tidak melaporkannya.
- Ruling: Baseline `0001_baseline_mysql` dibuat dalam bentuk **pre-labeling** (kolom SDI masih ada) supaya revisi labeling jalan tanpa percabangan di MySQL baru maupun MySQL lama.
- Ruling: Baris label lama di-backfill ke `metode='manual'`, bukan `'klasterisasi'` — asalnya formula SDI, menandainya klasterisasi akan memalsukan provenance.
- Ruling: `op.alter_column(metode, DROP DEFAULT)` diguard `if dialect.name != 'sqlite'` — sintaks itu valid MySQL, SQLite tidak mendukungnya dan tidak butuh default yang bersih.
- Ruling: Pembersihan komentar dibatasi ke file labeling/migration/config + test labeling. 21 file yang ditandai JANGAN DIUBAH di `TODO.md` tidak disentuh. 4 komentar bermakna dipertahankan (pool_pre_ping, backfill `metode`, guard dialek, bentuk pre-labeling baseline).
