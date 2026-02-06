from abc import ABC, abstractmethod
from typing import Optional, Callable
from dataclasses import dataclass, field
import rawpy
import cv2
import numpy as np
from io import BytesIO
from .enums import OutputFormat


@dataclass
class ImageAnalysis:
    """Comprehensive image analysis results for adaptive processing."""
    # Brightness
    mean_brightness: float = 128.0
    brightness_std: float = 50.0
    dark_ratio: float = 0.0
    bright_ratio: float = 0.0
    is_low_light: bool = False
    is_high_key: bool = False
    
    # Color
    mean_saturation: float = 100.0
    is_saturated: bool = False
    is_desaturated: bool = False
    green_ratio: float = 0.0
    blue_ratio: float = 0.0
    warm_ratio: float = 0.0
    dominant_hue: str = "neutral"
    color_temperature: str = "neutral"  # warm, cool, neutral
    
    # Detail
    sharpness: float = 300.0
    edge_density: float = 0.05
    is_sharp: bool = False
    is_blurry: bool = False
    has_fine_detail: bool = False
    noise_level: float = 0.0
    
    # Regions
    has_sky: bool = False
    sky_ratio: float = 0.0
    has_faces: bool = False
    face_count: int = 0
    skin_ratio: float = 0.0
    has_vegetation: bool = False
    has_water: bool = False
    
    # Adaptive parameters (computed from analysis)
    recommended_clahe_clip: float = 2.0
    recommended_saturation: float = 1.0
    recommended_sharpening: float = 1.0
    recommended_denoise: float = 0.0
    
    # Region masks
    sky_mask: np.ndarray = field(default=None, repr=False)
    skin_mask: np.ndarray = field(default=None, repr=False)
    vegetation_mask: np.ndarray = field(default=None, repr=False)
    water_mask: np.ndarray = field(default=None, repr=False)
    foreground_mask: np.ndarray = field(default=None, repr=False)


