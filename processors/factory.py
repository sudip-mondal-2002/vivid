from typing import Optional, Callable
from .enums import PresetType
from .base import BaseEnhancer
# Classic presets
from .LandscapeEnhancer import LandscapeEnhancer
from .PortraitEnhancer import PortraitEnhancer
from .ArchitectureEnhancer import ArchitectureEnhancer
from .JungleEnhancer import JungleEnhancer
# Renamed presets (keeping old class names for now)
from .GeneralEnhancer import GeneralEnhancer      # STANDARD
from .LowLightEnhancer import LowLightEnhancer    # NIGHT
from .SeascapeEnhancer import SeascapeEnhancer    # OCEAN
from .GoldenHourEnhancer import GoldenHourEnhancer  # SUNSET
from .HighKeyEnhancer import HighKeyEnhancer      # BRIGHT
from .MoodyEnhancer import MoodyEnhancer          # CINEMATIC
from .UnderwaterEnhancer import UnderwaterEnhancer
# New presets
from .FoodEnhancer import FoodEnhancer
from .PetsEnhancer import PetsEnhancer
from .CityEnhancer import CityEnhancer
from .SnowEnhancer import SnowEnhancer
from .IndoorEnhancer import IndoorEnhancer
from .RetroEnhancer import RetroEnhancer
from .BAndWEnhancer import BAndWEnhancer

class EnhancerFactory:
    @staticmethod
    def get_enhancer(
        preset: PresetType, 
        file_bytes: bytes,
        progress_callback: Optional[Callable[[str, int, str], None]] = None
    ) -> BaseEnhancer:
        mapping = {
            # Classic (kept as-is)
            PresetType.PORTRAIT: PortraitEnhancer,
            PresetType.LANDSCAPE: LandscapeEnhancer,
            PresetType.ARCHITECTURE: ArchitectureEnhancer,
            PresetType.JUNGLE: JungleEnhancer,
            # Renamed
            PresetType.STANDARD: GeneralEnhancer,
            PresetType.NIGHT: LowLightEnhancer,
            PresetType.OCEAN: SeascapeEnhancer,
            PresetType.SUNSET: GoldenHourEnhancer,
            PresetType.BRIGHT: HighKeyEnhancer,
            PresetType.CINEMATIC: MoodyEnhancer,
            PresetType.UNDERWATER: UnderwaterEnhancer,
            # New presets
            PresetType.FOOD: FoodEnhancer,
            PresetType.PETS: PetsEnhancer,
            PresetType.CITY: CityEnhancer,
            PresetType.SNOW: SnowEnhancer,
            PresetType.INDOOR: IndoorEnhancer,
            PresetType.RETRO: RetroEnhancer,
            PresetType.B_AND_W: BAndWEnhancer,
        }
        
        enhancer_class = mapping.get(preset, GeneralEnhancer)
        return enhancer_class(file_bytes, progress_callback)
