import logging
import pytesseract
from PIL import Image
from typing import List, Dict, Any

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

from perception.image_preprocessor import preprocess_image_for_ocr

class OCREngine:
    def __init__(self, config: dict):
        self.config = config.get("perception", {}).get("ocr", {})
        self.engine_type = self.config.get("engine", "easyocr")
        self.confidence_threshold = self.config.get("confidence_threshold", 0.6)
        self.use_gpu = self.config.get("gpu_enabled", True)
        self.langs = self.config.get("languages", ["en"])
        self.preprocess = self.config.get("preprocess_image", True)
        
        self.reader = None
        
        if self.engine_type == "easyocr" and EASYOCR_AVAILABLE:
            logging.info(f"Initializing EasyOCR (GPU: {self.use_gpu})")
            try:
                self.reader = easyocr.Reader(self.langs, gpu=self.use_gpu)
            except Exception as e:
                logging.error(f"Failed to initialize EasyOCR: {e}. Falling back to Tesseract.")
                self.engine_type = "tesseract"
        elif self.engine_type == "easyocr":
            logging.info("EasyOCR not found. Falling back to Tesseract.")
            self.engine_type = "tesseract"

    def process_image(self, image_path: str, step_id: str) -> List[Dict[str, Any]]:
        """Run OCR on an image and return structured results."""
        if self.preprocess:
            try:
                # This requires cv2 saving to a temp file or passing numpy array directly
                # EasyOCR handles numpy arrays
                img = preprocess_image_for_ocr(image_path)
            except Exception as e:
                logging.warning(f"Preprocessing failed ({e}), using raw image.")
                img = image_path
        else:
             img = image_path

        if self.engine_type == "easyocr" and self.reader:
            return self._run_easyocr(img, step_id)
        else:
            return self._run_tesseract(image_path, step_id)

    def _run_easyocr(self, img, step_id: str) -> List[Dict[str, Any]]:
        results = []
        try:
            # reader.readtext accepts file paths, PIL images, or numpy arrays
            raw_results = self.reader.readtext(img)
            
            for idx, (bbox, text, conf) in enumerate(raw_results):
                # bbox is a list of 4 points: [top-left, top-right, bottom-right, bottom-left]
                if conf < self.confidence_threshold:
                    continue
                    
                tl, tr, br, bl = bbox
                
                # Convert coords to int
                x = int(min(tl[0], bl[0]))
                y = int(min(tl[1], tr[1]))
                w = int(max(tr[0], br[0]) - x)
                h = int(max(bl[1], br[1]) - y)
                
                confidence_level = "reliable" if conf >= 0.8 else "uncertain"
                
                results.append({
                    "id": f"ocr_{step_id}_{idx}",
                    "text": text,
                    "confidence": float(conf),
                    "confidence_level": confidence_level,
                    "bounding_box": {"x": x, "y": y, "width": w, "height": h}
                })
        except Exception as e:
            logging.error(f"EasyOCR error: {e}")
            
        return results

    def _run_tesseract(self, image_path: str, step_id: str) -> List[Dict[str, Any]]:
        """Fallback OCR using Tesseract"""
        results = []
        try:
            img = Image.open(image_path)
            data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
            
            for i in range(len(data['text'])):
                text = data['text'][i].strip()
                conf = int(data['conf'][i]) / 100.0  # Tesseract gives conf 0-100
                
                if not text or conf < self.confidence_threshold:
                    continue
                    
                x = data['left'][i]
                y = data['top'][i]
                w = data['width'][i]
                h = data['height'][i]
                
                confidence_level = "reliable" if conf >= 0.8 else "uncertain"
                
                results.append({
                    "id": f"tess_{step_id}_{i}",
                    "text": text,
                    "confidence": float(conf),
                    "confidence_level": confidence_level,
                    "bounding_box": {"x": x, "y": y, "width": w, "height": h}
                })
        except Exception as e:
            logging.error(f"Tesseract error: {e}. Is tesseract installed on the system?")
            
        return results
