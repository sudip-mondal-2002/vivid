import cv2
import numpy as np
from .base import BaseEnhancer

class ArchitectureEnhancer(BaseEnhancer):
    """
    ARCHITECTURE: Geometric precision and detail.
    ISP: High clarity/structure to emphasize lines, higher contrast,
    neutralize white balance (remove color casts from artificial lights).
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Exposure correction
        if a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=115)

        # Neutralize white balance — remove artificial light color casts
        img = self._neutralize_wb(img)

        # Higher contrast via CLAHE
        img = self.apply_clahe(img, clip_limit=1.5)

        # High clarity/structure — large-radius high-pass for line emphasis
        img = self._add_clarity(img)

        # Keep saturation neutral/clean
        img = self.adjust_saturation(img, scale=1.0)

        # Sharpening for geometric detail
        if a.noise_level < 10:
            img = self.unsharp_mask(img, sigma=1.0, strength=0.5, threshold=3)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _neutralize_wb(self, image: np.ndarray) -> np.ndarray:
        """Remove color casts by pulling a/b channels toward neutral."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        a_ch = a_ch * 0.75 + 128 * 0.25
        b_ch = b_ch * 0.75 + 128 * 0.25
        lab = cv2.merge([l, np.clip(a_ch, 0, 255), np.clip(b_ch, 0, 255)])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _add_clarity(self, image: np.ndarray) -> np.ndarray:
        """Large-radius high-pass on luminance = clarity/structure for lines."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        blurred = cv2.GaussianBlur(l, (0, 0), 8)
        high_pass = cv2.subtract(l, blurred)
        l = cv2.add(l, cv2.multiply(high_pass, 0.35))
        lab = cv2.merge([np.clip(l, 0, 255).astype(np.uint8), a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
