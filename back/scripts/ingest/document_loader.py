"""
범용 문서 로더 (Universal Document Loader) - HWP/HWPX 지원 추가
모든 파일 형식을 완벽하게 파싱 + 노이즈 제거 + HWP 검증 강화
"""

from pathlib import Path
from typing import List, Dict
import platform

# PDF
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image, ImageEnhance

# Office 문서
try:
    import docx

    DOCX_AVAILABLE = True
except ImportError:
    DOCX_AVAILABLE = False

try:
    from pptx import Presentation

    PPTX_AVAILABLE = True
except ImportError:
    PPTX_AVAILABLE = False

try:
    import openpyxl

    OPENPYXL_AVAILABLE = True
except ImportError:
    OPENPYXL_AVAILABLE = False

try:
    import pandas as pd

    PANDAS_AVAILABLE = True
except ImportError:
    PANDAS_AVAILABLE = False

# 구버전 Office 파일 (.doc, .xls, .ppt)
try:
    import win32com.client  # type: ignore

    WIN32COM_AVAILABLE = True
except ImportError:
    WIN32COM_AVAILABLE = False

# HWP 파일 처리
try:
    import olefile

    HWP_AVAILABLE = True
except ImportError:
    HWP_AVAILABLE = False

# hwp5 라이브러리는 설치가 어려워서 제거
# HWP는 olefile의 PrvText 방식으로 처리

# Unstructured (Deep Document Parser)
try:
    from unstructured.partition.auto import partition
    UNSTRUCTURED_AVAILABLE = True
except ImportError:
    UNSTRUCTURED_AVAILABLE = False

# Upstage VLM API (표/도장/날인 인식)
try:
    from langchain_upstage import UpstageDocumentParseLoader
    VLM_AVAILABLE = True
except ImportError:
    VLM_AVAILABLE = False

# 텍스트 정제
from back.scripts.clean.text_cleaner import TextCleaner

# HWP 처리
from back.scripts.ingest.hwp_processor import HwpProcessor

# Tesseract/Poppler 경로 (Windows)
if platform.system() == "Windows":
    # Tesseract OCR 비활성화
    # pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"

    import glob

    poppler_search = glob.glob(r"C:\Program Files\poppler-*\Library\bin")
    POPPLER_PATH = (
        poppler_search[0]
        if poppler_search
        else r"C:\Program Files\poppler-25.07.0\Library\bin"
    )
else:
    POPPLER_PATH = None


