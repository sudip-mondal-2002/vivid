import cv2
import numpy as np
from .base import BaseEnhancer

class MoodyEnhancer(BaseEnhancer):
    """
    CINEMATIC: Dramatic movie feel.
    ISP: Teal/orange separation (shadows teal, highlights orange),
    add vignette. High contrast.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Exposure — slightly moody/dark
        if a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=105)

        # Teal/orange color separation
        img = self._teal_orange_grade(img)

        # Higher contrast — dramatic S-curve
        img = self.apply_clahe(img, clip_limit=1.3)
        img = self._apply_contrast_curve(img)

        # Slight saturation — cinematic isn't oversaturated
        img = self.adjust_saturation(img, scale=0.95)

        # Vignette for cinematic framing
        img = self._apply_vignette(img, strength=0.18)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _teal_orange_grade(self, image: np.ndarray) -> np.ndarray:
        """Push shadows teal, highlights orange — classic cinema LUT."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        shadow_mask = np.clip((128 - l) / 128, 0, 1)
        highlight_mask = np.clip((l - 128) / 128, 0, 1)
        # Shadows → teal (−a = green, −b = blue)
        a_ch = a_ch - shadow_mask * 6
        b_ch = b_ch - shadow_mask * 8
        # Highlights → orange (+a = red, +b = yellow)
        a_ch = a_ch + highlight_mask * 4
        b_ch = b_ch + highlight_mask * 7
        lab = cv2.merge([l, np.clip(a_ch, 0, 255), np.clip(b_ch, 0, 255)])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _apply_contrast_curve(self, image: np.ndarray) -> np.ndarray:
        """S-curve on luminance for dramatic contrast."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        l_norm = l / 255.0
        l_curved = 0.5 + (l_norm - 0.5) * 1.25
        l = np.clip(l_curved * 255, 0, 255)
        lab = cv2.merge([l, a_ch, b_ch])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _apply_vignette(self, image: np.ndarray, strength: float = 0.18) -> np.ndarray:
        """Cinematic vignette — darken edges."""
        rows, cols = image.shape[:2]
        X, Y = np.meshgrid(np.arange(cols), np.arange(rows))
        cx, cy = cols // 2, rows // 2
        radius = max(cx, cy) * 1.1
        dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
        vignette = 1 - strength * (dist / radius) ** 2
        vignette = np.clip(vignette, 0, 1)
        vignette_3d = np.stack([vignette] * 3, axis=-1)
        return (image.astype(np.float32) * vignette_3d).astype(np.uint8)
