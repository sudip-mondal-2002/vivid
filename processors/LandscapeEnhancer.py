import cv2
import numpy as np
from .base import BaseEnhancer

class LandscapeEnhancer(BaseEnhancer):
    """
    LANDSCAPE: High dynamic range and lush colors.
    ISP: Lower highlights (recover sky), lift shadows (reveal foreground),
    boost saturation globally, slight sharpness for foliage.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Exposure — balance, don't blow out
        if a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=115)

        # Lower highlights (recover sky) + lift shadows (reveal foreground)
        img = self._compress_dynamic_range(img)

        # Gentle CLAHE for tonal depth
        img = self.apply_clahe(img, clip_limit=1.2)

        # Boost saturation globally — lush colors
        img = self.adjust_saturation(img, scale=1.12)

        # Slight sharpness for foliage detail
        if a.noise_level < 8:
            img = self.unsharp_mask(img, sigma=1.0, strength=0.4, threshold=4)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _compress_dynamic_range(self, image: np.ndarray) -> np.ndarray:
        """Lower highlights, lift shadows — pseudo-HDR tone mapping."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)

        # Shadow lift: boost dark pixels
        shadow_mask = np.clip((90 - l) / 90, 0, 1)
        l = l + shadow_mask * 25  # Lift shadows

        # Highlight recovery: compress bright pixels
        highlight_mask = np.clip((l - 180) / 75, 0, 1)
        l = l - highlight_mask * 20  # Pull down highlights

        lab = cv2.merge([np.clip(l, 0, 255), a_ch, b_ch])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
