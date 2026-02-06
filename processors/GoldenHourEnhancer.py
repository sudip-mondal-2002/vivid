import cv2
import numpy as np
from .base import BaseEnhancer

class GoldenHourEnhancer(BaseEnhancer):
    """
    SUNSET: Amplify golden hour colors.
    ISP: Shift temp to warm (yellow/red), shift tint to magenta,
    lower highlights to preserve sun disk, boost vibrance.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Shift temperature warm (yellow/red) + tint towards magenta
        img = self._warm_and_magenta(img)

        # Lower highlights — preserve sun disk detail
        img = self._lower_highlights(img)

        # Gentle CLAHE
        img = self.apply_clahe(img, clip_limit=1.0)

        # Boost vibrance — amplify golden hour colors
        img = self._boost_vibrance(img, strength=0.2)

        # Saturation boost for sunset warmth
        img = self.adjust_saturation(img, scale=1.10)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _warm_and_magenta(self, image: np.ndarray) -> np.ndarray:
        """Shift temp warm (+b) and tint magenta (+a) in LAB."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        a_ch = a_ch + 4   # +a = magenta tint
        b_ch = b_ch + 8   # +b = warm/yellow
        lab = cv2.merge([l, np.clip(a_ch, 0, 255), np.clip(b_ch, 0, 255)])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _lower_highlights(self, image: np.ndarray) -> np.ndarray:
        """Compress highlights to preserve sun disk and sky gradients."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        highlight_mask = np.clip((l - 180) / 75, 0, 1)
        l = l - highlight_mask * 25
        lab = cv2.merge([np.clip(l, 0, 255), a_ch, b_ch])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _boost_vibrance(self, image: np.ndarray, strength: float = 0.2) -> np.ndarray:
        """Vibrance: boost under-saturated pixels more."""
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(np.float32)
        h, s, v = cv2.split(hsv)
        boost = strength * (1.0 - s / 255.0)
        s = s * (1.0 + boost)
        hsv = cv2.merge([h, np.clip(s, 0, 255), v]).astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
