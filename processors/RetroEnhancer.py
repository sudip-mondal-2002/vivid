import cv2
import numpy as np
from .base import BaseEnhancer

class RetroEnhancer(BaseEnhancer):
    """
    RETRO: Nostalgic/film look.
    ISP: Lift black point (faded blacks), add grain,
    shift colors towards green/yellow, slightly desaturated.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise (light — we're adding grain back anyway)
        if a.recommended_denoise > 2:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise * 0.5)

        # Exposure correction
        if a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=110)

        # Lift black point — faded blacks (signature retro look)
        img = self._fade_blacks(img)

        # Shift colors towards green/yellow
        img = self._shift_green_yellow(img)

        # Slightly desaturated
        img = self.adjust_saturation(img, scale=0.82)

        # Add film grain
        img = self._add_grain(img, intensity=6.0)

        # Soft vignette
        img = self._apply_vignette(img, strength=0.20)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _fade_blacks(self, image: np.ndarray) -> np.ndarray:
        """Lift the black point — shadows never go to true black."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        # Compress from below: black point at ~20 instead of 0
        l = l * 0.88 + 20
        lab = cv2.merge([np.clip(l, 0, 255), a_ch, b_ch])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _shift_green_yellow(self, image: np.ndarray) -> np.ndarray:
        """Shift overall color cast towards green/yellow (vintage film)."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        a_ch = a_ch - 3   # −a = green shift
        b_ch = b_ch + 5   # +b = yellow shift
        lab = cv2.merge([l, np.clip(a_ch, 0, 255), np.clip(b_ch, 0, 255)])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _add_grain(self, image: np.ndarray, intensity: float = 6.0) -> np.ndarray:
        """Add monochromatic film grain."""
        h, w = image.shape[:2]
        grain = np.random.normal(0, intensity, (h, w)).astype(np.float32)
        grain_3d = np.stack([grain] * 3, axis=-1)
        return np.clip(image.astype(np.float32) + grain_3d, 0, 255).astype(np.uint8)

    def _apply_vignette(self, image: np.ndarray, strength: float = 0.20) -> np.ndarray:
        rows, cols = image.shape[:2]
        X, Y = np.meshgrid(np.arange(cols), np.arange(rows))
        cx, cy = cols // 2, rows // 2
        radius = max(cx, cy) * 1.2
        dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        vig = np.clip(1 - strength * (dist / radius) ** 2, 0, 1)
        vig_3d = np.stack([vig] * 3, axis=-1)
        return (image.astype(np.float32) * vig_3d).astype(np.uint8)
