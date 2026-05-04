from langdetect import detect, DetectorFactory

# Seeding ensures the detector gives consistent results for the exact same text
DetectorFactory.seed = 0

def get_language(text, default_lang="en"):
    """
    Analyzes the text and returns 'vi' for Vietnamese or 'en' for English.
    Includes safeguards for empty or extremely short strings.
    """
    text = text.strip()
    
    # Safeguard: Too short to accurately detect, use default
    if len(text) < 3:
        return default_lang
        
    try:
        lang = detect(text)
        
        # We only care about routing to our two installed engines
        if lang == 'vi':
            return 'vi'
        return 'en'
        
    except Exception as e:
        print(f"[Language Detector] Warning: Could not detect language. Defaulting to {default_lang}. Error: {e}")
        return default_lang