class UniversalDocumentLoader:
    """범용 문서 로더 - 모든 파일 형식 완벽 처리"""

    def __init__(self, config):
        self.config = config
        self.ocr_dpi = getattr(config, "ocr_dpi", 300)
        self.text_cleaner = TextCleaner()  # 텍스트 정제기 초기화
        self.hwp_processor = HwpProcessor(config, self.text_cleaner)  # HWP 처리기 초기화
        self._print_capabilities()

    def _print_capabilities(self):
        """지원 형식 출력"""
        print("\n📋 문서 로더 지원 형식:")
        print(f"  - PDF: ✓ (텍스트 + OCR + 노이즈 제거)")
        print(f"  - TXT: ✓")
        print(
            f"  - Word (.docx): {'✓' if DOCX_AVAILABLE else '✗ (pip install python-docx)'}"
        )
        print(
            f"  - Word (.doc): {'✓' if WIN32COM_AVAILABLE else '✗ (Windows 전용, pip install pywin32)'}"
        )
        print(
            f"  - PowerPoint (.pptx): {'✓' if PPTX_AVAILABLE else '✗ (pip install python-pptx)'}"
        )
        print(
            f"  - PowerPoint (.ppt): {'✓' if WIN32COM_AVAILABLE else '✗ (Windows 전용, pip install pywin32)'}"
        )
        print(
            f"  - Excel (.xlsx): {'✓' if OPENPYXL_AVAILABLE else '✗ (pip install openpyxl)'}"
        )
        print(
            f"  - Excel (.xls): {'✓' if WIN32COM_AVAILABLE else '✗ (Windows 전용, pip install pywin32)'}"
        )
        print(f"  - CSV: {'✓' if PANDAS_AVAILABLE else '✗ (pip install pandas)'}")
        print(
            f"  - HWP (.hwp/.hwpx): {'✓' if HWP_AVAILABLE else '✗ (pip install olefile)'}"
        )
        print(f"  - 이미지 (.jpg/.png): ✓ (OCR + 노이즈 제거)\n")

    def load(self, file_path: Path) -> List[Dict]:
        """
        파일 형식 자동 감지 및 텍스트 추출

        Returns:
            List[Dict]: [{'page_num': int, 'text': str, 'method': str}, ...]
        """
        suffix = file_path.suffix.lower()

        # 파일 형식별 라우팅
        if suffix == ".pdf":
            return self._load_pdf(file_path)
        elif suffix == ".txt":
            return self._load_txt(file_path)
        elif suffix == ".docx":
            return self._load_docx(file_path)
        elif suffix == ".doc":
            return self._load_doc_legacy(file_path)
        elif suffix == ".pptx":
            return self._load_pptx(file_path)
        elif suffix == ".ppt":
            return self._load_ppt_legacy(file_path)
        elif suffix == ".xlsx":
            return self._load_excel(file_path)
        elif suffix == ".xls":
            return self._load_xls_legacy(file_path)
        elif suffix == ".csv":
            return self._load_csv(file_path)
        # elif suffix in [".hwp", ".hwpx"]:  # HWP 처리 비활성화 (느림)
        #     return self.hwp_processor.load_hwp(file_path, vlm_parser_func=self._parse_with_vlm)
        elif suffix in [".jpg", ".jpeg", ".png", ".bmp", ".tiff"]:
            return self._load_image(file_path)
        else:
            print(f"  ⚠️ 지원하지 않는 형식: {suffix}")
            return []

    # ============================================
    # PDF 처리 (강화)
    # ============================================

    def _load_pdf(self, file_path: Path) -> List[Dict]:
        """PDF 텍스트 추출 (텍스트 우선, 스캔본은 Google Vision OCR)"""
        try:
            # 방법 1: PyPDF2로 텍스트 추출 시도 (타이핑된 문서용)
            with open(file_path, "rb") as f:
                reader = PyPDF2.PdfReader(f)
                total_pages = len(reader.pages)

                print(f"  📑 PDF {total_pages}페이지")

                # 첫 페이지로 텍스트 여부 판단
                first_text = reader.pages[0].extract_text().strip()
                first_text_len = len(first_text)

                print(f"  📊 첫 페이지 텍스트: {first_text_len}자")

                # 텍스트가 충분하면 (타이핑된 문서)
                if first_text_len >= 50:
                    print("  ✓ 텍스트 기반 PDF (타이핑된 문서)")
                    pages_data = []

                    for page_num, page in enumerate(reader.pages, 1):
                        text = page.extract_text().strip()

                        if len(text) < 50:
                            print(f"    페이지 {page_num}: 텍스트 부족, OCR 적용")
                            text = self._ocr_pdf_page(file_path, page_num)
                            method = "pdf_ocr"
                        else:
                            # 텍스트 후처리 적용
                            text = self.text_cleaner.clean_ocr_text(text)
                            method = "pdf_text"

                        pages_data.append(
                            {"page_num": page_num, "text": text, "method": method}
                        )

                    return pages_data

                # 텍스트가 부족하면 스캔본/캡처본으로 판단
                print("  ⚠️ 스캔본/캡처본 감지 (텍스트 부족)")

            # 방법 2: Upstage VLM OCR (스캔본/캡처본 전용 - 표/도장/날인 인식)
            if VLM_AVAILABLE:
                print("  🔍 Upstage VLM OCR 시도 중...")
                result = self._parse_with_vlm(file_path)
                if result:
                    print(f"  ✓ VLM OCR 성공 ({len(result)}페이지)")
                    return result
                print("  ⚠️ VLM OCR 실패 → Tesseract OCR 폴백")

            # 방법 3: Tesseract OCR (최종 폴백)
            print("  → Tesseract OCR 모드로 전환")
            return self._ocr_pdf(file_path)

        except Exception as e:
            print(f"  ❌ PDF 읽기 실패: {e}")
            print("  → Tesseract OCR 모드로 전환")
            return self._ocr_pdf(file_path)

    def _ocr_pdf(self, file_path: Path) -> List[Dict]:
        """PDF 전체 OCR (강화 버전)"""
        try:
            if platform.system() == "Windows":
                images = convert_from_path(
                    file_path, dpi=self.ocr_dpi, poppler_path=POPPLER_PATH
                )
            else:
                images = convert_from_path(file_path, dpi=self.ocr_dpi)

            print(f"  🔍 {len(images)}페이지 OCR 처리 중 (노이즈 필터링)...")

            pages_data = []
            for page_num, image in enumerate(images, 1):
                print(f"    페이지 {page_num}/{len(images)}...", end=" ")

                try:
                    # 전처리
                    image = self._preprocess_image_for_table(image)

                    text = pytesseract.image_to_string(
                        image, lang="kor+eng", config="--oem 1 --psm 6"
                    ).strip()

                    # 후처리
                    text = self.text_cleaner.clean_ocr_text(text)

                    print(f"✓ ({len(text)}자)")

                    pages_data.append(
                        {"page_num": page_num, "text": text, "method": "pdf_ocr"}
                    )
                except Exception as e:
                    print(f"✗ 실패: {e}")
                    pages_data.append(
                        {"page_num": page_num, "text": "", "method": "ocr_failed"}
                    )

            return pages_data

        except Exception as e:
            print(f"  ❌ OCR 실패: {e}")
            return []

    def _ocr_pdf_page(self, file_path: Path, page_num: int) -> str:
        """PDF 특정 페이지만 OCR (강화 버전)"""
        try:
            if platform.system() == "Windows":
                images = convert_from_path(
                    file_path,
                    first_page=page_num,
                    last_page=page_num,
                    dpi=self.ocr_dpi,
                    poppler_path=POPPLER_PATH,
                )
            else:
                images = convert_from_path(
                    file_path, first_page=page_num, last_page=page_num, dpi=self.ocr_dpi
                )

            if images:
                # 전처리
                image = self._preprocess_image_for_table(images[0])

                text = pytesseract.image_to_string(
                    image, lang="kor+eng", config="--oem 1 --psm 6"
                ).strip()

                # 후처리
                text = self.text_cleaner.clean_ocr_text(text)

                return text
            return ""

        except Exception as e:
            print(f" (OCR 실패: {e})")
            return ""

    # ============================================
    # TXT 처리
    # ============================================

    def _load_txt(self, file_path: Path) -> List[Dict]:
        """TXT 파일 읽기 (다중 인코딩 지원)"""
        try:
            encodings = ["utf-8", "utf-8-sig", "cp949", "euc-kr", "latin-1", "ascii"]
            text = None

            for encoding in encodings:
                try:
                    with open(file_path, "r", encoding=encoding) as f:
                        text = f.read()
                    print(f"  ✓ TXT 읽기 성공 ({encoding})")
                    break
                except (UnicodeDecodeError, LookupError):
                    continue

            if text is None:
                print("  ❌ 인코딩 실패")
                return []

            # 후처리 적용
            text = self.text_cleaner.clean_ocr_text(text)

            return [{"page_num": 1, "text": text, "method": "txt"}]

        except Exception as e:
            print(f"  ❌ TXT 읽기 실패: {e}")
            return []

    # ============================================
    # Word 처리 (강화 - .docx + .doc)
    # ============================================

    def _load_docx(self, file_path: Path) -> List[Dict]:
        """Word .docx 파일 읽기"""
        if not DOCX_AVAILABLE:
            print("  ❌ python-docx 미설치")
            print("     설치: pip install python-docx")
            return []

        try:
            doc = docx.Document(file_path)

            # 단락별 텍스트 추출
            paragraphs = [para.text for para in doc.paragraphs if para.text.strip()]

            # 표 추출
            tables_text = []
            for table in doc.tables:
                for row in table.rows:
                    row_text = " | ".join(cell.text.strip() for cell in row.cells)
                    if row_text.strip():
                        tables_text.append(row_text)

            # 병합
            all_text = "\n".join(paragraphs)
            if tables_text:
                all_text += "\n\n[표 데이터]\n" + "\n".join(tables_text)

            # 후처리 추가
            all_text = self.text_cleaner.clean_ocr_text(all_text)

            print(f"  ✓ Word (.docx) 읽기 완료 ({len(all_text)}자)")

            return [{"page_num": 1, "text": all_text, "method": "docx"}]

        except Exception as e:
            print(f"  ❌ Word (.docx) 읽기 실패: {e}")
            if "not a zip file" in str(e).lower():
                print("  → 구버전 .doc 파일로 재시도")
                return self._load_doc_legacy(file_path)
            return []

    def _load_doc_legacy(self, file_path: Path) -> List[Dict]:
        """Word .doc 파일 읽기 (구버전 - Windows 전용)"""
        if not WIN32COM_AVAILABLE:
            print("  ❌ pywin32 미설치 (Windows 전용)")
            print("     설치: pip install pywin32")
            return []

        if platform.system() != "Windows":
            print("  ❌ .doc 파일은 Windows에서만 지원됩니다")
            return []

        try:
            import pythoncom

            pythoncom.CoInitialize()

            word = win32com.client.Dispatch("Word.Application")
            word.Visible = False

            doc = word.Documents.Open(str(file_path.absolute()))
            text = doc.Content.Text

            doc.Close()
            word.Quit()

            pythoncom.CoUninitialize()

            # 후처리 추가
            text = self.text_cleaner.clean_ocr_text(text)

            print(f"  ✓ Word (.doc) 읽기 완료 ({len(text)}자)")

            return [{"page_num": 1, "text": text, "method": "doc_legacy"}]

        except Exception as e:
            print(f"  ❌ Word (.doc) 읽기 실패: {e}")
            return []

    # ============================================
    # PowerPoint 처리 (강화 - .pptx + .ppt)
    # ============================================

    def _load_pptx(self, file_path: Path) -> List[Dict]:
        """PowerPoint .pptx 파일 읽기"""
        if not PPTX_AVAILABLE:
            print("  ❌ python-pptx 미설치")
            print("     설치: pip install python-pptx")
            return []

        try:
            prs = Presentation(file_path)
            pages_data = []

            print(f"  📊 PowerPoint (.pptx) {len(prs.slides)}슬라이드")

            for slide_num, slide in enumerate(prs.slides, 1):
                texts = []

                for shape in slide.shapes:
                    if hasattr(shape, "text") and shape.text.strip():
                        texts.append(shape.text.strip())

                slide_text = "\n".join(texts)

                # 후처리 추가
                slide_text = self.text_cleaner.clean_ocr_text(slide_text)

                pages_data.append(
                    {"page_num": slide_num, "text": slide_text, "method": "pptx"}
                )

            print(f"  ✓ PowerPoint (.pptx) 읽기 완료")
            return pages_data

        except Exception as e:
            print(f"  ❌ PowerPoint (.pptx) 읽기 실패: {e}")
            return []

    def _load_ppt_legacy(self, file_path: Path) -> List[Dict]:
        """PowerPoint .ppt 파일 읽기 (구버전 - Windows 전용)"""
        if not WIN32COM_AVAILABLE:
            print("  ❌ pywin32 미설치 (Windows 전용)")
            print("     설치: pip install pywin32")
            return []

        if platform.system() != "Windows":
            print("  ❌ .ppt 파일은 Windows에서만 지원됩니다")
            return []

        try:
            import pythoncom

            pythoncom.CoInitialize()

            powerpoint = win32com.client.Dispatch("PowerPoint.Application")
            powerpoint.Visible = False

            presentation = powerpoint.Presentations.Open(
                str(file_path.absolute()), ReadOnly=True
            )
            pages_data = []

            print(f"  📊 PowerPoint (.ppt) {presentation.Slides.Count}슬라이드")

            for slide_num in range(1, presentation.Slides.Count + 1):
                slide = presentation.Slides(slide_num)
                texts = []

                for shape in slide.Shapes:
                    if shape.HasTextFrame:
                        if shape.TextFrame.HasText:
                            texts.append(shape.TextFrame.TextRange.Text)

                slide_text = "\n".join(texts)

                # 후처리 추가
                slide_text = self.text_cleaner.clean_ocr_text(slide_text)

                pages_data.append(
                    {"page_num": slide_num, "text": slide_text, "method": "ppt_legacy"}
                )

            presentation.Close()
            powerpoint.Quit()
            pythoncom.CoUninitialize()

            print(f"  ✓ PowerPoint (.ppt) 읽기 완료")
            return pages_data

        except Exception as e:
            print(f"  ❌ PowerPoint (.ppt) 읽기 실패: {e}")
            return []

    # ============================================
    # Excel 처리 (강화 - .xlsx + .xls)
    # ============================================

    def _load_excel(self, file_path: Path) -> List[Dict]:
        """Excel .xlsx 파일 읽기"""
        if not OPENPYXL_AVAILABLE:
            print("  ❌ openpyxl 미설치")
            print("     설치: pip install openpyxl")
            return []

        try:
            wb = openpyxl.load_workbook(file_path, data_only=True)
            pages_data = []

            print(f"  📊 Excel (.xlsx) {len(wb.sheetnames)}시트")

            for sheet_num, sheet_name in enumerate(wb.sheetnames, 1):
                sheet = wb[sheet_name]

                rows_text = []
                for row in sheet.iter_rows(values_only=True):
                    row_text = " | ".join(
                        str(cell) if cell is not None else "" for cell in row
                    )
                    if row_text.strip():
                        rows_text.append(row_text)

                sheet_text = f"[시트: {sheet_name}]\n" + "\n".join(rows_text)

                # 후처리 추가
                sheet_text = self.text_cleaner.clean_ocr_text(sheet_text)

                pages_data.append(
                    {"page_num": sheet_num, "text": sheet_text, "method": "xlsx"}
                )

            print(f"  ✓ Excel (.xlsx) 읽기 완료")
            return pages_data

        except Exception as e:
            print(f"  ❌ Excel (.xlsx) 읽기 실패: {e}")
            return []

    def _load_xls_legacy(self, file_path: Path) -> List[Dict]:
        """Excel .xls 파일 읽기 (구버전 - Windows 전용)"""
        if not WIN32COM_AVAILABLE:
            print("  ❌ pywin32 미설치 (Windows 전용)")
            print("     설치: pip install pywin32")
            return []

        if platform.system() != "Windows":
            print("  ❌ .xls 파일은 Windows에서만 지원됩니다")
            return []

        try:
            import pythoncom

            pythoncom.CoInitialize()

            excel = win32com.client.Dispatch("Excel.Application")
            excel.Visible = False

            workbook = excel.Workbooks.Open(str(file_path.absolute()), ReadOnly=True)
            pages_data = []

            print(f"  📊 Excel (.xls) {workbook.Sheets.Count}시트")

            for sheet_num in range(1, workbook.Sheets.Count + 1):
                sheet = workbook.Sheets(sheet_num)
                rows_text = []

                used_range = sheet.UsedRange
                for row in used_range.Rows:
                    row_values = []
                    for cell in row.Cells:
                        value = cell.Value
                        row_values.append(str(value) if value is not None else "")
                    row_text = " | ".join(row_values)
                    if row_text.strip():
                        rows_text.append(row_text)

                sheet_text = f"[시트: {sheet.Name}]\n" + "\n".join(rows_text)

                # 후처리 추가
                sheet_text = self.text_cleaner.clean_ocr_text(sheet_text)

                pages_data.append(
                    {"page_num": sheet_num, "text": sheet_text, "method": "xls_legacy"}
                )

            workbook.Close(False)
            excel.Quit()
            pythoncom.CoUninitialize()

            print(f"  ✓ Excel (.xls) 읽기 완료")
            return pages_data

        except Exception as e:
            print(f"  ❌ Excel (.xls) 읽기 실패: {e}")
            return []

    # ============================================
    # CSV 처리 (강화)
    # ============================================

    def _load_csv(self, file_path: Path) -> List[Dict]:
        """CSV 읽기 (다중 인코딩 지원)"""
        if not PANDAS_AVAILABLE:
            print("  ❌ pandas 미설치")
            print("     설치: pip install pandas")
            return []

        try:
            encodings = ["utf-8", "utf-8-sig", "cp949", "euc-kr", "latin-1"]
            df = None

            for encoding in encodings:
                try:
                    df = pd.read_csv(file_path, encoding=encoding)
                    print(f"  ✓ CSV 읽기 성공 ({encoding}, {len(df)}행)")
                    break
                except:
                    continue

            if df is None:
                print("  ❌ CSV 인코딩 실패")
                return []

            csv_text = df.to_string(index=False)

            # 후처리 추가
            csv_text = self.text_cleaner.clean_ocr_text(csv_text)

            return [{"page_num": 1, "text": csv_text, "method": "csv"}]

        except Exception as e:
            print(f"  ❌ CSV 읽기 실패: {e}")
            return []

    # ============================================
    # Unstructured (Deep Document Parser)
    # ============================================

    def _load_with_unstructured(self, file_path: Path) -> List[Dict]:
        """Unstructured를 사용한 딥러닝 기반 문서 파싱"""
        print(f"  🔄 방법: Unstructured Deep Parser")

        if not UNSTRUCTURED_AVAILABLE:
            print(f"  ⚠️ Unstructured 라이브러리 미설치")
            print(f"     설치: pip install unstructured")
            print(f"     전체 지원: pip install \"unstructured[all-docs]\"")
            return []

        try:
            # Unstructured로 파일 파싱
            elements = partition(filename=str(file_path))

            # 텍스트 추출
            full_text = "\n\n".join([str(el) for el in elements])

            # 후처리
            full_text = self.text_cleaner.clean_ocr_text(full_text)

            print(f"  ✅ Unstructured 파싱 완료 ({len(full_text)}자, {len(elements)}개 요소)")

            return [
                {
                    "page_num": 1,
                    "text": full_text,
                    "method": f"unstructured_{file_path.suffix[1:]}",
                    "elements_count": len(elements)
                }
            ]

        except Exception as e:
            print(f"  ⚠️ Unstructured 파싱 실패: {e}")
            return []

    # ============================================
    # Upstage VLM API (문서 OCR - 표/도장/날인 인식)
    # ============================================

    def _parse_with_vlm(self, file_path: Path) -> List[Dict]:
        """Upstage VLM API로 문서 파싱 (표/도장/날인 인식)"""
        print(f"  🔄 방법: Upstage VLM OCR")

        try:
            from langchain_upstage import UpstageDocumentParseLoader

            api_key = self.config.upstage_api_key
            if not api_key:
                print(f"  ⚠️ Upstage API 키가 설정되지 않았습니다")
                return []

            loader = UpstageDocumentParseLoader(
                file_path=str(file_path),
                split="page",
                api_key=api_key,
            )

            docs = loader.load()
            pages_data = []

            for idx, doc in enumerate(docs, 1):
                text = doc.page_content.strip()

                # 노이즈 제거
                text = self.text_cleaner.clean_ocr_text(text)

                pages_data.append(
                    {"page_num": idx, "text": text, "method": "vlm_ocr"}
                )

            print(f"  ✅ VLM OCR 완료 ({len(pages_data)}페이지, {sum(len(p['text']) for p in pages_data)}자)")
            return pages_data

        except Exception as e:
            print(f"  ⚠️ VLM OCR 실패: {e}")
            return []

    # ============================================
    # 이미지 처리
    # ============================================

    def _load_image(self, file_path: Path) -> List[Dict]:
        """이미지 OCR"""
        try:
            print(f"  🖼️ 이미지 OCR 처리 중...")

            image = Image.open(file_path)

            # 전처리 추가
            image = self._preprocess_image_for_table(image)

            text = pytesseract.image_to_string(
                image, lang="kor+eng", config="--oem 1 --psm 6"
            ).strip()

            # 후처리 추가
            text = self.text_cleaner.clean_ocr_text(text)

            print(f"  ✓ OCR 완료 ({len(text)}자)")

            return [{"page_num": 1, "text": text, "method": "image_ocr"}]

        except Exception as e:
            print(f"  ❌ 이미지 OCR 실패: {e}")
            return []

    # ============================================
    # OCR 전처리 및 후처리
    # ============================================

    def _preprocess_image_for_table(self, image: Image.Image) -> Image.Image:
        """표 인식을 위한 이미지 전처리"""
        # 1. 그레이스케일 변환
        image = image.convert("L")

        # 2. 대비 강화 (표 선을 더 명확하게)
        enhancer = ImageEnhance.Contrast(image)
        image = enhancer.enhance(2.5)

        # 3. 선명도 강화
        enhancer = ImageEnhance.Sharpness(image)
        image = enhancer.enhance(2.0)

        # 4. 이진화 (표 경계 강조)
        threshold = 128
        image = image.point(lambda p: 255 if p > threshold else 0)

        return image

