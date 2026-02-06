import cv2
import numpy as np
from .base import BaseEnhancer

class SnowEnhancer(BaseEnhancer):
    """
    SNOW: True white snow (not gray or blue).
    ISP: Overexpose +0.5 to +1.0 (camera meters see white → darkens to gray),
    shift temp slightly warm to counteract blue shadows, default neutral.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # OVEREXPOSE: cameras underexpose snow (gray target). Push up +0.5 to +1.0 stop.
        # Target brightness well above average to make snow white, not gray.
        target = min(a.mean_brightness + 40, 175)  # +40 ≈ +0.7 stop
        img = self.adaptive_gamma(img, target_brightness=target)

        # Counteract blue shadow cast — slight warm shift
        img = self._warm_blue_shadows(img)

        # Gentle CLAHE — don't crush the whites
        img = self.apply_clahe(img, clip_limit=0.8)

        # Neutral saturation — snow should be clean white
        img = self.adjust_saturation(img, scale=1.02)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _warm_blue_shadows(self, image: np.ndarray) -> np.ndarray:
        """Counteract blue cast in snow shadows by warming them."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        # Only in shadow areas (low L) push b towards warm
        shadow_mask = np.clip((100 - l) / 100, 0, 1)
        b_ch = b_ch + shadow_mask * 8  # +b = yellow/warm
        lab = cv2.merge([l, a_ch, np.clip(b_ch, 0, 255)])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
