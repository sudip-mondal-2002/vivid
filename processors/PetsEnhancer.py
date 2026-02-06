import cv2
import numpy as np
from .base import BaseEnhancer

class PetsEnhancer(BaseEnhancer):
    """
    PETS: Detail in fur/feathers.
    ISP: High texture/structure to emphasize fur, neutral WB,
    slight contrast boost to separate subject from background.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise first
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Neutral exposure
        if a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=120)

        # Neutral white balance — pull a/b channels towards center
        img = self._neutralize_wb(img)

        # High texture/structure: local contrast on L channel (small grid = micro-contrast)
        img = self._enhance_fur_structure(img)

        # Slight contrast boost to separate subject from background
        img = self.apply_clahe(img, clip_limit=1.2)

        # Neutral saturation — keep colors true to life
        img = self.adjust_saturation(img, scale=1.02)

        # Sharpening tuned for fur detail (slightly higher sigma for texture)
        if a.noise_level < 10:
            img = self.unsharp_mask(img, sigma=1.2, strength=0.5, threshold=3)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _neutralize_wb(self, image: np.ndarray) -> np.ndarray:
        """Pull white balance towards neutral by centering a/b channels."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        # Gently pull a and b towards 128 (neutral) by 20%
        a_ch = a_ch * 0.8 + 128 * 0.2
        b_ch = b_ch * 0.8 + 128 * 0.2
        lab = cv2.merge([l, np.clip(a_ch, 0, 255), np.clip(b_ch, 0, 255)])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _enhance_fur_structure(self, image: np.ndarray) -> np.ndarray:
        """High-pass micro-contrast on luminance for fur/feather texture."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        # Small-radius high-pass = texture/structure
        blurred = cv2.GaussianBlur(l, (0, 0), 2.0)
        high_pass = cv2.subtract(l, blurred)
        l = cv2.add(l, cv2.multiply(high_pass, 0.4))
        lab = cv2.merge([np.clip(l, 0, 255).astype(np.uint8), a, b])
        return cv2.cvtColor(lab, cv2.COLOR_LAB2RGB)
