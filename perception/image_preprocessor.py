import cv2
import numpy as np

def preprocess_image_for_ocr(image_path: str) -> np.ndarray:
    """
    Prepares a screenshot for OCR by converting to grayscale,
    increasing contrast, and reducing noise.
    """
    # Read the image
    img = cv2.imread(image_path)
    if img is None:
        raise FileNotFoundError(f"Could not read image at {image_path}")
        
    # Convert to grayscale
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    
    # Increase contrast using CLAHE (Contrast Limited Adaptive Histogram Equalization)
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    contrast = clahe.apply(gray)
    
    # Denoise
    denoised = cv2.fastNlMeansDenoising(contrast, None, 10, 7, 21)
    
    # Optional: Binarization (can sometimes hurt if background varies, keeping it simple for now)
    # _, binary = cv2.threshold(denoised, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    
    return denoised
