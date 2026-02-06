import cv2
import numpy as np
from .base import BaseEnhancer

class CityEnhancer(BaseEnhancer):
    """
    CITY: Urban grit and energy.
    ISP: Higher contrast, slightly desaturated colors ("bleach bypass" feel),
    increased structure.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Exposure — slightly moody
        if a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=105)

        # Higher contrast — CLAHE + S-curve
        img = self.apply_clahe(img, clip_limit=1.5)
        img = self._apply_contrast_curve(img)

        # Increased structure (high-pass clarity)
        img = self._add_structure(img)

        # Bleach bypass: slightly desaturated
        img = self.adjust_saturation(img, scale=0.88)

        # Sharpening for urban detail
        if a.noise_level < 10:
            img = self.unsharp_mask(img, sigma=1.0, strength=0.45, threshold=3)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _apply_contrast_curve(self, image: np.ndarray) -> np.ndarray:
        """S-curve on luminance for higher contrast."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        l_norm = l / 255.0
        l_curved = 0.5 + (l_norm - 0.5) * 1.2  # Mild S-curve
        l = np.clip(l_curved * 255, 0, 255)
        lab = cv2.merge([l, a_ch, b_ch])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _add_structure(self, image: np.ndarray) -> np.ndarray:
        """High-pass micro-contrast for urban texture."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        blurred = cv2.GaussianBlur(l, (0, 0), 4)
        high_pass = cv2.subtract(l, blurred)
        l = cv2.add(l, cv2.multiply(high_pass, 0.3))
        lab = cv2.merge([np.clip(l, 0, 255).astype(np.uint8), a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
