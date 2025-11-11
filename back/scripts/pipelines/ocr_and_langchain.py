import os
import re
from pathlib import Path
from typing import List, Dict, Optional
import PyPDF2
from pdf2image import convert_from_path
import pytesseract
from PIL import Image
import json
import platform

# LangChain imports
try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False
    print("⚠️ LangChain이 설치되지 않았습니다. 기본 분할 방식을 사용합니다.")
    print("   설치: pip install langchain")

# ============================================
# Windows: Tesseract 및 Poppler 경로 설정
# ============================================
if platform.system() == 'Windows':
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    
    # Poppler 경로 자동 찾기
    import glob
    poppler_search = glob.glob(r'C:\Program Files\poppler-*\Library\bin')
    if poppler_search:
        POPPLER_PATH = poppler_search[0]
    else:
        POPPLER_PATH = r'C:\Program Files\poppler-25.07.0\Library\bin'
else:
    POPPLER_PATH = None


class HybridPDFProcessor:
    """
    하이브리드 PDF 처리기
    - OCR: 커스텀 구현 (Tesseract)
    - 청크 분할: LangChain (옵션) 또는 기본 방식
    """
    
    def __init__(
        self, 
        raw_folder: str = "data/raw", 
        output_folder: str = "data/chunks",
        use_langchain: bool = True,
        chunk_size: int = 500,  # 스캔본이므로 작게
        chunk_overlap: int = 50,  # 오버랩 줄임
        ocr_dpi: int = 300
    ):
        self.raw_folder = Path(raw_folder)
        self.output_folder = Path(output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)
        
        self.use_langchain = use_langchain and LANGCHAIN_AVAILABLE
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap
        self.ocr_dpi = ocr_dpi
        
        # LangChain TextSplitter 초기화
        if self.use_langchain:
            self.text_splitter = RecursiveCharacterTextSplitter(
                chunk_size=chunk_size,
                chunk_overlap=chunk_overlap,
                separators=[
                    "\n\n",  # 문단 구분
                    "\n",    # 줄바꿈
                    "。",    # 한국어 마침표
                    ". ",    # 영어 마침표
                    "! ",    # 느낌표
                    "? ",    # 물음표
                    "， ",   # 쉼표
                    ", ",
                    " ",     # 공백
                    ""       # 마지막 수단
                ],
                length_function=len,
                is_separator_regex=False
            )
            print(f"✓ LangChain 분할 모드 활성화 (chunk_size={chunk_size}, overlap={chunk_overlap})")
        else:
            print(f"✓ 기본 분할 모드 (chunk_size={chunk_size}, overlap={chunk_overlap})")
    
    # ============================================
    # OCR 관련 메서드 (커스텀 구현 유지)
    # ============================================
    
    def extract_text_from_pdf(self, pdf_path: Path) -> List[Dict]:
        """PDF에서 텍스트 추출 (PyPDF2 우선, 실패시 OCR)"""
        pages_data = []
        
        try:
            with open(pdf_path, 'rb') as file:
                pdf_reader = PyPDF2.PdfReader(file)
                total_pages = len(pdf_reader.pages)
                
                print(f"  📑 총 {total_pages}페이지 발견")
                
                # 첫 페이지로 스캔본 여부 판단
                first_page_text = pdf_reader.pages[0].extract_text().strip()
                
                if len(first_page_text) < 50:
                    print("  ⚠️ 스캔본 PDF로 감지됨 → 전체 OCR 모드")
                    return self._ocr_entire_pdf(pdf_path)
                
                # 텍스트 기반 PDF - 페이지별 처리
                print("  ✓ 텍스트 기반 PDF로 감지됨")
                for page_num, page in enumerate(pdf_reader.pages, 1):
                    text = page.extract_text().strip()
                    
                    if len(text) < 50:
                        print(f"    페이지 {page_num}: 텍스트 부족 → OCR 사용")
                        text = self._ocr_page(pdf_path, page_num)
                        method = 'ocr'
                    else:
                        method = 'extraction'
                    
                    pages_data.append({
                        'page_num': page_num,
                        'text': text,
                        'method': method
                    })
                    
        except Exception as e:
            print(f"  ❌ PyPDF2 처리 실패: {e}")
            print("  🔄 OCR 모드로 전환합니다...")
            pages_data = self._ocr_entire_pdf(pdf_path)
            
        return pages_data
    
    def _ocr_page(self, pdf_path: Path, page_num: int) -> str:
        """특정 페이지에 대해 OCR 수행"""
        try:
            if platform.system() == 'Windows':
                images = convert_from_path(
                    pdf_path, 
                    first_page=page_num, 
                    last_page=page_num,
                    dpi=self.ocr_dpi,
                    poppler_path=POPPLER_PATH
                )
            else:
                images = convert_from_path(
                    pdf_path, 
                    first_page=page_num, 
                    last_page=page_num,
                    dpi=self.ocr_dpi
                )
            
            if images:
                # 한글+영어 OCR
                custom_config = r'--oem 3 --psm 6'
                text = pytesseract.image_to_string(
                    images[0], 
                    lang='kor+eng',
                    config=custom_config
                )
                
                if text.strip():
                    print(f"      ✓ 성공 (추출: {len(text)} 자)")
                else:
                    print(f"      ⚠️ 텍스트 없음")
                
                return text.strip()
            else:
                print(f"      ❌ 이미지 변환 실패")
                return ""
                
        except Exception as e:
            print(f"      ❌ OCR 실패: {e}")
            return ""
    
    def _ocr_entire_pdf(self, pdf_path: Path) -> List[Dict]:
        """전체 PDF에 대해 OCR 수행"""
        pages_data = []
        
        try:
            print("  🔍 PDF를 이미지로 변환 중...")
            
            if platform.system() == 'Windows':
                images = convert_from_path(
                    pdf_path, 
                    dpi=self.ocr_dpi,
                    poppler_path=POPPLER_PATH
                )
            else:
                images = convert_from_path(pdf_path, dpi=self.ocr_dpi)
            
            print(f"  ✓ {len(images)}개 페이지 변환 완료")
            print("  🔤 OCR 텍스트 추출 중...")
            
            for page_num, image in enumerate(images, 1):
                print(f"    페이지 {page_num}/{len(images)}...", end=" ")
                
                try:
                    custom_config = r'--oem 3 --psm 6'
                    text = pytesseract.image_to_string(
                        image, 
                        lang='kor+eng',
                        config=custom_config
                    )
                    
                    text = text.strip()
                    
                    if text:
                        print(f"✓ (추출: {len(text)} 자)")
                    else:
                        print("⚠️ 텍스트 없음")
                    
                    pages_data.append({
                        'page_num': page_num,
                        'text': text,
                        'method': 'ocr'
                    })
                    
                except Exception as e:
                    print(f"❌ 실패: {e}")
                    pages_data.append({
                        'page_num': page_num,
                        'text': '',
                        'method': 'ocr_failed'
                    })
                
        except Exception as e:
            print(f"  ❌ 전체 OCR 실패: {e}")
            
        return pages_data
    
    # ============================================
    # 텍스트 정제
    # ============================================
    
    def clean_text(self, text: str) -> str:
        """텍스트 정제 - OCR 노이즈 제거"""
        if not text:
            return ""
        
        # 1. 연속된 공백을 하나로
        text = re.sub(r' +', ' ', text)
        
        # 2. 탭 문자 제거
        text = text.replace('\t', ' ')
        
        # 3. 연속된 줄바꿈을 최대 2개로 제한
        text = re.sub(r'\n{3,}', '\n\n', text)
        
        # 4. 각 줄의 앞뒤 공백 제거
        lines = [line.strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)  # 빈 줄 제거
        
        # 5. OCR 특수 노이즈 제거 (선택적)
        # text = re.sub(r'[^\w\s\n.,!?()[\]{}\-:;\'\"가-힣]', '', text)
        
        return text.strip()
    
    # ============================================
    # 청크 분할 (하이브리드)
    # ============================================
    
    def split_into_chunks_langchain(self, pages_data: List[Dict]) -> List[Dict]:
        """LangChain을 사용한 스마트 청크 분할"""
        chunks = []
        chunk_id = 0
        
        for page_data in pages_data:
            text = self.clean_text(page_data['text'])
            page_num = page_data['page_num']
            
            if not text:
                chunks.append({
                    'chunk_id': chunk_id,
                    'page_num': page_num,
                    'text': '',
                    'char_count': 0,
                    'warning': 'no_text_extracted'
                })
                chunk_id += 1
                continue
            
            # LangChain으로 의미 단위 분할
            split_texts = self.text_splitter.split_text(text)
            
            for split_text in split_texts:
                chunks.append({
                    'chunk_id': chunk_id,
                    'page_num': page_num,
                    'text': split_text,
                    'char_count': len(split_text),
                    'split_method': 'langchain'
                })
                chunk_id += 1
        
        return chunks
    
    def split_into_chunks_basic(self, pages_data: List[Dict]) -> List[Dict]:
        """기본 청크 분할 (폴백)"""
        chunks = []
        chunk_id = 0
        
        for page_data in pages_data:
            text = self.clean_text(page_data['text'])
            page_num = page_data['page_num']
            
            if not text:
                chunks.append({
                    'chunk_id': chunk_id,
                    'page_num': page_num,
                    'text': '',
                    'char_count': 0,
                    'warning': 'no_text_extracted'
                })
                chunk_id += 1
                continue
            
            # 청크 크기보다 작으면 그대로
            if len(text) <= self.chunk_size:
                chunks.append({
                    'chunk_id': chunk_id,
                    'page_num': page_num,
                    'text': text,
                    'char_count': len(text),
                    'split_method': 'basic'
                })
                chunk_id += 1
            else:
                # 오버랩 방식 분할
                start = 0
                while start < len(text):
                    end = min(start + self.chunk_size, len(text))
                    chunk_text = text[start:end]
                    
                    chunks.append({
                        'chunk_id': chunk_id,
                        'page_num': page_num,
                        'text': chunk_text,
                        'char_count': len(chunk_text),
                        'split_method': 'basic'
                    })
                    
                    chunk_id += 1
                    
                    if end >= len(text):
                        break
                        
                    start = end - self.chunk_overlap
        
        return chunks
    
    def split_into_chunks(self, pages_data: List[Dict]) -> List[Dict]:
        """청크 분할 라우터"""
        if self.use_langchain:
            return self.split_into_chunks_langchain(pages_data)
        else:
            return self.split_into_chunks_basic(pages_data)
    
    # ============================================
    # 처리 파이프라인
    # ============================================
    
    def process_pdf(self, pdf_filename: str) -> Optional[Dict]:
        """PDF 파일 전체 처리 파이프라인"""
        pdf_path = self.raw_folder / pdf_filename
        
        if not pdf_path.exists():
            raise FileNotFoundError(f"PDF 파일을 찾을 수 없습니다: {pdf_path}")
        
        print(f"\n{'='*60}")
        print(f"📄 처리 중: {pdf_filename}")
        print(f"{'='*60}")
        
        # 1. 텍스트 추출 (OCR)
        print("\n[1단계] 텍스트 추출")
        pages_data = self.extract_text_from_pdf(pdf_path)
        
        if not pages_data:
            print("  ❌ 텍스트 추출 실패!")
            return None
        
        # 2. 청크 분할
        print(f"\n[2단계] 청크 분할 ({'LangChain' if self.use_langchain else '기본'} 모드)")
        chunks = self.split_into_chunks(pages_data)
        
        # 3. 통계
        total_chars = sum(chunk['char_count'] for chunk in chunks if 'char_count' in chunk)
        non_empty_chunks = sum(1 for chunk in chunks if chunk.get('text'))
        avg_chunk_size = total_chars / non_empty_chunks if non_empty_chunks > 0 else 0
        
        print(f"  ✓ 총 {len(chunks)}개 청크 생성")
        print(f"  ✓ 텍스트 있는 청크: {non_empty_chunks}개")
        print(f"  ✓ 총 추출 문자 수: {total_chars:,} 자")
        print(f"  ✓ 평균 청크 크기: {avg_chunk_size:.0f} 자")
        
        # 4. 결과 저장
        output_data = {
            'source_file': pdf_filename,
            'total_pages': len(pages_data),
            'total_chunks': len(chunks),
            'total_characters': total_chars,
            'average_chunk_size': round(avg_chunk_size, 2),
            'chunks': chunks,
            'processing_info': {
                'chunk_size': self.chunk_size,
                'chunk_overlap': self.chunk_overlap,
                'ocr_dpi': self.ocr_dpi,
                'split_method': 'langchain' if self.use_langchain else 'basic',
                'methods_used': list(set(p['method'] for p in pages_data))
            }
        }
        
        # JSON 저장
        output_filename = pdf_path.stem + '_chunks.json'
        output_path = self.output_folder / output_filename
        
        print("\n[3단계] 파일 저장")
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)
        
        print(f"  ✓ 저장 완료: {output_path}")
        
        return output_data
    
    def process_all_pdfs(self):
        """raw 폴더의 모든 PDF 처리"""
        pdf_files = list(self.raw_folder.glob("*.pdf"))
        
        if not pdf_files:
            print("\n❌ 처리할 PDF 파일이 없습니다.")
            print(f"   경로 확인: {self.raw_folder.absolute()}")
            return []
        
        print(f"\n{'='*60}")
        print(f"🚀 하이브리드 PDF 처리 시작")
        print(f"{'='*60}")
        print(f"📁 대상 폴더: {self.raw_folder.absolute()}")
        print(f"📊 발견된 파일: {len(pdf_files)}개")
        print(f"⚙️ 청크 설정: size={self.chunk_size}, overlap={self.chunk_overlap}")
        print(f"🔧 OCR DPI: {self.ocr_dpi}")
        print(f"{'='*60}")
        
        results = []
        success_count = 0
        
        for idx, pdf_file in enumerate(pdf_files, 1):
            print(f"\n[{idx}/{len(pdf_files)}]")
            try:
                result = self.process_pdf(pdf_file.name)
                if result:
                    results.append(result)
                    success_count += 1
            except Exception as e:
                print(f"\n❌ 오류 발생: {e}")
                import traceback
                traceback.print_exc()
                continue
        
        # 최종 요약
        print(f"\n{'='*60}")
        print(f"✅ 처리 완료!")
        print(f"{'='*60}")
        print(f"  성공: {success_count}/{len(pdf_files)}개")
        print(f"  실패: {len(pdf_files) - success_count}개")
        
        if results:
            total_chunks = sum(r['total_chunks'] for r in results)
            total_chars = sum(r['total_characters'] for r in results)
            print(f"  총 생성된 청크: {total_chunks}개")
            print(f"  총 추출 문자: {total_chars:,}자")
        
        print(f"  저장 위치: {self.output_folder.absolute()}")
        print(f"{'='*60}\n")
        
        return results


# ============================================
# 사용 예시
# ============================================

def main():
    """메인 실행 함수"""
    
    # 방법 1: LangChain 사용 (권장 - 스캔본 최적화)
    processor = HybridPDFProcessor(
        raw_folder="data/raw",
        output_folder="data/chunks",
        use_langchain=True,      # LangChain 사용
        chunk_size=500,          # 스캔본이므로 작게 (기존 1000 → 500)
        chunk_overlap=50,        # 오버랩 줄임 (기존 200 → 50)
        ocr_dpi=300              # OCR 해상도
    )
    
    # 방법 2: 기본 방식 사용
    # processor = HybridPDFProcessor(
    #     raw_folder="data/raw",
    #     output_folder="data/chunks",
    #     use_langchain=False,
    #     chunk_size=400,
    #     chunk_overlap=30,
    #     ocr_dpi=300
    # )
    
    # 모든 PDF 처리
    processor.process_all_pdfs()


if __name__ == "__main__":
    main()