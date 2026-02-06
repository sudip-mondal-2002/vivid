import cv2
import numpy as np
from .base import BaseEnhancer

class SeascapeEnhancer(BaseEnhancer):
    """
    OCEAN: Emphasize blues and aquas.
    ISP: Shift tint towards green/cyan, specific saturation boost to blue channels,
    brighten highlights (sparkles on water).
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Exposure
        if a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=120)

        # Shift tint towards green/cyan in LAB
        img = self._shift_tint_cyan(img)

        # Specific saturation boost to blue/cyan channels
        img = self._boost_blue_saturation(img)

        # Brighten highlights — sparkles on water
        img = self._brighten_highlights(img)

        # Gentle CLAHE
        img = self.apply_clahe(img, clip_limit=1.0)

        # Global saturation — slightly boosted for vivid ocean
        img = self.adjust_saturation(img, scale=1.08)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _shift_tint_cyan(self, image: np.ndarray) -> np.ndarray:
        """Shift tint towards green/cyan via LAB a-channel (negative a = green)."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        a_ch = a_ch - 4  # Shift towards green/cyan
        b_ch = b_ch - 3  # Shift towards blue
        lab = cv2.merge([l, np.clip(a_ch, 0, 255), np.clip(b_ch, 0, 255)])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _boost_blue_saturation(self, image: np.ndarray) -> np.ndarray:
        """Selectively boost saturation in blue/cyan hue range."""
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(np.float32)
        h, s, v = cv2.split(hsv)
        blue_mask = ((h >= 80) & (h <= 130)).astype(np.float32)
        s = s + blue_mask * 20  # Boost blue/cyan saturation
        hsv = cv2.merge([h, np.clip(s, 0, 255), v]).astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)

    def _brighten_highlights(self, image: np.ndarray) -> np.ndarray:
        """Brighten existing highlights — water sparkles."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        highlight_mask = np.clip((l - 170) / 85, 0, 1)
        l = l + highlight_mask * 10
        lab = cv2.merge([np.clip(l, 0, 255), a_ch, b_ch])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
