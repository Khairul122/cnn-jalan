# Migrasi SQL lama (dialek MySQL) — arsip

Skema sekarang dikelola Alembic (`migrations/`, jalankan `flask db upgrade`) dan basis datanya Postgres (Supabase).
File di folder ini hanya rujukan sejarah perubahan skema MySQL; jangan dijalankan.
Data lama dipindahkan dengan `scripts/migrate_mysql_to_supabase.py`.
