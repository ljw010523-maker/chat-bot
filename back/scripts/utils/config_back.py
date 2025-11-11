"""
설정 관리
"""

from pathlib import Path
import platform
import glob


class Config:
    """파이프라인 설정"""

    def __init__(self):
        # 경로 설정
        self.raw_folder = "data/raw"
        self.output_folder = "data/chunks"

        # 청크 설정
        self.chunk_size = 500
        self.chunk_overlap = 50
        self.use_langchain = True

        # OCR 설정
        self.ocr_dpi = 300

        # 개인정보 필터링 설정
        self.use_privacy_filter = False  # True로 설정하면 필터링 활성화

        # 🆕 Hanspell 텍스트 정규화 설정
        self.use_hanspell_normalization = True  # True로 설정하면 Hanspell 정규화 활성화

        # Windows 전용 경로
        if platform.system() == "Windows":
            self.tesseract_path = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

            poppler_search = glob.glob(r"C:\Program Files\poppler-*\Library\bin")
            self.poppler_path = poppler_search[0] if poppler_search else None
        else:
            self.tesseract_path = None
            self.poppler_path = None
