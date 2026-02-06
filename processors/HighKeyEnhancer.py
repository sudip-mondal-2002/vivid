import cv2
import numpy as np
from .base import BaseEnhancer

class HighKeyEnhancer(BaseEnhancer):
    """
    BRIGHT: Airy, clean, lifestyle look.
    ISP: High exposure, low contrast (flatten the image),
    slightly desaturated shadows.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # High exposure — bright, airy feel
        target = min(a.mean_brightness + 30, 165)
        img = self.adaptive_gamma(img, target_brightness=target)

        # Low contrast — flatten the image (blend towards midgray)
        img = self._reduce_contrast(img, strength=0.12)

        # Very gentle CLAHE
        img = self.apply_clahe(img, clip_limit=0.6)

        # Slightly desaturate shadows for clean lifestyle look
        img = self._desaturate_shadows(img)

        # Global: very subtle desaturation
        img = self.adjust_saturation(img, scale=0.96)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _reduce_contrast(self, image: np.ndarray, strength: float = 0.12) -> np.ndarray:
        """Flatten contrast by blending towards midgray."""
        result = image.astype(np.float32) * (1 - strength) + 128.0 * strength
        return np.clip(result, 0, 255).astype(np.uint8)

    def _desaturate_shadows(self, image: np.ndarray) -> np.ndarray:
        """Desaturate shadow regions for clean, airy look."""
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(np.float32)
        h, s, v = cv2.split(hsv)
        # Shadow mask: dark pixels
        shadow_mask = np.clip((80 - v) / 80, 0, 1)
        s = s * (1 - shadow_mask * 0.3)  # Reduce saturation in shadows
        hsv = cv2.merge([h, np.clip(s, 0, 255), v]).astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
