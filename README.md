# LADAS: Local AI Desktop Automation System

LADAS is a vision-first, local-only desktop automation system designed to interact with your computer like a human would.

## Features

- **Vision-First Perception:** Uses EasyOCR and YOLOv8 to "see" the screen.
- **Human-Like Execution:** Uses Bezier curves for smooth mouse movements and randomized typing delays.
- **Robust State Management:** Tracks automation loops and implements failsafes (default F12).
- **Local LLM Intelligence:** Integrates with local LLMs via `llama-cpp-python` for privacy-preserving reasoning.

## Setup

1. Create a virtual environment: `python -m venv venv`
2. Activate it: `venv\Scripts\activate` (Windows)
3. Install dependencies: `pip install -r requirements.txt`
4. Install local models (EasyOCR will download standard models automatically; you can point `config.yaml` to explicit GGUF and PT files for LLMs and vision models).

## Running

```bash
python main.py
```

Type commands into the interactive prompt. Press `F12` to abort any active automation sequence.
