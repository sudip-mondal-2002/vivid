import cv2
import numpy as np
from .base import BaseEnhancer

class PortraitEnhancer(BaseEnhancer):
    """
    PORTRAIT: Flattering skin tones, focus on face.
    ISP: +0.1 exposure, reduce clarity on skin, sharpen eyes/hair,
    protect orange/red channels from over-saturation ("sunburn" guard).
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise first - clean skin is priority
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Slight exposure lift (+0.1 stop ≈ target ~135 from 128)
        img = self.adaptive_gamma(img, target_brightness=max(a.mean_brightness + 8, 130))

        # Reduce clarity on skin (bilateral = softens texture but keeps edges)
        skin_mask, skin_ratio = self.detect_skin_tones(img)
        if skin_ratio > 0.03:
            img = self._soften_skin(img, skin_mask)
            # Sharpen NON-skin (eyes, hair, lashes)
            img = self._sharpen_non_skin(img, skin_mask)

        # Gentle CLAHE - avoid emphasizing pores
        img = self.apply_clahe(img, clip_limit=0.8)

        # CRITICAL: Protect orange/red from over-saturation
        img = self._protect_warm_channels(img)

        # Very subtle global saturation
        img = self.adjust_saturation(img, scale=1.03)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _soften_skin(self, image: np.ndarray, skin_mask: np.ndarray) -> np.ndarray:
        """Reduce clarity/texture on skin regions (bilateral filter)."""
        soft_mask = cv2.GaussianBlur(skin_mask, (31, 31), 0)
        mask_norm = soft_mask.astype(np.float32) / 255.0
        smoothed = cv2.bilateralFilter(image, d=9, sigmaColor=55, sigmaSpace=55)
        mask_3d = np.stack([mask_norm] * 3, axis=-1)
        return (smoothed * mask_3d + image.astype(np.float32) * (1 - mask_3d)).astype(np.uint8)

    def _sharpen_non_skin(self, image: np.ndarray, skin_mask: np.ndarray) -> np.ndarray:
        """Sharpen eyes, hair, lashes — everything outside skin."""
        inv_mask = cv2.bitwise_not(skin_mask)
        soft_inv = cv2.GaussianBlur(inv_mask, (21, 21), 0).astype(np.float32) / 255.0
        sharpened = self.unsharp_mask(image, sigma=0.8, strength=0.5, threshold=4)
        mask_3d = np.stack([soft_inv] * 3, axis=-1)
        return (sharpened.astype(np.float32) * mask_3d + image.astype(np.float32) * (1 - mask_3d)).astype(np.uint8)

    def _protect_warm_channels(self, image: np.ndarray) -> np.ndarray:
        """Clamp orange/red saturation to prevent 'sunburn' look."""
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype(np.float32)
        h, s, v = cv2.split(hsv)
        # Orange/red hue range (0-25 and 160-180)
        warm_mask = ((h <= 25) | (h >= 160)).astype(np.float32)
        # Cap saturation in warm regions at current level (don't let it increase)
        max_warm_sat = 160.0
        s = np.where((warm_mask > 0) & (s > max_warm_sat), max_warm_sat, s)
        hsv = cv2.merge([h, s, v]).astype(np.uint8)
        return cv2.cvtColor(hsv, cv2.COLOR_HSV2RGB)
