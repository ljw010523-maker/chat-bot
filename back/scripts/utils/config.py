"""
설정 관리 (민감정보 처리 비활성화)
back/scripts/utils/config.py
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
        self.chunk_overlap = 100
        self.use_langchain = True

        # OCR 설정
        self.ocr_dpi = 300

        # Upstage API 설정
        self.upstage_api_key = None  # 여기에 API 키 입력

        # ❌ 민감정보 필터링 완전 비활성화
        self.use_privacy_filter = False

        # ❌ T5 정규화 비활성화 (띄어쓰기만 처리)
        self.use_hanspell_normalization = False

        # Windows 전용 경로
        if platform.system() == "Windows":
            self.tesseract_path = None  # Tesseract OCR 비활성화

            poppler_search = glob.glob(r"C:\Program Files\poppler-*\Library\bin")
            self.poppler_path = poppler_search[0] if poppler_search else None
        else:
            self.tesseract_path = None
            self.poppler_path = None
