import cv2
import numpy as np
from .base import BaseEnhancer

class GeneralEnhancer(BaseEnhancer):
    """
    STANDARD: True-to-life.
    ISP: Zero adjustments or very mild auto-levels. Denoise only.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise if needed — keep it clean
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img)

        # Very mild auto-levels: only correct if clearly off
        if a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=112)
        elif a.mean_brightness < 95:
            img = self.adaptive_gamma(img, target_brightness=110)

        # Minimal CLAHE — just enough to not look flat
        img = self.apply_clahe(img, clip_limit=0.8)

        # True-to-life saturation — almost no change
        img = self.adjust_saturation(img, scale=1.02)

        return np.clip(img, 0, 255).astype(np.uint8)
