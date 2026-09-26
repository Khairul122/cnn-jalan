"""Tahap Augmentasi (terpisah dari Preprocessing): menghasilkan salinan gambar dari hasil tahap denoise.

Transformasi setara 10 layer augmentasi Keras di `cnn_service/model.py` (flip horizontal, rotasi, zoom, translasi, brightness,
contrast, hue, saturasi, noise piksel, random erasing), tetapi dijalankan offline dengan RNG ber-seed sehingga hasilnya
reproducible. Tiap salinan membawa ID foto asal; kelas dan fold mengikuti foto asal.
"""
import copy
import os
import time

import cv2
import numpy as np
from PIL import Image

# Urutan sama dengan cnn_service.model.AUG_KEYS (dijaga oleh tes); tidak diimpor dari sana agar layanan ini tanpa TensorFlow.
KUNCI = ('flip', 'rotasi', 'zoom', 'translasi', 'brightness', 'contrast', 'hue', 'saturasi', 'noise', 'erasing')

DEFAULT_PARAMS = {
    'flip':       {'aktif': True, 'p': 0.5},
    'rotasi':     {'aktif': True, 'derajat': 18.0},
    'zoom':       {'aktif': True, 'faktor': 0.2},
    'translasi':  {'aktif': True, 'faktor': 0.1},
    'brightness': {'aktif': True, 'faktor': 0.3},
    'contrast':   {'aktif': True, 'faktor': 0.3},
    'hue':        {'aktif': True, 'faktor': 0.05},
    'saturasi':   {'aktif': True, 'faktor': 0.2},
    'noise':      {'aktif': True, 'sigma': 3.0},
    'erasing':    {'aktif': True, 'p': 0.5, 'luas_min': 0.02, 'luas_maks': 0.08},
}

AUGMENTED_SUBDIR = os.path.join('uploads', 'augmented')


def default_params():
    return copy.deepcopy(DEFAULT_PARAMS)


def normalisasi_params(params):
    """Lengkapi dengan default dan validasi tipe/rentang. ValueError bila tidak valid."""
    hasil = default_params()
    for kunci, nilai in (params or {}).items():
        if kunci not in hasil:
            raise ValueError(f'Transformasi augmentasi tidak dikenal: {kunci}')
        for k, v in nilai.items():
            if k not in hasil[kunci]:
                raise ValueError(f'Parameter {kunci}.{k} tidak dikenal')
            hasil[kunci][k] = bool(v) if k == 'aktif' else float(v)
    for kunci in ('flip', 'erasing'):
        if not 0 <= hasil[kunci]['p'] <= 1:
            raise ValueError(f'{kunci}.p harus di antara 0 dan 1')
    for kunci, k in (('zoom', 'faktor'), ('translasi', 'faktor'), ('brightness', 'faktor'), ('contrast', 'faktor'),
                     ('hue', 'faktor'), ('saturasi', 'faktor')):
        if not 0 <= hasil[kunci][k] <= 1:
            raise ValueError(f'{kunci}.{k} harus di antara 0 dan 1')
    if not 0 <= hasil['rotasi']['derajat'] <= 90:
        raise ValueError('rotasi.derajat harus di antara 0 dan 90')
    if hasil['noise']['sigma'] < 0:
        raise ValueError('noise.sigma tidak boleh negatif')
    e = hasil['erasing']
    if not 0 < e['luas_min'] <= e['luas_maks'] < 1:
        raise ValueError('erasing: 0 < luas_min <= luas_maks < 1')
    return hasil


def rng_untuk(seed, dokumentasi_id, salinan_ke):
    """RNG deterministik per (seed, foto, salinan): hasil sama di mesin mana pun dan tidak bergantung urutan proses."""
    return np.random.default_rng([int(seed), int(dokumentasi_id), int(salinan_ke)])


