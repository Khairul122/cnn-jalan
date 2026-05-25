import os
import time
import random
import numpy as np
import cv2
from PIL import Image, ImageOps, ImageEnhance


class PreprocessingService:

    @staticmethod
    def run_pipeline(img_path, config):
        """
        Jalankan 5 tahap preprocessing: Resize → Center Crop → Normalisasi → Augmentasi → Denoise.
        Kembalikan (PIL.Image hasil, dict meta, durasi_ms).
        Raise Exception jika gagal.
        """
        t0 = time.time()

        # ── Step 1: Resize ────────────────────────────────────────────
        img = Image.open(img_path).convert('RGB')
        resample = getattr(Image.Resampling, str(config.resize_method), Image.Resampling.LANCZOS)
        img = img.resize((int(config.target_width), int(config.target_height)), resample)

        # ── Step 2: Center Crop ───────────────────────────────────────
        if config.crop_enabled:
            cw, ch = int(config.crop_width), int(config.crop_height)
            iw, ih = img.size
            left = max(0, (iw - cw) // 2)
            top  = max(0, (ih - ch) // 2)
            img  = img.crop((left, top, left + min(cw, iw), top + min(ch, ih)))

        # ── Step 3: Normalisasi ───────────────────────────────────────
        # Normalisasi statistik (minmax/zscore) tidak disimpan ke file karena
        # JPEG hanya bisa menyimpan uint8 [0–255]. Normalisasi untuk CNN
        # dilakukan otomatis oleh preprocess_input() saat load_dataset().
        # Step ini dicatat sebagai metadata konfigurasi saja.

        # ── Step 4: Augmentasi (random per gambar) ────────────────────
        if config.aug_flip_h and random.random() < 0.5:
            img = ImageOps.mirror(img)
        if config.aug_flip_v and random.random() < 0.5:
            img = ImageOps.flip(img)
        deg = float(config.aug_rotate_deg or 0)
        if deg != 0:
            angle = random.uniform(-deg, deg)
            img = img.rotate(angle, expand=False, fillcolor=(0, 0, 0))
        brightness = float(config.aug_brightness or 1.0)
        if brightness != 1.0:
            factor = random.uniform(1.0 / brightness, brightness)
            img = ImageEnhance.Brightness(img).enhance(factor)
        contrast = float(config.aug_contrast or 1.0)
        if contrast != 1.0:
            factor = random.uniform(1.0 / contrast, contrast)
            img = ImageEnhance.Contrast(img).enhance(factor)

        # ── Step 5: Denoise (OpenCV) ──────────────────────────────────
        method = str(config.denoise_method)
        if method != 'none':
            k = int(config.denoise_ksize or 3)
            k = k if k % 2 == 1 else k + 1   # kernel harus ganjil
            cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            if method == 'gaussian':
                cv_img = cv2.GaussianBlur(cv_img, (k, k), 0)
            elif method == 'median':
                cv_img = cv2.medianBlur(cv_img, k)
            elif method == 'bilateral':
                cv_img = cv2.bilateralFilter(cv_img, k, 75, 75)
            img = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))

        durasi_ms = int((time.time() - t0) * 1000)
        meta = {
            'width': img.width,
            'height': img.height,
            'durasi_ms': durasi_ms,
        }
        return img, meta

    @staticmethod
    def save_result(img, output_path):
        """Simpan PIL Image ke file JPEG."""
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        img.save(output_path, 'JPEG', quality=95)

    @staticmethod
    def get_file_kb(path):
        """Kembalikan ukuran file dalam KB, atau None jika tidak ada."""
        try:
            return max(1, os.path.getsize(path) // 1024)
        except OSError:
            return None
