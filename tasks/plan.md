# Implementation Plan: Visual K-Means Labeling Rewrite

## Overview
Mengganti labeling SDI berbasis dimensi lokasi dengan labeling berbasis fitur visual foto jalan: MobileNetV2 embedding + Canny edge density + StandardScaler + PCA + K-Means. Workflow otomatis menjadi Config → Run → Review → Terapkan/Buang. Label manual tetap tersedia sebagai override. Perubahan dibatasi pada subsistem labeling, migrasi yang diperlukan, dan test labeling.

Referensi desain yang disetujui: `docs/superpowers/specs/2026-09-25-kmeans-labeling-rewrite-design.md`.

## Constraints
- Pertahankan semua source code, template, konfigurasi, dan file gambar.
- Jangan ubah CNN, preprocessing, augmentasi, split, dedup, metrics, evaluasi, klasifikasi, peta, dashboard, auth, lokasi, arsitektur, `app/kelas.py`, atau test yang tidak terkait SDI.
- Default wajib: image 224x224, MobileNetV2, Canny 50/150, PCA 50, K-Means k=4, `random_state=42`, `n_init=10`.
- Mapping tingkat tetap: `1=Rusak Berat`, `2=Rusak Ringan`, `3=Sedang`, `4=Baik`.
- Run otomatis tidak boleh mengubah `LabelKerusakan` sebelum aksi Terapkan.
- Semua input route divalidasi dan semua operasi mutasi mengikuti proteksi admin/CSRF aplikasi.

## File Map

### Existing files to modify
- `app/models/label_kerusakan.py`: hapus kontrak SDI; simpan metadata label manual/klasterisasi.
- `app/models/lokasi_kerusakan.py`: ubah nama relationship label lama menjadi relationship netral bila diperlukan.
- `app/models/__init__.py`: import model labeling baru.
- `app/controllers/label_controller.py`: implementasikan route Config → Run → Review → Terapkan/Buang dan manual edit.
- `app/templates/label/index.html`: daftar lokasi, status label, konfigurasi, run terbaru, empty/error states.
- `app/templates/label/edit.html`: form tingkat kerusakan manual dan catatan; hapus field SDI.
- `tests/test_p2.py`: hapus hanya test formula SDI lama.

### New files
- `app/models/labeling_config.py`: konfigurasi parameter labeling.
- `app/models/hasil_labeling.py`: satu eksekusi labeling dan status penerapan.
- `app/models/hasil_labeling_item.py`: hasil per lokasi dalam satu run.
- `app/services/labeling_service.py`: ekstraksi fitur, agregasi, clustering, mapping, persistence, apply, discard.
- `app/templates/label/config_form.html`: create/edit konfigurasi.
- `app/templates/label/review.html`: review run dan tindakan Terapkan/Buang.
- `tests/test_labeling_service.py`: unit/integration tests untuk kontrak labeling.
- migration file di `migrations/versions/` jika Flask-Migrate tersedia.

## Dependency Graph

1. Test contract dan model schema
2. Feature/clustering service
3. Persistence/apply/discard service
4. Controller routes
5. Templates/UI
6. Migration and full verification

Controller depends on service contracts; templates depend on route names and view context. Migration must be created only after model metadata stabilizes.

## Task List

### Phase 1 — Foundation and schema

#### Task 1: Establish failing labeling contract tests
**Description:** Tambahkan test yang mendefinisikan default parameter, mapping cluster berdasarkan edge density, skip foto invalid, determinisme, dan run yang belum diterapkan. Hapus test SDI lama yang tidak lagi valid tanpa mengubah test lain.

**Acceptance criteria:**
- [ ] Test menyatakan default 224x224, Canny 50/150, PCA 50, k=4, seed 42, n_init 10.
- [ ] Test menyatakan mapping edge density ascending ke ID 4, 3, 2, 1.
- [ ] Test menyatakan lokasi tanpa foto valid dilewati dengan alasan.
- [ ] Test menyatakan hasil run tidak langsung membuat/mengubah `LabelKerusakan`.
- [ ] Test gagal secara bermakna karena implementasi baru belum ada.

**Verification:** `python -m unittest tests.test_labeling_service -v` dan pastikan failure berasal dari fitur yang belum diimplementasikan.

**Dependencies:** None.

**Files likely touched:** `tests/test_labeling_service.py`, `tests/test_p2.py`.

**Estimated scope:** Small.

