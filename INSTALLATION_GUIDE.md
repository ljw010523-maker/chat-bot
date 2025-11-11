# 설치 가이드 (Installation Guide)

## 📋 시스템 요구사항

- **Python**: 3.8 이상
- **OS**: Windows 10/11 (HWP 처리는 Windows 전용)
- **RAM**: 최소 8GB (AI 모델 사용 시 16GB 권장)
- **디스크**: 최소 5GB 여유 공간

---

## 🚀 1단계: 기본 환경 설정

### 1.1 Python 설치 확인
```bash
python --version
```

출력: `Python 3.8.x` 이상이어야 함

### 1.2 가상환경 생성 (권장)
```bash
cd c:\Users\bravo\Desktop\test
python -m venv venv
```

### 1.3 가상환경 활성화

**Windows (PowerShell):**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows (명령 프롬프트):**
```cmd
venv\Scripts\activate
```

**Linux/Mac:**
```bash
source venv/bin/activate
```

---

## 📦 2단계: Python 패키지 설치

### 2.1 requirements.txt로 일괄 설치
```bash
pip install -r requirements.txt
```

### 2.2 개별 설치 (문제 발생 시)

#### 핵심 문서 처리
```bash
pip install PyPDF2 pdf2image pytesseract Pillow chardet
```

#### Office 문서 처리
```bash
pip install python-docx python-pptx openpyxl pandas
```

#### HWP 파일 처리
```bash
pip install olefile
```

**Windows 전용 (한글, 구버전 Office):**
```bash
pip install pywin32
```

#### Google Cloud Vision API
```bash
pip install google-cloud-vision
```

#### 텍스트 정제 (Privacy Filter)
```bash
pip install transformers torch
```

#### 의미 기반 청킹 (Semantic Chunking)
```bash
pip install langchain langdetect spacy
```

#### 기타
```bash
pip install requests
```

---

## 🔧 3단계: 외부 도구 설치

### 3.1 Tesseract OCR 설치

