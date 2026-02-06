import cv2
import numpy as np
from .base import BaseEnhancer

class JungleEnhancer(BaseEnhancer):
    """
    JUNGLE: Lush, deep greens.
    ISP: Shift green hue towards cyan/emerald (not yellow), moderate contrast,
    lower exposure slightly to avoid blowing out bright leaves.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Lower exposure slightly — avoid blowing out sun-dappled leaves
        if a.mean_brightness > 130:
            img = self.adaptive_gamma(img, target_brightness=120)
        elif a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=110)

        # Shift green hue towards cyan/emerald (away from yellow)
        img = self._shift_greens_to_emerald(img)

        # Moderate contrast
        img = self.apply_clahe(img, clip_limit=1.2)

        # Lush saturation — greens pop
        img = self.adjust_saturation(img, scale=1.10)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _shift_greens_to_emerald(self, image: np.ndarray) -> np.ndarray:
        """Shift yellow-greens towards cyan/emerald for lush jungle look."""
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(np.float32)
        h, s, v = cv2.split(hsv)
        # Yellow-green (35-55) → shift towards true green/cyan
        yellow_green = ((h >= 35) & (h <= 55)).astype(np.float32)
        h = h + yellow_green * 8  # Push towards cyan/emerald
        # Boost saturation in all greens
        green_mask = ((h >= 35) & (h <= 85)).astype(np.float32)
        s = s + green_mask * 12
        hsv = cv2.merge([np.clip(h, 0, 179), np.clip(s, 0, 255), v]).astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
