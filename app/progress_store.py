"""Store progres run background, thread-safe, per kunci.

Dipakai bersama oleh controller yang menjalankan proses panjang di thread
(split, preprocessing, augmentasi, arsitektur, klasifikasi) supaya UI bisa
polling persen nyata tanpa tiap controller menulis sendiri kunci lock-nya.

Nilai HARUS skalar/JSON-safe — objek ORM & datetime tidak boleh masuk sini.
"""
import threading


class ProgressStore:
    """Dict dengan lock. Nilai diganti utuh, bukan dimutasi di tempat."""

    def __init__(self):
        self._data = {}
        self._lock = threading.Lock()

    def set(self, key, data):
        with self._lock:
            self._data[key] = data

    def get(self, key):
        with self._lock:
            return self._data.get(key)

    def snapshot(self):
        """Salinan seluruh isi store (untuk endpoint ringkasan)."""
        with self._lock:
            return dict(self._data)

    def pop(self, key, default=None):
        with self._lock:
            return self._data.pop(key, default)

    def clear(self):
        with self._lock:
            self._data.clear()

    def sederhanakan(self, key, **fields):
        """Update sebagian field dari data yang sudah ada (kalau ada)."""
        with self._lock:
            cur = dict(self._data.get(key) or {})
            cur.update(fields)
            self._data[key] = cur
            return cur
