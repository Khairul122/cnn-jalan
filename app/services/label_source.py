"""Satu sumber untuk pertanyaan "apa dan berapa label tingkat kerusakan sekarang".

Historis: label hanya ada di `label_kerusakan` dan baru terisi setelah endpoint
"Terapkan" dijalankan, padahal hasil klasterisasi (`hasil_labeling_item`) sudah
final sejak run selesai. Akibatnya halaman split bisa melihat 0 foto berlabel
padahal labeling sudah jalan, dan setiap konsumen harus diingatkan untuk membaca
tabel yang sama.

Modul ini menyatukannya. Semua konsumen — split, cek label basi, prediksi massal,
dashboard — memanggil `label_map()` sehingga angkanya tidak pernah berbeda antar
halaman.

Prioritas per lokasi, yang pertama menang:

  1. label manual (``metode='manual'``) — keputusan manusia tetap override hasil
     klasterisasi, sesuai peran "edit manual" di halaman Labeling Visual.
  2. item run klasterisasi terakhir yang ``status == 'selesai'`` — sumber utama.
  3. label hasil Terapkan (``metode='klasterisasi'``) — cadangan bila run asalnya
     sudah dihapus (lihat ``label.run_delete``) atau belum ada run sama sekali.
"""
from collections import Counter

from app.models.hasil_labeling import HasilLabeling
from app.models.hasil_labeling_item import HasilLabelingItem
from app.models.label_kerusakan import LabelKerusakan


def active_run(run_id=None):
    """Run klasterisasi terbaru yang selesai, atau None bila belum ada."""
    if run_id is not None:
        return HasilLabeling.query.filter(
            HasilLabeling.id == run_id, HasilLabeling.status == 'selesai'
        ).first()
    return (
        HasilLabeling.query
        .filter(HasilLabeling.status == 'selesai')
        .order_by(HasilLabeling.id.desc())
        .first()
    )


def label_map(run=None):
    """Return {lokasi_id: tingkat_kerusakan_id} untuk lokasi yang punya label efektif.

    `run` opsional: bila None dipakai run selesai terbaru. Query-nya dua kali
    (label_kerusakan + item run) sehingga aman dipanggil berulang dalam satu request.
    """
    if run is None:
        run = active_run()

    rows = LabelKerusakan.query.with_entities(
        LabelKerusakan.lokasi_id,
        LabelKerusakan.tingkat_kerusakan_id,
        LabelKerusakan.metode,
    ).all()

    # 3. label hasil Terapkan / legacy lebih dulu, supaya kalah dari run & manual
    labels = {l: t for l, t, m in rows if m != 'manual' and t}

    if run is not None:                          # 2. hasil klasterisasi = sumber utama
        for item in HasilLabelingItem.query.filter_by(run_id=run.id):
            if item.tingkat_kerusakan_id:
                labels[item.lokasi_id] = item.tingkat_kerusakan_id

    # 1. override manusia menang atas keduanya
    labels.update({l: t for l, t, m in rows if m == 'manual' and t})

    return labels


def per_class(run=None):
    """Return Counter {tingkat_kerusakan_id: jumlah lokasi} dari label efektif."""
    return Counter(label_map(run).values())
