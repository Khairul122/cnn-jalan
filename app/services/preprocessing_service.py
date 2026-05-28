import os
import time
import random
import numpy as np
import cv2
from PIL import Image, ImageOps, ImageEnhance


class PreprocessingService:

    @staticmethod
    def run_pipeline_steps(img_path, config):
        """
        Jalankan pipeline 5 tahap dan simpan hasil tiap tahap secara kumulatif.
        Kembalikan list of (step_key, PIL.Image, durasi_ms).
        Setiap gambar adalah hasil penerapan semua step sebelumnya + step ini.
        """
        results = []

        # ── Step 1: Resize ────────────────────────────────────────────
        t0 = time.time()
        img = Image.open(img_path).convert('RGB')
        resample = getattr(Image.Resampling, str(config.resize_method), Image.Resampling.LANCZOS)
        img = img.resize((int(config.target_width), int(config.target_height)), resample)
        results.append(('resize', img.copy(), int((time.time() - t0) * 1000)))

        # ── Step 2: Center Crop ───────────────────────────────────────
        t0 = time.time()
        if config.crop_enabled:
            cw, ch = int(config.crop_width), int(config.crop_height)
            iw, ih = img.size
            left = max(0, (iw - cw) // 2)
            top  = max(0, (ih - ch) // 2)
            img  = img.crop((left, top, left + min(cw, iw), top + min(ch, ih)))
        results.append(('crop', img.copy(), int((time.time() - t0) * 1000)))

        # ── Step 3: Normalisasi (visual representasi, disimpan sebagai uint8) ──
        t0 = time.time()
        arr = np.array(img, dtype=np.float32)
        norm = str(config.norm_method)
        if norm == 'minmax':
            # Per-channel min-max stretch ke rentang penuh [0, 255]
            for c in range(arr.shape[2]):
                ch_min, ch_max = arr[:, :, c].min(), arr[:, :, c].max()
                if ch_max > ch_min:
                    arr[:, :, c] = (arr[:, :, c] - ch_min) / (ch_max - ch_min) * 255
            img = Image.fromarray(arr.astype(np.uint8))
        elif norm == 'zscore':
            # Z-score global lalu rescale ke [0, 255] untuk display
            mean, std = arr.mean(), arr.std()
            if std > 0:
                arr = (arr - mean) / std
                arr = np.clip((arr + 3) / 6 * 255, 0, 255)
            img = Image.fromarray(arr.astype(np.uint8))
        # norm == 'none': gambar tetap sama, tetap simpan sebagai checkpoint
        results.append(('normalisasi', img.copy(), int((time.time() - t0) * 1000)))

        # ── Step 4: Augmentasi (random per gambar) ────────────────────
        t0 = time.time()
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
        results.append(('augmentasi', img.copy(), int((time.time() - t0) * 1000)))

        # ── Step 5: Denoise (OpenCV) ──────────────────────────────────
        t0 = time.time()
        method = str(config.denoise_method)
        if method != 'none':
            k = int(config.denoise_ksize or 3)
            k = k if k % 2 == 1 else k + 1
            cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
            if method == 'gaussian':
                cv_img = cv2.GaussianBlur(cv_img, (k, k), 0)
            elif method == 'median':
                cv_img = cv2.medianBlur(cv_img, k)
            elif method == 'bilateral':
                cv_img = cv2.bilateralFilter(cv_img, k, 75, 75)
            img = Image.fromarray(cv2.cvtColor(cv_img, cv2.COLOR_BGR2RGB))
        results.append(('denoise', img.copy(), int((time.time() - t0) * 1000)))

        return results

    @staticmethod
    def run_pipeline(img_path, config):
        """Jalankan pipeline penuh dan kembalikan hanya output akhir (backward compat)."""
        steps = PreprocessingService.run_pipeline_steps(img_path, config)
        final_img, durasi_ms = steps[-1][1], sum(s[2] for s in steps)
        meta = {'width': final_img.width, 'height': final_img.height, 'durasi_ms': durasi_ms}
        return final_img, meta

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
