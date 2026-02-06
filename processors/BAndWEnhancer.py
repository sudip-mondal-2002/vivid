import cv2
import numpy as np
from .base import BaseEnhancer

class BAndWEnhancer(BaseEnhancer):
    """
    B&W: Classic monochrome.
    ISP: Saturation = 0, high contrast S-curve,
    apply red color filter before desaturating (darkens blue skies, brightens skin).
    """
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        a = self._analysis
        img = image.copy()

        # Denoise
        if a.recommended_denoise > 0:
            img = self.denoise_adaptive(img, strength=a.recommended_denoise)

        # Exposure correction before conversion
        if a.is_low_light:
            img = self.adaptive_gamma(img, target_brightness=115)

        # Apply RED filter before desaturating
        # Red filter: darkens blue skies, brightens warm tones (skin, lips)
        bw = self._red_filter_bw(img)

        # High contrast S-curve
        bw = self._apply_s_curve(bw)

        # Gentle CLAHE for tonal richness
        clahe = cv2.createCLAHE(clipLimit=1.5, tileGridSize=(8, 8))
        bw = clahe.apply(bw)

        # Convert back to 3-channel RGB for output pipeline
        return cv2.cvtColor(bw, cv2.COLOR_GRAY2RGB)

    def _red_filter_bw(self, image: np.ndarray) -> np.ndarray:
        """Red filter B&W: heavy red weight darkens blues, brightens warm tones."""
        r, g, b = cv2.split(image.astype(np.float32))
        # Red filter mix: emphasize red, reduce blue
        bw = r * 0.50 + g * 0.35 + b * 0.15
        return np.clip(bw, 0, 255).astype(np.uint8)

    def _apply_s_curve(self, bw: np.ndarray) -> np.ndarray:
        """High-contrast S-curve for dramatic B&W."""
        lut = np.zeros(256, dtype=np.uint8)
        for i in range(256):
            n = i / 255.0
            # Strong S-curve: tanh with steepness 3.5
            curved = 0.5 * (1 + np.tanh(3.5 * (n - 0.5)))
            lut[i] = int(curved * 255)
        return cv2.LUT(bw, lut)
