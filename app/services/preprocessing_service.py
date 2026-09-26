import os
import time
import numpy as np
import cv2
from PIL import Image, ImageOps


class PreprocessingService:

    @staticmethod
    def _gray_world_white_balance(img):
        """Koreksi iluminasi gray-world: skalakan tiap kanal RGB supaya mean-nya sama
        dengan mean abu-abu keseluruhan — mengurangi variasi warna akibat pencahayaan
        beda antar sesi pemotretan lapangan."""
        arr = np.array(img, dtype=np.float32)
        means = arr.reshape(-1, 3).mean(axis=0)
        gray_mean = means.mean()
        means = np.where(means == 0, 1, means)   # cegah div/0 pada kanal hitam total
        scale = gray_mean / means
        arr = np.clip(arr * scale, 0, 255)
        return Image.fromarray(arr.astype(np.uint8))

    @staticmethod
    def run_pipeline_steps(img_path, config):
        """
        Jalankan pipeline 4 tahap (resize, crop, normalisasi, denoise) dan simpan hasil tiap tahap secara kumulatif.
        Kembalikan list of (step_key, PIL.Image, durasi_ms).
        Setiap gambar adalah hasil penerapan semua step sebelumnya + step ini.
        """
        results = []

        # ── Step 1: Resize (+ koreksi iluminasi opsional sebelum resize) ────
        t0 = time.time()
        img = Image.open(img_path)
        if str(config.resize_method) == 'LANCZOS_CV':
            img = ImageOps.exif_transpose(img)   # cv2.imread (notebook) menerapkan orientasi EXIF, Pillow tidak
        img = img.convert('RGB')
        if getattr(config, 'illum_correction', False):
            img = PreprocessingService._gray_world_white_balance(img)
        metode = str(config.resize_method)
        resample = getattr(Image.Resampling, metode, Image.Resampling.LANCZOS)
        target_w, target_h = int(config.target_width), int(config.target_height)
        if str(getattr(config, 'resize_mode', 'stretch')) == 'letterbox':
            # Jaga aspect ratio: resize supaya pas di dalam target box, lalu pad hitam di sisa ruang
            iw, ih = img.size
            scale = min(target_w / iw, target_h / ih)
            new_w, new_h = max(1, round(iw * scale)), max(1, round(ih * scale))
            resized = img.resize((new_w, new_h), resample)
            img = Image.new('RGB', (target_w, target_h), (0, 0, 0))
            img.paste(resized, ((target_w - new_w) // 2, (target_h - new_h) // 2))
        elif metode == 'LANCZOS_CV':
            # Sama dengan notebook: cv2.INTER_LANCZOS4 (tanpa antialias, beda dari LANCZOS Pillow).
            img = Image.fromarray(cv2.resize(np.array(img), (target_w, target_h), interpolation=cv2.INTER_LANCZOS4))
        else:
            img = img.resize((target_w, target_h), resample)
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
        elif norm == 'clahe':
            # CLAHE di kanal L (luminance) — kontras lokal naik tanpa merusak kontras
            # absolut antar foto seperti minmax/zscore global
            lab = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
            l = clahe.apply(l)
            lab = cv2.merge((l, a, b))
            img = Image.fromarray(cv2.cvtColor(lab, cv2.COLOR_LAB2RGB))
        # norm == 'none': gambar tetap sama, tetap simpan sebagai checkpoint
        results.append(('normalisasi', img.copy(), int((time.time() - t0) * 1000)))

        # ── Step 4: Denoise (OpenCV) — keluaran tahap ini yang dipakai training ──────────────────────────────────
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
            if method == 'nlmeans':
                # Persis notebook Colab: array RGB langsung ke fastNlMeansDenoisingColored (OpenCV
                # menganggapnya BGR), h=7, hColor=7, template 7, search 21. Tanpa konversi warna.
                img = Image.fromarray(cv2.fastNlMeansDenoisingColored(np.array(img), None, 7, 7, 7, 21))
            else:
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
