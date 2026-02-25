import os
import urllib.request
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

MODELS_DIR = "models"
os.makedirs(MODELS_DIR, exist_ok=True)

# 1. Download LLM (Phi-3-mini-4k-instruct GGUF) - small, capable model
LLM_URL = "https://huggingface.co/microsoft/Phi-3-mini-4k-instruct-gguf/resolve/main/Phi-3-mini-4k-instruct-q4.gguf?download=true"
LLM_PATH = os.path.join(MODELS_DIR, "Phi-3-mini-4k-instruct-q4.gguf")

def report_hook(count, block_size, total_size):
    if count % 1000 == 0:
        percent = int(count * block_size * 100 / total_size)
        print(f"\rDownloading LLM: {percent}%", end="")

if not os.path.exists(LLM_PATH):
    logging.info(f"Downloading LLM from {LLM_URL.split('?')[0]}...")
    try:
        # Use a user-agent to avoid 403 Forbidden on HuggingFace sometimes
        req = urllib.request.Request(
            LLM_URL, 
            data=None, 
            headers={'User-Agent': 'Mozilla/5.0'}
        )
        with urllib.request.urlopen(req) as response, open(LLM_PATH, 'wb') as out_file:
            # We don't have total size if it's chunked, so just read iter
            total_size = int(response.info().get('Content-Length', 0))
            downloaded = 0
            block_size = 1024 * 8
            while True:
                buffer = response.read(block_size)
                if not buffer:
                    break
                downloaded += len(buffer)
                out_file.write(buffer)
                if total_size > 0 and (downloaded // block_size) % 1000 == 0:
                    percent = int(downloaded * 100 / total_size)
                    print(f"\rDownloading LLM: {percent}% ({downloaded / 1024 / 1024:.2f} MB)", end="")
        print()
        logging.info("LLM downloaded successfully.")
    except Exception as e:
        logging.error(f"Failed to download LLM: {e}")
else:
    logging.info("LLM already exists.")

# 2. Trigger YOLOv8 download
logging.info("Initializing YOLOv8 to trigger download...")
try:
    from ultralytics import YOLO
    model = YOLO("yolov8n.pt")
    logging.info("YOLOv8 initialized.")
except Exception as e:
    logging.error(f"Failed to initialize YOLOv8: {e}")

# 3. Trigger EasyOCR model download
logging.info("Initializing EasyOCR to trigger download...")
try:
    import easyocr
    reader = easyocr.Reader(['en'], gpu=False)
    logging.info("EasyOCR initialized.")
except Exception as e:
    logging.error(f"Failed to initialize EasyOCR: {e}")

logging.info("Models download complete.")
