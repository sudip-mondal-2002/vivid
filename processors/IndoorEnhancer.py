import cv2
import numpy as np
from .base import BaseEnhancer

class IndoorEnhancer(BaseEnhancer):
    """
    INDOOR: Correct poor lighting.
    ISP: Lift shadows significantly, auto-white balance is critical
    (fix tungsten/yellow casts).
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise first — indoor = high ISO = noise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise * 1.2)

        # Auto-white balance — CRITICAL for indoor (fix tungsten/yellow/fluorescent casts)
        img = self._auto_white_balance(img)

        # Exposure correction
        if a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=115)
        elif a.mean_brightness < 110:
            img = self.adaptive_gamma(img, target_brightness=118)

        # Lift shadows significantly — reveal room detail
        img = self._lift_shadows(img)

        # Gentle CLAHE
        img = self.apply_clahe(img, clip_limit=1.0)

        # Neutral saturation
        img = self.adjust_saturation(img, scale=1.03)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _auto_white_balance(self, image: np.ndarray) -> np.ndarray:
        """Gray-world auto WB — critical for indoor tungsten/fluorescent correction."""
        result = image.astype(np.float32)
        avg_r = np.mean(result[:, :, 0])
        avg_g = np.mean(result[:, :, 1])
        avg_b = np.mean(result[:, :, 2])
        avg_gray = (avg_r + avg_g + avg_b) / 3.0
        if avg_r > 0: result[:, :, 0] *= avg_gray / avg_r
        if avg_g > 0: result[:, :, 1] *= avg_gray / avg_g
        if avg_b > 0: result[:, :, 2] *= avg_gray / avg_b
        return np.clip(result, 0, 255).astype(np.uint8)

    def _lift_shadows(self, image: np.ndarray) -> np.ndarray:
        """Lift shadows significantly to reveal indoor detail."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        shadow_mask = np.clip((90 - l) / 90, 0, 1)
        l = l + shadow_mask * 30  # Significant shadow lift
        lab = cv2.merge([np.clip(l, 0, 255), a_ch, b_ch])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
