import cv2
import numpy as np
from .base import BaseEnhancer

class FoodEnhancer(BaseEnhancer):
    """
    FOOD: Make it look appetizing.
    ISP: Increase saturation & vibrance significantly, shift temperature warmer,
    slightly increased exposure.
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Slightly increased exposure — food should look bright and inviting
        img = self.adaptive_gamma(img, target_brightness=max(a.mean_brightness + 10, 135))

        # Shift temperature warmer (warm food > cold food)
        img = self._warm_temperature(img)

        # Gentle CLAHE for food texture
        img = self.apply_clahe(img, clip_limit=1.0)

        # Boost vibrance (saturate under-saturated pixels more than already-saturated)
        img = self._boost_vibrance(img, strength=0.25)

        # Increase saturation significantly for appetizing colors
        img = self.adjust_saturation(img, scale=1.15)

        # Light sharpening for texture
        if a.noise_level < 8:
            img = self.unsharp_mask(img, sigma=0.8, strength=0.35, threshold=4)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _warm_temperature(self, image: np.ndarray) -> np.ndarray:
        """Shift color temperature warmer via LAB b-channel."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        # Warm shift: +b = yellow, +a = slight red warmth
        b_ch = b_ch + 6
        a_ch = a_ch + 2
        lab = cv2.merge([l, np.clip(a_ch, 0, 255), np.clip(b_ch, 0, 255)])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)

    def _boost_vibrance(self, image: np.ndarray, strength: float = 0.25) -> np.ndarray:
        """Vibrance: boost saturation of less-saturated pixels more than already-saturated ones."""
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(np.float32)
        h, s, v = cv2.split(hsv)
        # Inverse relationship: low-sat pixels get more boost
        boost = strength * (1.0 - s / 255.0)
        s = s * (1.0 + boost)
        hsv = cv2.merge([h, np.clip(s, 0, 255), v]).astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
