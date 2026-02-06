from enum import Enum

class PresetType(str, Enum):
    # --- Subjects (What's in the photo?) ---
    PORTRAIT = "portrait"
    PETS = "pets"
    FOOD = "food"
    
    # --- Scenes (Where/What environment?) ---
    LANDSCAPE = "landscape"
    ARCHITECTURE = "architecture"
    CITY = "city"
    OCEAN = "ocean"
    UNDERWATER = "underwater"
    JUNGLE = "jungle"
    SNOW = "snow"
    INDOOR = "indoor"
    
    # --- Vibes (Lighting/Mood/Style) ---
    STANDARD = "standard"
    SUNSET = "sunset"
    NIGHT = "night"
    BRIGHT = "bright"
    CINEMATIC = "cinematic"
    RETRO = "retro"
    B_AND_W = "black_and_white"

class OutputFormat(str, Enum):
    JPG = "jpg"
    PNG = "png"
