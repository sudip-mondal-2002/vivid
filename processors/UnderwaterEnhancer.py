import cv2
import numpy as np
from .base import BaseEnhancer

class UnderwaterEnhancer(BaseEnhancer):
    """
    UNDERWATER: Correct color absorption.
    ISP: HEAVY addition of red and magenta (compensate water absorbing red light),
    increase contrast significantly (underwater photos are flat/hazy).
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise — underwater photos are often noisy
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise * 1.2)

        # HEAVY red + magenta compensation via channel manipulation
        img = self._restore_red_channel(img)

        # Shift tint towards magenta in LAB (counteract green cast)
        img = self._add_magenta_tint(img)

        # Increase contrast significantly — underwater photos are flat
        img = self.apply_clahe(img, clip_limit=2.0)

        # Saturation boost to bring back colors lost to water
        img = self.adjust_saturation(img, scale=1.2)

        # Sharpening to counter water diffusion
        if a.noise_level < 12:
            img = self.unsharp_mask(img, sigma=1.0, strength=0.5, threshold=3)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _restore_red_channel(self, image: np.ndarray) -> np.ndarray:
        """Heavy red channel boost to compensate water absorbing red light."""
        r, g, b = cv2.split(image.astype(np.float32))
        # Add flat offset + multiplicative boost to red
        r = r + 40
        r = r * 1.25
        # Slightly reduce blue to counter blue haze
        b = b * 0.90
        return cv2.merge([np.clip(r, 0, 255), g, np.clip(b, 0, 255)]).astype(np.uint8)

    def _add_magenta_tint(self, image: np.ndarray) -> np.ndarray:
        """Shift towards magenta/red in LAB to counter green underwater cast."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        a_ch = a_ch + 8  # +a = magenta/red (away from green)
        lab = cv2.merge([l, np.clip(a_ch, 0, 255), b_ch])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