#### Task 2: Implement labeling models and relationships
**Description:** Buat tiga model baru dan rewrite `LabelKerusakan` agar mendukung label manual/klasterisasi, foreign keys, timestamps, dan cascade item run. Sesuaikan relationship lokasi jika dibutuhkan tanpa mengubah model domain lain.

**Acceptance criteria:**
- [ ] Semua model dapat diimpor melalui `app.models`.
- [ ] Field SDI dan method SDI tidak ada lagi pada `LabelKerusakan`.
- [ ] Enum/metode, cluster metadata, run reference, config fields, status, dan distribution JSON tersedia sesuai spec.
- [ ] Relationship/cascade memungkinkan item run dibuang tanpa orphan.

**Verification:** import check dan focused model tests; `python -m unittest tests.test_labeling_service -v` masih boleh gagal hanya pada service.

**Dependencies:** Task 1.

**Files likely touched:** `app/models/label_kerusakan.py`, `app/models/lokasi_kerusakan.py`, `app/models/labeling_config.py`, `app/models/hasil_labeling.py`, `app/models/hasil_labeling_item.py`, `app/models/__init__.py`.

**Estimated scope:** Medium.

### Checkpoint: Foundation
- [ ] Model imports succeed.
- [ ] No out-of-scope files changed.
- [ ] Focused tests fail only for unimplemented service behavior.

### Phase 2 — Algorithm and persistence

#### Task 3: Implement feature extraction and clustering core
**Description:** Implement pure/testable helpers and service orchestration for image loading, MobileNetV2 embedding, Canny edge density, per-location aggregation, StandardScaler, PCA, K-Means, centroid distance, and semantic mapping.

**Acceptance criteria:**
- [ ] Valid images use 224x224 RGB and the required MobileNetV2 contract.
- [ ] Canny uses configured low/high thresholds and normalized edge density.
- [ ] Invalid/missing images do not abort the entire run.
- [ ] PCA component count is safely bounded by available samples/features while preserving configured default when possible.
- [ ] K-Means uses `n_init=10`, configured seed, and deterministic cluster ordering by mean edge density.
- [ ] No label database write occurs in the clustering core.

**Verification:** mocked embedding/image tests; `python -m unittest tests.test_labeling_service -v`.

**Dependencies:** Task 2.

**Files likely touched:** `app/services/labeling_service.py`, `tests/test_labeling_service.py`.

**Estimated scope:** Medium.

#### Task 4: Implement run persistence, apply, and discard
**Description:** Persist temporary run/items, expose summary and skip reasons, atomically apply results to `LabelKerusakan`, and discard runs idempotently.

**Acceptance criteria:**
- [ ] Completed run stores items and distribution but leaves labels untouched.
- [ ] Apply upserts one label per location and marks run applied in one transaction.
- [ ] Repeated apply does not duplicate labels or corrupt metadata.
- [ ] Discard removes run/items and does not modify existing labels.
- [ ] Failed/no-valid-photo run has a user-readable reason and cannot be applied.

**Verification:** database-backed service tests using the repository’s test app/database setup.

**Dependencies:** Task 3.

**Files likely touched:** `app/services/labeling_service.py`, `tests/test_labeling_service.py`.

**Estimated scope:** Medium.

### Checkpoint: Algorithm
- [ ] Focused labeling tests pass.
- [ ] Mocked tests prove defaults and deterministic mapping.
- [ ] Existing label rows remain unchanged until apply.

### Phase 3 — HTTP workflow

#### Task 5: Rewrite labeling controller
**Description:** Replace SDI/automatic-label routes with config CRUD, synchronous run, review, apply, discard, manual edit, and existing label deletion routes where required.

**Acceptance criteria:**
- [ ] Config routes validate numeric bounds and preserve defaults.
- [ ] Run route creates a temporary run and redirects to review.
- [ ] Review route exposes run summary, items, distribution, and skipped locations.
- [ ] Apply/discard are admin-only POST actions with CSRF and safe status checks.
- [ ] Manual edit accepts only valid level IDs and notes; it no longer computes SDI.
- [ ] Removed route names/symbols are absent from controller.

**Verification:** Flask test-client route tests for permissions, redirects, validation, apply/discard, and manual edit.

**Dependencies:** Task 4.

**Files likely touched:** `app/controllers/label_controller.py`, `tests/test_labeling_service.py` or a focused controller test file.

**Estimated scope:** Medium.

### Phase 4 — UI

#### Task 6: Implement configuration and review templates
**Description:** Add accessible, responsive templates for config create/edit and run review, following the existing application tokens and antislop DURING rules.

