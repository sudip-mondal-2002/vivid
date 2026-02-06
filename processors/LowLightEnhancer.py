import cv2
import numpy as np
from .base import BaseEnhancer

class LowLightEnhancer(BaseEnhancer):
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        """
        NIGHT: Visibility without noise.
        ISP: Lift exposure slightly, keep blacks crushed (hide noise),
        reduce saturation slightly (night vision is less colorful), noise reduction.
        """
        a = self._analysis
        img = image.copy()

        darkness_level = np.clip(1.0 - (a.mean_brightness / 128.0), 0, 1)

        # Heavy denoise FIRST — night = high ISO noise
        img = self._adaptive_denoise(img, darkness_level, a.sharpness)

        # Lift exposure slightly — but not too much
        target = min(a.mean_brightness + 20, 115)
        img = self.adaptive_gamma(img, target_brightness=target)

        # Crush blacks — hide remaining noise in shadows
        img = self._crush_blacks(img)

        # Gentle CLAHE — don't amplify noise
        img = self.apply_clahe(img, clip_limit=min(a.recommended_clahe_clip, 1.2))

        # Reduce saturation slightly — night vision is less colorful
        img = self.adjust_saturation(img, scale=0.92)

        # Final bilateral pass to clean up noise revealed by brightening
        img = cv2.bilateralFilter(img, d=5, sigmaColor=25, sigmaSpace=25)

        return np.clip(img, 0, 255).astype(np.uint8)

    def _crush_blacks(self, image: np.ndarray) -> np.ndarray:
        """Crush the deepest shadows to hide noise."""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB).astype(np.float32)
        l, a_ch, b_ch = cv2.split(lab)
        # Push very dark pixels towards true black
        dark_mask = np.clip((30 - l) / 30, 0, 1)
        l = l * (1 - dark_mask * 0.5)  # Darken deepest shadows further
        lab = cv2.merge([np.clip(l, 0, 255), a_ch, b_ch])
        return cv2.cvtColor(lab.astype(np.uint8), cv2.COLOR_LAB2RGB)
    
    def _protect_skin_in_lowlight(self, image: np.ndarray, skin_mask: np.ndarray) -> np.ndarray:
        """Apply gentler processing to skin regions in low light."""
        def gentle_smooth(img):
            return cv2.bilateralFilter(img, d=9, sigmaColor=60, sigmaSpace=60)
        
        return self.apply_to_region(image, skin_mask, gentle_smooth)

    def _adaptive_denoise(self, image: np.ndarray, darkness: float, sharpness: float) -> np.ndarray:
        """Apply adaptive denoising based on image characteristics."""
        bgr = cv2.cvtColor(image, cv2.COLOR_RGB2BGR)
        
        # Stronger denoising for darker, noisier images
        h_luminance = int(5 + darkness * 10)  # 5-15
        h_color = int(5 + darkness * 8)  # 5-13
        
        # Preserve detail in sharper images
        if sharpness > 300:
            h_luminance = max(3, h_luminance - 3)
            h_color = max(3, h_color - 2)
        
        template_window = 7
        search_window = 21
        
        denoised = cv2.fastNlMeansDenoisingColored(
            bgr, None, h_luminance, h_color, template_window, search_window
        )
        return cv2.cvtColor(denoised, cv2.COLOR_BGR2RGB)

    def _exposure_fusion(self, image: np.ndarray, a) -> np.ndarray:
        """Create exposure fusion from multiple virtual exposures."""
        img_float = image.astype(np.float32) / 255.0
        
        # Create brighter virtual exposures
        exposures = [img_float]
        
        # Calculate needed boost based on analysis
        if a.mean_brightness < 40:
            boost_factors = [2.0, 3.5, 5.0]
        elif a.mean_brightness < 80:
            boost_factors = [1.5, 2.5, 3.5]
        else:
            boost_factors = [1.3, 1.8, 2.3]
        
        for factor in boost_factors:
            boosted = np.clip(img_float * factor, 0, 1)
            exposures.append(boosted)
        
        # Weight by well-exposedness (prefer mid-tones)
        weights = []
        for exp in exposures:
            gray = np.mean(exp, axis=2)
            # Gaussian centered at 0.5 (mid-tone)
            weight = np.exp(-((gray - 0.5) ** 2) / (2 * 0.2 ** 2))
            weights.append(weight)
        
        # Normalize weights
        weight_sum = np.sum(weights, axis=0) + 1e-8
        weights = [w / weight_sum for w in weights]
        
        # Blend exposures
        result = np.zeros_like(img_float)
        for exp, weight in zip(exposures, weights):
            result += exp * weight[:, :, np.newaxis]
        
        return (np.clip(result, 0, 1) * 255).astype(np.uint8)

    def _preserve_highlights(self, enhanced: np.ndarray, original: np.ndarray) -> np.ndarray:
        """Blend back original highlights to prevent blowout."""
        gray_orig = cv2.cvtColor(original, cv2.COLOR_RGB2GRAY)
        
        # Create mask for bright regions in original
        highlight_mask = (gray_orig > 200).astype(np.float32)
        highlight_mask = cv2.GaussianBlur(highlight_mask, (15, 15), 0)
        
        # Blend
        mask_3d = np.stack([highlight_mask] * 3, axis=-1)
        result = enhanced * (1 - mask_3d * 0.5) + original * (mask_3d * 0.5)
        return result.astype(np.uint8)

    def _auto_white_balance(self, image: np.ndarray) -> np.ndarray:
        """Apply gray world auto white balance."""
        result = image.astype(np.float32)
        
        avg_r = np.mean(result[:, :, 0])
        avg_g = np.mean(result[:, :, 1])
        avg_b = np.mean(result[:, :, 2])
        avg_gray = (avg_r + avg_g + avg_b) / 3
        
        if avg_r > 0:
            result[:, :, 0] = result[:, :, 0] * (avg_gray / avg_r)
        if avg_g > 0:
            result[:, :, 1] = result[:, :, 1] * (avg_gray / avg_g)
        if avg_b > 0:
            result[:, :, 2] = result[:, :, 2] * (avg_gray / avg_b)
        
        return np.clip(result, 0, 255).astype(np.uint8)
