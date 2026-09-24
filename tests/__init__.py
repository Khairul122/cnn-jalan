"""Paket tes. Bila TEST_DATABASE_URL diset, semua tes memakai database itu (bukan DATABASE_URL utama/Supabase)."""
import os

if os.environ.get('TEST_DATABASE_URL'):
    os.environ['DATABASE_URL'] = os.environ['TEST_DATABASE_URL']
