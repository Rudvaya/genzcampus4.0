import cv2
import numpy as np
import pytesseract
from PIL import Image

def extract_from_image(filepath):
    """
    Extract timetable from image using OpenCV and PyTesseract.
    """
    try:
        # NOTE: A robust implementation requires contour detection to build a grid of text cells
        # Since Tesseract and OpenCV are heavily reliant on proper environment paths and trained models,
        # we will use this as a stub that mimics the OCR fallback logic as requested.
        img = Image.open(filepath)
        text = pytesseract.image_to_string(img)
        
        # If the image was readable, we would ideally parse the grid using similar heuristics to the excel parser.
        raise ValueError("Image OCR needs robust contour tuning for table reconstruction. Returning needs_review.")
    except Exception as e:
        raise ValueError(f"Image parsing error: {str(e)}")