**Acceptance criteria:**
- [ ] Forms have labels, error messaging, visible focus, CSRF, and keyboard-operable controls.
- [ ] Review clearly distinguishes temporary results from applied labels.
- [ ] Apply and discard are explicit actions with confirmation and disabled/invalid states represented server-side.
- [ ] Tables/cards/galeries reflow without horizontal overflow on narrow screens.
- [ ] No decorative controls, invented metrics, or SDI terminology remains.

**Verification:** render tests plus browser smoke test if app/database environment is available; inspect mobile layout manually.

**Dependencies:** Task 5.

**Files likely touched:** `app/templates/label/config_form.html`, `app/templates/label/review.html`, `app/templates/label/index.html`.

**Estimated scope:** Medium.

#### Task 7: Rewrite manual edit template and list states
**Description:** Replace SDI input form with manual level dropdown/notes and update index copy/status actions to the new workflow.

**Acceptance criteria:**
- [ ] Manual edit shows location photos/context and level choices with correct semantic names.
- [ ] Existing manual/cluster metadata is visible without presenting SDI fields.
- [ ] Index has empty state, no-label state, latest-run state, and actionable links.
- [ ] Templates contain no SDI labels, fields, or route references.

**Verification:** template render tests and grep for `sdi`, `SDI`, `auto_label`, and `hitung-sdi` in labeling templates.

**Dependencies:** Task 6.

**Files likely touched:** `app/templates/label/edit.html`, `app/templates/label/index.html`.

**Estimated scope:** Medium.

### Checkpoint: Workflow/UI
- [ ] Config → Run → Review → Terapkan/Buang works through Flask test client.
- [ ] Manual edit works independently of automatic runs.
- [ ] Focused UI/controller tests pass.
- [ ] Responsive/accessibility review finds no blocking issue.

### Phase 5 — Migration, cleanup, and final verification

#### Task 8: Create and validate database migration
**Description:** Generate or write the migration for the new labeling schema, inspect upgrade/downgrade operations, and do not execute against an unavailable or unverified `DATABASE_URL`.

**Acceptance criteria:**
- [ ] Migration creates new tables/columns and removes only obsolete labeling schema fields as intended.
- [ ] Foreign-key ordering and cascade behavior are valid.
- [ ] Migration does not silently delete unrelated application data.
- [ ] Upgrade/downgrade can be inspected or run against an isolated test database.

**Verification:** migration check command available in the repo; isolated upgrade/downgrade smoke test. If `DATABASE_URL` is unavailable, report rather than guessing.

**Dependencies:** Tasks 2–4.

**Files likely touched:** `migrations/versions/*` and migration config only if required.

**Estimated scope:** Medium.

#### Task 9: Full test, scope, and data-preservation verification
**Description:** Run the complete suite, static checks, SDI-reference grep, git diff scope check, and image/non-image inventory.

**Acceptance criteria:**
- [ ] `python -m unittest discover tests` passes or every environment limitation is documented.
- [ ] `git diff --check` passes.
- [ ] No old SDI symbols/routes remain in labeling code, templates, or tests.
- [ ] No protected module was modified.
- [ ] All retained image extensions/files remain; approved non-image data artifacts remain removed.
- [ ] Database cleanup status is explicitly reported based on verified connection availability.

**Verification:** full command set from the final verification checklist.

**Dependencies:** Tasks 5–8.

**Files likely touched:** none expected; verification artifacts only if needed.

**Estimated scope:** Small.

### Checkpoint: Complete
- [ ] All acceptance criteria met.
- [ ] Code review completed across correctness, readability, architecture, security, and performance.
- [ ] Verification evidence recorded before claiming completion.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| MobileNetV2 weights unavailable or expensive in tests | High | Mock model in unit tests; keep runtime failure user-readable; use existing dependency versions. |
| PCA/K-Means constraints fail with few locations | High | Validate minimum samples and bound PCA components; create failed run instead of partial labels. |
| Existing database schema differs from models | High | Inspect migration and isolated DB first; never guess `DATABASE_URL`; do not auto-delete unrelated data. |
| Existing templates rely on implicit relationship name | Medium | Search all references before renaming; preserve compatibility alias if needed within labeling scope. |
| UI actions accidentally apply automatically | High | Service contract and route tests assert labels remain unchanged until explicit apply. |
| Working tree contains user files | Medium | Inspect status/diff before every destructive or broad edit; modify only mapped files. |

## Open Decisions
- Execution method after plan approval: native inline execution or subagent-driven execution.
- Database cleanup remains conditional on a verifiable `DATABASE_URL`; no credential or target guessing.