#### Windows
1. [Tesseract 다운로드 페이지](https://github.com/UB-Mannheim/tesseract/wiki) 접속
2. 최신 버전 설치 파일 다운로드 (예: `tesseract-ocr-w64-setup-5.3.3.exe`)
3. 설치 진행
4. 한국어 언어팩 체크 (Korean, Korean (vertical) 선택)
5. 설치 경로 확인: `C:\Program Files\Tesseract-OCR\`

#### 설치 확인
```bash
tesseract --version
```

### 3.2 Poppler 설치 (PDF → 이미지 변환)

#### Windows
1. [Poppler 다운로드](https://github.com/oschwartz10612/poppler-windows/releases/) 접속
2. 최신 릴리스 다운로드 (예: `poppler-xx.xx.x-x.zip`)
3. `C:\Program Files\` 폴더에 압축 해제
4. 경로 예시: `C:\Program Files\poppler-25.07.0\Library\bin`

#### 환경 변수 설정 (선택)
1. **시스템 속성** → **고급** → **환경 변수**
2. **Path** 변수에 Poppler bin 경로 추가:
   ```
   C:\Program Files\poppler-25.07.0\Library\bin
   ```

---

## 🤖 4단계: spaCy 언어 모델 설치

### 4.1 한국어 모델
```bash
python -m spacy download ko_core_news_sm
```

### 4.2 영어 모델
```bash
python -m spacy download en_core_web_sm
```

### 4.3 설치 확인
```python
python -c "import spacy; nlp = spacy.load('ko_core_news_sm'); print('한국어 모델 로드 성공')"
```

---

## 🔑 5단계: Google Cloud Vision API 설정

자세한 내용은 **[GOOGLE_VISION_SETUP.md](GOOGLE_VISION_SETUP.md)** 참고

### 요약
1. Google Cloud 프로젝트 생성
2. Vision API 활성화
3. 서비스 계정 생성 및 JSON 키 다운로드
4. 환경 변수 설정:
   ```bash
   set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\key.json
   ```

---

## 📁 6단계: 폴더 구조 확인

```
c:\Users\bravo\Desktop\test\
├── back/
│   └── scripts/
│       ├── ingest/          # 문서 로더
│       ├── clean/           # 텍스트 정제
│       ├── chunk/           # 청킹
│       ├── normalize/       # 정규화
│       ├── pipeline/        # 통합 파이프라인
│       └── utils/           # 설정
├── data/
│   ├── raw/                 # 원본 문서 (여기에 파일 넣기)
│   └── chunks/              # 처리 결과
├── requirements.txt
├── INSTALLATION_GUIDE.md
└── GOOGLE_VISION_SETUP.md
```

### 필수 폴더 생성
```bash
mkdir data\raw
mkdir data\chunks
```

---

## 🧪 7단계: 설치 확인 테스트

### 7.1 전체 임포트 테스트
```python
# test_imports.py
print("기본 라이브러리 테스트...")
import PyPDF2
import pytesseract
from PIL import Image
print("✓ 기본 라이브러리 OK")

print("\nOffice 문서 라이브러리 테스트...")
import docx
from pptx import Presentation
import openpyxl
import pandas as pd
print("✓ Office 문서 라이브러리 OK")

print("\nHWP 라이브러리 테스트...")
import olefile
print("✓ HWP 라이브러리 OK")

print("\nGoogle Vision API 테스트...")
from google.cloud import vision
print("✓ Google Vision API OK")

print("\nAI 모델 라이브러리 테스트...")
import transformers
import torch
print("✓ AI 모델 라이브러리 OK")

print("\nSemantic Chunking 라이브러리 테스트...")
from langchain.text_splitter import RecursiveCharacterTextSplitter
import langdetect
import spacy
print("✓ Semantic Chunking 라이브러리 OK")

print("\nspaCy 모델 로드 테스트...")
nlp_ko = spacy.load('ko_core_news_sm')
nlp_en = spacy.load('en_core_web_sm')
print("✓ spaCy 모델 로드 OK")

print("\n✅ 모든 라이브러리 설치 완료!")
```

실행:
```bash
python test_imports.py
```

### 7.2 파이프라인 테스트
```bash
# 테스트 문서를 data/raw/ 폴더에 넣기
cp test.pdf data/raw/

# 파이프라인 실행
cd back/scripts/pipeline
python pipeline.py
```

결과는 `data/chunks/` 폴더에 생성됩니다.

---

## 🔍 트러블슈팅

### 문제 1: Tesseract 경로 오류
**증상**: `TesseractNotFoundError`

**해결**:
[document_loader.py](back/scripts/ingest/document_loader.py)의 78번째 줄 확인:
```python
pytesseract.pytesseract.tesseract_cmd = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
```

설치 경로에 맞게 수정하세요.

### 문제 2: Poppler 경로 오류
**증상**: `PDFInfoNotInstalledError` 또는 `PDFPageCountError`

**해결**:
[document_loader.py](back/scripts/ingest/document_loader.py)의 84-89번째 줄 확인:
```python
POPPLER_PATH = r"C:\Program Files\poppler-25.07.0\Library\bin"
```

실제 설치 경로로 수정하세요.

### 문제 3: spaCy 모델 없음
**증상**: `OSError: [E050] Can't find model 'ko_core_news_sm'`

**해결**:
```bash
python -m spacy download ko_core_news_sm
python -m spacy download en_core_web_sm
```

### 문제 4: Google Vision API 인증 오류
**증상**: `google.auth.exceptions.DefaultCredentialsError`

**해결**:
환경 변수 설정 확인:
```bash
echo %GOOGLE_APPLICATION_CREDENTIALS%
```

비어있다면:
```bash
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\your\key.json
```

### 문제 5: PyTorch CUDA 오류 (GPU 사용 시)
**증상**: `RuntimeError: CUDA out of memory`

**해결**:
CPU 버전 사용:
```bash
pip uninstall torch
pip install torch --index-url https://download.pytorch.org/whl/cpu
```

### 문제 6: transformers 모델 다운로드 느림
**증상**: Hugging Face 모델 다운로드가 매우 느림

**해결**:
캐시 폴더 확인:
```bash
set HF_HOME=C:\HuggingFace
```

---

## 📊 설치 확인 체크리스트

- [ ] Python 3.8+ 설치
- [ ] 가상환경 생성 및 활성화
- [ ] requirements.txt 패키지 설치
- [ ] Tesseract OCR 설치 (한국어 언어팩 포함)
- [ ] Poppler 설치
- [ ] spaCy 한국어/영어 모델 다운로드
- [ ] Google Cloud Vision API 설정 (JSON 키 + 환경 변수)
- [ ] `data/raw/` 및 `data/chunks/` 폴더 생성
- [ ] `test_imports.py` 실행 성공
- [ ] 파이프라인 테스트 실행 성공

---

## 🎯 다음 단계

설치가 완료되면:

1. **문서 준비**: `data/raw/` 폴더에 처리할 문서 복사
2. **파이프라인 실행**:
   ```bash
   cd back/scripts/pipeline
   python pipeline.py
   ```
3. **결과 확인**: `data/chunks/` 폴더에서 JSON 파일 확인
4. **다음 작업**:
   - 벡터 임베딩 모델 선택
   - 벡터 DB 구축 (ChromaDB/FAISS)
   - RAG 파이프라인 구현

---

## 📚 참고 문서

- [GOOGLE_VISION_SETUP.md](GOOGLE_VISION_SETUP.md) - Google Vision API 상세 설정 가이드
- [requirements.txt](requirements.txt) - 필요 패키지 목록

문제가 발생하면 위 트러블슈팅 섹션을 먼저 확인하세요!