def augment_array(arr, params, rng):
    """arr: uint8 [H, W, 3] RGB. Return uint8 [H, W, 3]. Urutan transformasi sama dengan layer Keras di model."""
    p = params
    out = np.asarray(arr, dtype=np.float32)
    h, w = out.shape[:2]

    if p['flip']['aktif'] and rng.random() < p['flip']['p']:
        out = np.ascontiguousarray(out[:, ::-1])

    # Rotasi + zoom + translasi digabung dalam satu transformasi afin (tepi dicerminkan seperti fill 'reflect' Keras).
    sudut = rng.uniform(-p['rotasi']['derajat'], p['rotasi']['derajat']) if p['rotasi']['aktif'] else 0.0
    skala = 1.0 + rng.uniform(-p['zoom']['faktor'], p['zoom']['faktor']) if p['zoom']['aktif'] else 1.0
    tx = rng.uniform(-p['translasi']['faktor'], p['translasi']['faktor']) * w if p['translasi']['aktif'] else 0.0
    ty = rng.uniform(-p['translasi']['faktor'], p['translasi']['faktor']) * h if p['translasi']['aktif'] else 0.0
    if sudut or skala != 1.0 or tx or ty:
        m = cv2.getRotationMatrix2D((w / 2, h / 2), sudut, skala)
        m[:, 2] += (tx, ty)
        out = cv2.warpAffine(out, m, (w, h), flags=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT_101)

    if p['brightness']['aktif']:
        out = out + rng.uniform(-p['brightness']['faktor'], p['brightness']['faktor']) * 255.0
    if p['contrast']['aktif']:
        rata = out.mean()
        out = (out - rata) * rng.uniform(1 - p['contrast']['faktor'], 1 + p['contrast']['faktor']) + rata

    if p['hue']['aktif'] or p['saturasi']['aktif']:
        hsv = cv2.cvtColor(np.clip(out, 0, 255).astype(np.uint8), cv2.COLOR_RGB2HSV).astype(np.float32)
        if p['hue']['aktif']:   # OpenCV: hue 0..179 = 0..360 derajat
            hsv[..., 0] = (hsv[..., 0] + rng.uniform(-p['hue']['faktor'], p['hue']['faktor']) * 180.0) % 180.0
        if p['saturasi']['aktif']:
            hsv[..., 1] = np.clip(hsv[..., 1] * rng.uniform(1 - p['saturasi']['faktor'], 1 + p['saturasi']['faktor']), 0, 255)
        out = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2RGB).astype(np.float32)

    if p['noise']['aktif'] and p['noise']['sigma'] > 0:
        out = out + rng.normal(0.0, p['noise']['sigma'], out.shape)

    if p['erasing']['aktif'] and rng.random() < p['erasing']['p']:
        e = p['erasing']
        luas = rng.uniform(e['luas_min'], e['luas_maks']) * h * w
        rasio = float(np.exp(rng.uniform(np.log(0.3), np.log(3.3))))
        eh = int(min(h, max(1, round(np.sqrt(luas / rasio)))))
        ew = int(min(w, max(1, round(np.sqrt(luas * rasio)))))
        y0 = int(rng.integers(0, h - eh + 1))
        x0 = int(rng.integers(0, w - ew + 1))
        out[y0:y0 + eh, x0:x0 + ew, :] = rng.uniform(0, 255, size=3)

    return np.clip(out, 0, 255).astype(np.uint8)


def augment_image(img, params, rng):
    return Image.fromarray(augment_array(np.array(img.convert('RGB')), params, rng))


def _folder(root_static):
    folder = os.path.join(root_static, AUGMENTED_SUBDIR)
    os.makedirs(folder, exist_ok=True)
    return folder


def jalankan(config, root_static, doc_ids=None, on_progress=None):
    """
    Buat `config.n_salinan` salinan augmentasi untuk tiap foto (default: semua foto yang punya hasil denoise) dan
    simpan ke <root_static>/uploads/augmented/. Return {'foto': n, 'salinan': n, 'gagal': n}.
    Pemanggil bertanggung jawab menghapus hasil lama lebih dulu (invarian satu config aktif) dan commit.
    """
    from app import db
    from app.models.hasil_augmentasi import HasilAugmentasi
    from app.models.hasil_preprocessing import HasilPreprocessing
    from sqlalchemy import func

    params = normalisasi_params(config.get_parameter())
    q = (db.session.query(HasilPreprocessing.dokumentasi_id, func.max(HasilPreprocessing.path_output))
         .filter(HasilPreprocessing.step_name == 'denoise', HasilPreprocessing.status == 'selesai',
                 HasilPreprocessing.path_output != '')
         .group_by(HasilPreprocessing.dokumentasi_id).order_by(HasilPreprocessing.dokumentasi_id))
    if doc_ids is not None:
        q = q.filter(HasilPreprocessing.dokumentasi_id.in_(list(doc_ids)))
    sumber = q.all()

    folder = _folder(root_static)
    n_salinan = n_gagal = 0
    for i, (doc_id, path_rel) in enumerate(sumber):
        try:
            with Image.open(os.path.join(root_static, path_rel)) as im:
                asal = im.convert('RGB')
        except Exception as e:
            db.session.add(HasilAugmentasi(dokumentasi_id=doc_id, config_id=config.id, salinan_ke=0, path_output='',
                                           status='gagal', catatan=str(e)[:250]))
            n_gagal += 1
            continue
        for k in range(1, config.n_salinan + 1):
            hasil = augment_image(asal, params, rng_untuk(config.seed, doc_id, k))
            nama = f'{time.strftime("%Y%m%d%H%M%S")}_{doc_id}_a{k}.jpg'
            hasil.save(os.path.join(folder, nama), 'JPEG', quality=95)
            db.session.add(HasilAugmentasi(dokumentasi_id=doc_id, config_id=config.id, salinan_ke=k,
                                           path_output=f'uploads/augmented/{nama}'))
            n_salinan += 1
        if on_progress:
            on_progress(i + 1, len(sumber))
    db.session.flush()
    return {'foto': len(sumber), 'salinan': n_salinan, 'gagal': n_gagal}


def hapus_semua_hasil(root_static, query=None):
    """Hapus file dan record hasil augmentasi (semua, atau hasil `query`). Return (jumlah_record, jumlah_file)."""
    from app.models.hasil_augmentasi import HasilAugmentasi
    query = query if query is not None else HasilAugmentasi.query
    n_file = 0
    for h in query.filter(HasilAugmentasi.path_output != '').all():
        path = os.path.join(root_static, h.path_output)
        if os.path.isfile(path):
            try:
                os.remove(path)
                n_file += 1
            except OSError:
                pass
    return query.delete(synchronize_session=False), n_file