class BaseEnhancer(ABC):
    def __init__(self, file_bytes: bytes, progress_callback: Optional[Callable[[str, int, str], None]] = None):
        self.raw_data = file_bytes
        self.rgb_image = None
        self._progress_callback = progress_callback
        self._analysis: Optional[ImageAnalysis] = None
    
    def _report_progress(self, stage: str, percent: int, message: str):
        """Report progress to callback if available."""
        if self._progress_callback:
            self._progress_callback(stage, percent, message)
        
    def process(self, output_format: OutputFormat = OutputFormat.JPG) -> bytes:
        """
        Template Method: Defines the skeletal workflow.
        """
        self._report_progress("loading_raw", 10, "Loading RAW file...")
        self._load_and_convert_raw()
        
        self._report_progress("analyzing", 30, "Analyzing image characteristics...")
        self._analysis = self.analyze_image(self.rgb_image)
        
        self._report_progress("enhancing", 40, "Applying intelligent enhancements...")
        enhanced_image = self._apply_enhancement_logic(self.rgb_image)
        
        self._report_progress("encoding", 85, "Encoding final image...")
        result = self._encode_image(enhanced_image, output_format)
        
        self._report_progress("complete", 100, "Enhancement complete!")
        return result

    def _load_and_convert_raw(self):
        with rawpy.imread(BytesIO(self.raw_data)) as raw:
            # Postprocess: high quality, auto white balance
            self.rgb_image = raw.postprocess(
                use_camera_wb=True, 
                bright=1.0, 
                no_auto_bright=False
            )

    def get_original_preview(self) -> bytes:
        """Get a JPG preview of the original RAW (no enhancements) for comparison."""
        if self.rgb_image is None:
            self._load_and_convert_raw()
        
        # Resize for preview (max 1080px on longest side)
        h, w = self.rgb_image.shape[:2]
        max_dim = 1080
        if max(h, w) > max_dim:
            scale = max_dim / max(h, w)
            new_w, new_h = int(w * scale), int(h * scale)
            preview = cv2.resize(self.rgb_image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        else:
            preview = self.rgb_image
        
        # Convert RGB to BGR and encode as JPG
        bgr = cv2.cvtColor(preview, cv2.COLOR_RGB2BGR)
        _, encoded = cv2.imencode('.jpg', bgr, [cv2.IMWRITE_JPEG_QUALITY, 85])
        return encoded.tobytes()

    @abstractmethod
    def _apply_enhancement_logic(self, image: np.ndarray) -> np.ndarray:
        """Subclasses must implement this specific logic."""
        pass

    def _encode_image(self, image: np.ndarray, fmt: OutputFormat) -> bytes:
        # Optimize for Instagram story (1080x1920 max, intelligent compression)
        optimized = self._optimize_for_instagram(image)
        
        # Convert RGB to BGR for OpenCV
        bgr_image = cv2.cvtColor(optimized, cv2.COLOR_RGB2BGR)
        
        if fmt == OutputFormat.PNG:
            _, encoded = cv2.imencode('.png', bgr_image, [cv2.IMWRITE_PNG_COMPRESSION, 6])
        else:
            # Intelligent quality based on image content
            quality = self._calculate_optimal_quality(optimized)
            _, encoded = cv2.imencode('.jpg', bgr_image, [
                cv2.IMWRITE_JPEG_QUALITY, quality,
                cv2.IMWRITE_JPEG_OPTIMIZE, 1,
                cv2.IMWRITE_JPEG_PROGRESSIVE, 1
            ])
            
        return encoded.tobytes()
    
    def _calculate_optimal_quality(self, image: np.ndarray) -> int:
        """
        Intelligently determine JPEG quality based on image characteristics.
        - High detail images (landscapes, architecture) need higher quality
        - Smooth images (portraits, sky) can use lower quality without visible loss
        - Target: Best visual quality while staying Instagram-friendly (<10MB)
        """
        detail = self.analyze_detail(image)
        color = self.analyze_color(image)
        
        # Base quality
        quality = 88
        
        # High detail images need more quality (fine textures, edges)
        if detail['sharpness'] > 800 or detail['edge_density'] > 0.15:
            quality = 92
        elif detail['sharpness'] > 400:
            quality = 90
        
        # Highly saturated images compress worse - boost quality
        if color['mean_saturation'] > 120:
            quality = min(quality + 2, 95)
        
        # Smooth images (low detail) can use lower quality
        if detail['sharpness'] < 200 and detail['edge_density'] < 0.05:
            quality = max(quality - 3, 85)
        
        return quality
    
    def _optimize_for_instagram(self, image: np.ndarray) -> np.ndarray:
        """
        Optimize image for Instagram story upload.
        - Max resolution: 1080x1920 (9:16 portrait) or fit within bounds
        - Maintains aspect ratio
        - Applies adaptive sharpening based on content
        """
        h, w = image.shape[:2]
        
        # Instagram story max dimensions
        MAX_WIDTH = 1080
        MAX_HEIGHT = 1920
        
        # Calculate scale to fit within bounds
        scale = min(MAX_WIDTH / w, MAX_HEIGHT / h, 1.0)
        
        if scale < 1.0:
            new_w = int(w * scale)
            new_h = int(h * scale)
            # Use LANCZOS for high-quality downscaling
            image = cv2.resize(image, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)
        
        return image
    
    def _adaptive_instagram_sharpen(self, image: np.ndarray) -> np.ndarray:
        """
        Adaptive sharpening optimized for Instagram compression.
        Adjusts sharpening strength based on image detail level.
        """
        detail = self.analyze_detail(image)
        
        # Already sharp images need less sharpening
        if detail['sharpness'] > 600:
            strength = 0.08
            sigma = 0.6
        # Medium detail
        elif detail['sharpness'] > 300:
            strength = 0.12
            sigma = 0.8
        # Low detail images benefit from more sharpening
        else:
            strength = 0.18
            sigma = 1.0
        
        blurred = cv2.GaussianBlur(image, (0, 0), sigma)
        sharpened = cv2.addWeighted(image, 1.0 + strength, blurred, -strength, 0)
        return np.clip(sharpened, 0, 255).astype(np.uint8)

    # --- Shared Toolkit for Subclasses ---
    
    def apply_clahe(self, image, clip_limit=2.0, grid_size=(8,8)):
        """Contrast Limited Adaptive Histogram Equalization on L-channel"""
        lab = cv2.cvtColor(image, cv2.COLOR_RGB2LAB)
        l, a, b = cv2.split(lab)
        clahe = cv2.createCLAHE(clipLimit=clip_limit, tileGridSize=grid_size)
        l = clahe.apply(l)
        merged = cv2.merge((l, a, b))
        return cv2.cvtColor(merged, cv2.COLOR_LAB2RGB)

    def adjust_saturation(self, image, scale=1.0):
        if scale == 1.0: return image
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV).astype("float32")
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] * scale, 0, 255)
        return cv2.cvtColor(hsv.astype("uint8"), cv2.COLOR_HSV2RGB)

    # --- Image Analysis Toolkit ---
    
    def analyze_brightness(self, image: np.ndarray) -> dict:
        """Analyze image brightness characteristics."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        mean_brightness = np.mean(gray)
        std_brightness = np.std(gray)
        dark_ratio = np.sum(gray < 50) / gray.size
        bright_ratio = np.sum(gray > 200) / gray.size
        return {
            "mean": mean_brightness,
            "std": std_brightness,
            "dark_ratio": dark_ratio,
            "bright_ratio": bright_ratio,
            "is_low_light": mean_brightness < 80,
            "is_high_key": mean_brightness > 180,
            "dynamic_range": std_brightness
        }

    def analyze_color(self, image: np.ndarray) -> dict:
        """Analyze color characteristics."""
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        h, s, v = cv2.split(hsv)
        mean_saturation = np.mean(s)
        
        # Detect dominant hue regions
        green_mask = ((h >= 35) & (h <= 85) & (s > 40)).astype(np.uint8)
        blue_mask = ((h >= 90) & (h <= 130) & (s > 40)).astype(np.uint8)
        warm_mask = (((h <= 30) | (h >= 160)) & (s > 40)).astype(np.uint8)
        
        return {
            "mean_saturation": mean_saturation,
            "is_saturated": mean_saturation > 100,
            "is_desaturated": mean_saturation < 50,
            "green_ratio": np.sum(green_mask) / green_mask.size,
            "blue_ratio": np.sum(blue_mask) / blue_mask.size,
            "warm_ratio": np.sum(warm_mask) / warm_mask.size
        }

    def analyze_detail(self, image: np.ndarray) -> dict:
        """Analyze image detail/texture level using Laplacian variance."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        laplacian = cv2.Laplacian(gray, cv2.CV_64F)
        variance = laplacian.var()
        edges = cv2.Canny(gray, 50, 150)
        edge_density = np.sum(edges > 0) / edges.size
        return {
            "sharpness": variance,
            "edge_density": edge_density,
            "is_sharp": variance > 500,
            "is_blurry": variance < 100,
            "has_fine_detail": edge_density > 0.1
        }

    def detect_skin_tones(self, image: np.ndarray) -> tuple:
        """Detect skin tone regions in image."""
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        ycrcb = cv2.cvtColor(image, cv2.COLOR_RGB2YCrCb)
        
        # Combined skin detection (HSV + YCrCb)
        lower_hsv = np.array([0, 20, 70], dtype=np.uint8)
        upper_hsv = np.array([25, 180, 255], dtype=np.uint8)
        mask_hsv = cv2.inRange(hsv, lower_hsv, upper_hsv)
        
        lower_ycrcb = np.array([0, 133, 77], dtype=np.uint8)
        upper_ycrcb = np.array([255, 173, 127], dtype=np.uint8)
        mask_ycrcb = cv2.inRange(ycrcb, lower_ycrcb, upper_ycrcb)
        
        skin_mask = cv2.bitwise_and(mask_hsv, mask_ycrcb)
        skin_mask = cv2.morphologyEx(skin_mask, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))
        skin_ratio = np.sum(skin_mask > 0) / skin_mask.size
        
        return skin_mask, skin_ratio

    def adaptive_gamma(self, image: np.ndarray, target_brightness: float = 128) -> np.ndarray:
        """Apply adaptive gamma correction based on image brightness."""
        brightness = self.analyze_brightness(image)
        current = brightness["mean"]
        
        if current < 1: current = 1
        gamma = np.log(target_brightness / 255) / np.log(current / 255)
        gamma = np.clip(gamma, 0.5, 2.5)
        
        inv_gamma = 1.0 / gamma
        table = np.array([((i / 255.0) ** inv_gamma) * 255 for i in range(256)]).astype("uint8")
        return cv2.LUT(image, table)

    def unsharp_mask(self, image: np.ndarray, sigma: float = 1.0, strength: float = 1.5, threshold: int = 0) -> np.ndarray:
        """Apply unsharp masking with threshold for selective sharpening."""
        blurred = cv2.GaussianBlur(image, (0, 0), sigma)
        sharpened = cv2.addWeighted(image, 1.0 + strength, blurred, -strength, 0)
        
        if threshold > 0:
            low_contrast_mask = np.abs(image.astype(np.int16) - blurred.astype(np.int16)) < threshold
            np.copyto(sharpened, image, where=low_contrast_mask)
        
        return np.clip(sharpened, 0, 255).astype(np.uint8)

    # --- Comprehensive Image Analysis ---
    
    def analyze_image(self, image: np.ndarray) -> ImageAnalysis:
        """Perform comprehensive image analysis and compute adaptive parameters."""
        analysis = ImageAnalysis()
        
        # Brightness analysis
        brightness = self.analyze_brightness(image)
        analysis.mean_brightness = brightness["mean"]
        analysis.brightness_std = brightness["std"]
        analysis.dark_ratio = brightness["dark_ratio"]
        analysis.bright_ratio = brightness["bright_ratio"]
        analysis.is_low_light = brightness["is_low_light"]
        analysis.is_high_key = brightness["is_high_key"]
        
        # Color analysis
        color = self.analyze_color(image)
        analysis.mean_saturation = color["mean_saturation"]
        analysis.is_saturated = color["is_saturated"]
        analysis.is_desaturated = color["is_desaturated"]
        analysis.green_ratio = color["green_ratio"]
        analysis.blue_ratio = color["blue_ratio"]
        analysis.warm_ratio = color["warm_ratio"]
        
        # Determine dominant hue
        if color["green_ratio"] > 0.15:
            analysis.dominant_hue = "green"
            analysis.has_vegetation = True
        elif color["blue_ratio"] > 0.15:
            analysis.dominant_hue = "blue"
        elif color["warm_ratio"] > 0.15:
            analysis.dominant_hue = "warm"
        
        # Color temperature
        if color["warm_ratio"] > color["blue_ratio"] * 1.5:
            analysis.color_temperature = "warm"
        elif color["blue_ratio"] > color["warm_ratio"] * 1.5:
            analysis.color_temperature = "cool"
        
        # Detail analysis
        detail = self.analyze_detail(image)
        analysis.sharpness = detail["sharpness"]
        analysis.edge_density = detail["edge_density"]
        analysis.is_sharp = detail["is_sharp"]
        analysis.is_blurry = detail["is_blurry"]
        analysis.has_fine_detail = detail["has_fine_detail"]
        
        # Noise estimation
        analysis.noise_level = self._estimate_noise(image)
        
        # Region detection
        analysis.sky_mask, analysis.sky_ratio, analysis.has_sky = self._detect_sky(image)
        analysis.skin_mask, analysis.skin_ratio = self.detect_skin_tones(image)
        analysis.has_faces = analysis.skin_ratio > 0.05
        analysis.vegetation_mask, veg_ratio = self._detect_vegetation(image)
        analysis.has_vegetation = veg_ratio > 0.1
        analysis.water_mask, water_ratio = self._detect_water(image)
        analysis.has_water = water_ratio > 0.1
        
        # Foreground/background separation
        analysis.foreground_mask = self._detect_foreground(image)
        
        # Compute adaptive parameters based on analysis
        self._compute_adaptive_parameters(analysis)
        
        return analysis
    
    def _compute_adaptive_parameters(self, analysis: ImageAnalysis):
        """Compute recommended processing parameters based on image analysis.
        Philosophy: Less is more. Aim for clean, natural, Instagram-ready output."""
        # CLAHE clip limit: gentle touch - avoid HDR look
        if analysis.brightness_std < 40:  # Low contrast
            analysis.recommended_clahe_clip = 1.5
        elif analysis.brightness_std > 70:  # High contrast
            analysis.recommended_clahe_clip = 0.8
        else:
            analysis.recommended_clahe_clip = 1.0
        
        # Low light needs slightly stronger CLAHE but still conservative
        if analysis.is_low_light:
            analysis.recommended_clahe_clip = min(analysis.recommended_clahe_clip + 0.5, 2.0)
        
        # Saturation: very subtle adjustments only
        if analysis.is_desaturated:
            analysis.recommended_saturation = 1.1
        elif analysis.is_saturated:
            analysis.recommended_saturation = 0.95
        else:
            analysis.recommended_saturation = 1.05
        
        # Sharpening: minimal - avoid grain amplification
        if analysis.is_blurry:
            analysis.recommended_sharpening = 0.6
        elif analysis.is_sharp or analysis.noise_level > 10:
            analysis.recommended_sharpening = 0.0  # Don't sharpen noisy/already sharp images
        else:
            analysis.recommended_sharpening = 0.3
        
        # Denoising: more aggressive - clean output is priority
        if analysis.noise_level > 15:
            analysis.recommended_denoise = 8.0
        elif analysis.noise_level > 8:
            analysis.recommended_denoise = 6.0
        elif analysis.noise_level > 4:
            analysis.recommended_denoise = 4.0
        elif analysis.noise_level > 2:
            analysis.recommended_denoise = 2.0
        else:
            analysis.recommended_denoise = 0.0
    
    def _estimate_noise(self, image: np.ndarray) -> float:
        """Estimate image noise level using Laplacian method."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        # Use a small region to estimate noise (avoid edges)
        h, w = gray.shape
        center = gray[h//4:3*h//4, w//4:3*w//4]
        
        # High-pass filter to isolate noise
        blur = cv2.GaussianBlur(center, (5, 5), 0)
        noise = np.abs(center.astype(np.float32) - blur.astype(np.float32))
        return np.std(noise)
    
    def _detect_sky(self, image: np.ndarray) -> tuple:
        """Detect sky region in the image."""
        h, w = image.shape[:2]
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        
        # Sky is typically blue-ish and in the upper portion
        # Also detect bright overcast sky (low saturation, high value)
        hue, sat, val = cv2.split(hsv)
        
        # Blue sky mask
        blue_sky = ((hue >= 90) & (hue <= 130) & (sat > 30) & (val > 100)).astype(np.uint8) * 255
        
        # Bright/overcast sky (low saturation, high brightness in upper half)
        upper_mask = np.zeros_like(hue)
        upper_mask[:h//2, :] = 1
        bright_sky = ((sat < 50) & (val > 180) & (upper_mask == 1)).astype(np.uint8) * 255
        
        # Combine masks
        sky_mask = cv2.bitwise_or(blue_sky, bright_sky)
        
        # Weight by vertical position (sky is usually at top)
        weight_mask = np.zeros((h, w), dtype=np.float32)
        for y in range(h):
            weight_mask[y, :] = 1.0 - (y / h) * 0.7
        
        weighted_sky = (sky_mask.astype(np.float32) * weight_mask).astype(np.uint8)
        
        # Morphological cleanup
        kernel = np.ones((15, 15), np.uint8)
        sky_mask = cv2.morphologyEx(weighted_sky, cv2.MORPH_CLOSE, kernel)
        sky_mask = cv2.morphologyEx(sky_mask, cv2.MORPH_OPEN, kernel)
        
        sky_ratio = np.sum(sky_mask > 0) / sky_mask.size
        has_sky = sky_ratio > 0.05
        
        return sky_mask, sky_ratio, has_sky
    
    def _detect_vegetation(self, image: np.ndarray) -> tuple:
        """Detect vegetation (green foliage) in the image."""
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        hue, sat, val = cv2.split(hsv)
        
        # Green vegetation mask
        veg_mask = ((hue >= 30) & (hue <= 90) & (sat > 40) & (val > 30)).astype(np.uint8) * 255
        
        # Cleanup
        kernel = np.ones((5, 5), np.uint8)
        veg_mask = cv2.morphologyEx(veg_mask, cv2.MORPH_OPEN, kernel)
        veg_mask = cv2.morphologyEx(veg_mask, cv2.MORPH_CLOSE, kernel)
        
        veg_ratio = np.sum(veg_mask > 0) / veg_mask.size
        return veg_mask, veg_ratio
    
    def _detect_water(self, image: np.ndarray) -> tuple:
        """Detect water regions in the image."""
        hsv = cv2.cvtColor(image, cv2.COLOR_RGB2HSV)
        hue, sat, val = cv2.split(hsv)
        
        # Water is typically cyan to blue, with moderate saturation
        water_mask = ((hue >= 80) & (hue <= 130) & (sat > 20) & (sat < 180) & (val > 50)).astype(np.uint8) * 255
        
        # Look for horizontal uniformity (water is often horizontally consistent)
        kernel = np.ones((3, 15), np.uint8)
        water_mask = cv2.morphologyEx(water_mask, cv2.MORPH_CLOSE, kernel)
        
        water_ratio = np.sum(water_mask > 0) / water_mask.size
        return water_mask, water_ratio
    
    def _detect_foreground(self, image: np.ndarray) -> np.ndarray:
        """Simple foreground detection using edge density and saliency."""
        gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
        h, w = gray.shape
        
        # Edge-based saliency
        edges = cv2.Canny(gray, 50, 150)
        
        # Blur edges to create regions
        saliency = cv2.GaussianBlur(edges.astype(np.float32), (31, 31), 0)
        
        # Center bias (foreground often in center)
        center_y, center_x = h // 2, w // 2
        y_coords, x_coords = np.ogrid[:h, :w]
        center_dist = np.sqrt((x_coords - center_x)**2 + (y_coords - center_y)**2)
        max_dist = np.sqrt(center_x**2 + center_y**2)
        center_weight = 1.0 - (center_dist / max_dist) * 0.5
        
        # Combine
        foreground_score = saliency * center_weight
        threshold = np.percentile(foreground_score, 60)
        foreground_mask = (foreground_score > threshold).astype(np.uint8) * 255
        
        # Cleanup
        kernel = np.ones((15, 15), np.uint8)
        foreground_mask = cv2.morphologyEx(foreground_mask, cv2.MORPH_CLOSE, kernel)
        
        return foreground_mask

    # --- Region-Based Processing Methods ---
    
    def apply_to_region(self, image: np.ndarray, mask: np.ndarray, 
                        process_func: Callable, **kwargs) -> np.ndarray:
        """Apply a processing function only to masked region with smooth blending."""
        if mask is None:
            return process_func(image, **kwargs)
        
        # Ensure mask is proper format
        if mask.dtype != np.uint8:
            mask = mask.astype(np.uint8)
        if len(mask.shape) == 2:
            mask_3ch = cv2.cvtColor(mask, cv2.COLOR_GRAY2RGB)
        else:
            mask_3ch = mask
        
        # Create soft mask for blending
        soft_mask = cv2.GaussianBlur(mask, (21, 21), 0)
        soft_mask_3ch = cv2.cvtColor(soft_mask, cv2.COLOR_GRAY2RGB).astype(np.float32) / 255.0
        
        # Process the full image
        processed = process_func(image, **kwargs)
        
        # Blend based on mask
        result = (processed.astype(np.float32) * soft_mask_3ch + 
                  image.astype(np.float32) * (1 - soft_mask_3ch))
        
        return np.clip(result, 0, 255).astype(np.uint8)
    
    def apply_excluding_region(self, image: np.ndarray, mask: np.ndarray,
                                process_func: Callable, **kwargs) -> np.ndarray:
        """Apply processing everywhere EXCEPT the masked region."""
        if mask is None:
            return process_func(image, **kwargs)
        
        inverted_mask = cv2.bitwise_not(mask)
        return self.apply_to_region(image, inverted_mask, process_func, **kwargs)
    
    def enhance_sky(self, image: np.ndarray, sky_mask: np.ndarray,
                    saturation_boost: float = 1.2, 
                    contrast_boost: float = 1.1) -> np.ndarray:
        """Enhance sky region specifically."""
        if sky_mask is None or np.sum(sky_mask) == 0:
            return image
        
        def sky_enhance(img, sat=saturation_boost, contrast=contrast_boost):
            # Boost saturation
            enhanced = self.adjust_saturation(img, sat)
            # Slight contrast
            lab = cv2.cvtColor(enhanced, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            l = np.clip(l.astype(np.float32) * contrast, 0, 255).astype(np.uint8)
            return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
        
        return self.apply_to_region(image, sky_mask, sky_enhance)
    
    def protect_skin(self, image: np.ndarray, skin_mask: np.ndarray,
                     process_func: Callable, **kwargs) -> np.ndarray:
        """Apply processing while protecting skin tones."""
        return self.apply_excluding_region(image, skin_mask, process_func, **kwargs)
    
    def enhance_foreground(self, image: np.ndarray, fg_mask: np.ndarray,
                           sharpening: float = 1.3,
                           contrast: float = 1.1) -> np.ndarray:
        """Enhance foreground subject with sharpening and contrast."""
        if fg_mask is None:
            return image
        
        def fg_enhance(img, sharp=sharpening, cont=contrast):
            enhanced = self.unsharp_mask(img, strength=sharp)
            lab = cv2.cvtColor(enhanced, cv2.COLOR_RGB2LAB)
            l, a, b = cv2.split(lab)
            l = np.clip(l.astype(np.float32) * cont, 0, 255).astype(np.uint8)
            return cv2.cvtColor(cv2.merge([l, a, b]), cv2.COLOR_LAB2RGB)
        
        return self.apply_to_region(image, fg_mask, fg_enhance)
    
    def denoise_adaptive(self, image: np.ndarray, strength: float = None) -> np.ndarray:
        """Apply adaptive denoising based on analysis or specified strength."""
        if strength is None:
            strength = self._analysis.recommended_denoise if self._analysis else 0
        
        if strength <= 0:
            return image
        
        # Use fastNlMeansDenoisingColored for color images
        return cv2.fastNlMeansDenoisingColored(image, None, strength, strength, 7, 21)