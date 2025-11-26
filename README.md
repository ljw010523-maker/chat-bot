# 📚 Document Processing Pipeline

다양한 형식의 문서를 자동으로 처리하여 텍스트 추출, 정제, 청크 분할을 수행하는 파이프라인 시스템입니다. RAG(Retrieval-Augmented Generation) 챗봇 구축을 위한 전처리 도구로 설계되었습니다.

## ✨ 주요 기능

### 📄 문서 처리
- **13가지 파일 형식 지원**: PDF, DOCX, PPTX, XLSX, HWP, HWPX, TXT, CSV, 이미지 등
- **자동 형식 감지**: 파일 확장자에 따라 최적의 처리 방법 자동 선택
- **고급 OCR**: Google Cloud Vision API 기반 표/도장/날인 인식
- **HWP 완벽 지원**: 한글 문서 자동 변환 및 텍스트 추출 (Windows 전용)

### 🧹 텍스트 정제
- **기본 정제**: 공백, 줄바꿈, 특수문자 정리
- **OCR 노이즈 제거**: 의미 없는 문자, 반복 패턴 자동 제거
- **개인정보 필터링**: KLUE + GLiNER 기반 민감정보 마스킹 (선택적)
- **맞춤법 교정**: T5 기반 AI 자동 교정 (선택적)

### ✂️ 청크 분할
- **의미 기반 분할**: spaCy를 활용한 문맥 인식 청킹
- **문서 구조 인식**: 제목, 표, 리스트 자동 감지
- **메타데이터 추출**: 날짜, 작성자, 부서 등 자동 추출
- **LangChain 통합**: RecursiveCharacterTextSplitter 폴백 지원

## 🎯 지원 파일 형식

| 형식 | 확장자 | 처리 방법 |
|------|--------|-----------|
| **PDF** | `.pdf` | PyPDF2 → Google Vision API → Tesseract |
| **Word** | `.docx`, `.doc` | python-docx, win32com |
| **PowerPoint** | `.pptx`, `.ppt` | python-pptx, win32com |
| **Excel** | `.xlsx`, `.xls` | openpyxl, win32com |
| **한글** | `.hwp`, `.hwpx` | olefile → PDF 변환 → OCR |
| **이미지** | `.jpg`, `.png` | Tesseract OCR |
| **텍스트** | `.txt`, `.csv` | chardet (다중 인코딩) |

## 🚀 설치 방법

### 1️⃣ 필수 요구사항
- Python 3.8 이상
- Windows 10/11 (HWP 처리용, 선택적)
- Google Cloud Vision API 키

### 2️⃣ Python 패키지 설치
```bash
pip install -r requirements.txt
```

### 3️⃣ 외부 도구 설치 (선택적)

**Tesseract OCR** (로컬 OCR용):
```bash
# Windows
choco install tesseract

# 또는 다운로드: https://github.com/UB-Mannheim/tesseract/wiki
```

**Poppler** (PDF 이미지 변환용):
```bash
# Windows
choco install poppler

# 또는 다운로드 후 PATH 추가
```

### 4️⃣ Google Cloud Vision API 설정
1. [Google Cloud Console](https://console.cloud.google.com/)에서 프로젝트 생성
2. Cloud Vision API 활성화
3. 서비스 계정 키(JSON) 다운로드
4. 환경변수 설정:
```bash
set GOOGLE_APPLICATION_CREDENTIALS=경로\to\your-key.json
```

자세한 설정 방법은 [GOOGLE_VISION_SETUP.md](GOOGLE_VISION_SETUP.md) 참조

### 5️⃣ spaCy 언어 모델 설치
```bash
# 한국어 모델
python -m spacy download ko_core_news_sm

# 영어 모델 (선택)
python -m spacy download en_core_web_sm
```

## 📖 사용 방법

### 기본 사용법

1. **문서 파일 배치**
```
data/raw/
  ├── document1.pdf
  ├── report.hwp
  └── presentation.pptx
```

2. **파이프라인 실행**
```bash
python back/scripts/pipeline/pipeline.py
```

3. **결과 확인**
```
data/chunks/
  ├── document1_pdf_chunks.json
  ├── report_hwp_chunks.json
  └── presentation_pptx_chunks.json
```

### 통합 파이프라인 사용 (최신)
```bash
python back/scripts/pipelines/ocr_and_clean.py
```

### 출력 형식
```json
{
  "source_file": "document.pdf",
  "file_type": ".pdf",
  "total_pages": 10,
  "total_chunks": 25,
  "total_characters": 12500,
  "average_chunk_size": 500,
  "chunks": [
    {
      "chunk_id": 0,
      "text": "청크 내용...",
      "char_count": 485,
      "page_num": 1,
      "metadata": {
        "title": "문서 제목",
        "date": "2025-11-24"
      }
    }
  ],
  "processing_info": {
    "chunk_size": 800,
    "chunk_overlap": 120,
    "split_method": "langchain",
    "methods_used": ["google_vision_api"],
    "privacy_filtering": false
  }
}
```

## ⚙️ 설정

### Config 파일 수정
[back/scripts/utils/config.py](back/scripts/utils/config.py)
```python
class Config:
    # 경로 설정
    raw_folder = "data/raw"
    output_folder = "data/chunks"

    # 청크 설정
    chunk_size = 500          # 청크 크기 (글자 수)
    chunk_overlap = 100       # 청크 오버랩 (글자 수)
    use_langchain = True      # LangChain 청킹 사용

    # OCR 설정
    ocr_dpi = 300            # OCR 해상도

    # 필터링 (선택적)
    use_privacy_filter = False              # 개인정보 필터링
    use_hanspell_normalization = False      # 맞춤법 교정
```

### YAML 설정 (대안)
[configs/settings.yaml](configs/settings.yaml)
```yaml
paths:
  raw_dir: "data/raw"
  chunks_dir: "data/chunks"

ingest:
  enable_auto_ocr: true
  ocr_lang: "kor+eng"
  dpi: 300

chunk:
  size: 800
  overlap: 120
```

## 📁 프로젝트 구조

```
test/
├── back/
│   └── scripts/
│       ├── ingest/                    # 문서 로드
│       │   ├── document_loader.py     # 통합 로더 (모든 형식)
│       │   └── hwp_processor.py       # HWP 전용 처리기
│       │
│       ├── clean/                     # 텍스트 정제
│       │   ├── text_cleaner.py        # 기본 정제
│       │   └── privacy_filter.py      # 개인정보 필터링
│       │
│       ├── chunk/                     # 청크 분할
│       │   └── semantic_splitter.py   # 의미 기반 분할
│       │
│       ├── normalize/                 # 텍스트 정규화
│       │   └── ai_normalizer.py       # T5 맞춤법 교정
│       │
│       ├── pipeline/                  # 통합 파이프라인
│       │   └── pipeline.py            # 메인 파이프라인
│       │
│       ├── pipelines/                 # 개별 파이프라인
│       │   ├── ocr_and_clean.py       # 통합 처리 (최신)
│       │   ├── embed.py               # 벡터 임베딩 (미완성)
│       │   └── upload_to_db.py        # DB 업로드 (미완성)
│       │
│       └── utils/                     # 유틸리티
│           └── config.py              # 설정 관리
│
├── data/
│   ├── raw/                           # 원본 문서
│   └── chunks/                        # 처리 결과 (JSON)
│
├── configs/
│   └── settings.yaml                  # YAML 설정
│
├── README.md                          # 이 파일
├── INSTALLATION_GUIDE.md              # 상세 설치 가이드
├── GOOGLE_VISION_SETUP.md             # Google Vision API 설정
├── MIGRATION_SUMMARY.md               # Upstage → Google Vision 마이그레이션 기록
└── requirements.txt                   # Python 패키지 목록
```

## 🔧 핵심 모듈 설명

### 1. Document Loader
**파일**: [back/scripts/ingest/document_loader.py](back/scripts/ingest/document_loader.py)

모든 문서 형식을 자동으로 감지하고 텍스트를 추출합니다.
- **자동 형식 감지**: 확장자 기반 최적 처리 방법 선택
- **다단계 OCR 폴백**: Google Vision API → Tesseract
- **표 인식 최적화**: 이미지 전처리 (이진화, 대비 강화)
- **다중 인코딩 지원**: chardet으로 인코딩 자동 감지

### 2. HWP Processor
**파일**: [back/scripts/ingest/hwp_processor.py](back/scripts/ingest/hwp_processor.py)

한글 문서 전용 처리기 (Windows 전용):
- **olefile 방식**: PrvText 스트림 직접 추출
- **PDF 변환**: HWP → PDF → OCR
- **보안 설정 자동화**: 한글 보안 팝업 자동 클릭
- **XML 폴백**: HWPX ZIP 구조 파싱

### 3. Text Cleaner
**파일**: [back/scripts/clean/text_cleaner.py](back/scripts/clean/text_cleaner.py)

기본 텍스트 정제:
- 연속 공백/줄바꿈 제거
- OCR 노이즈 필터링 (의미 없는 문자 제거)
- 특수문자 정리

### 4. Semantic Splitter
**파일**: [back/scripts/chunk/semantic_splitter.py](back/scripts/chunk/semantic_splitter.py)

의미 기반 청크 분할:
- **spaCy 문장 분리**: 다국어 지원
- **문서 구조 인식**: 제목, 표, 리스트 감지
- **메타데이터 추출**: 날짜, 부서, 작성자 등
- **LangChain 폴백**: RecursiveCharacterTextSplitter

## 🧪 개발 상태

### ✅ 완성된 기능 (80%)
- [x] 다양한 문서 형식 로드
- [x] HWP 파일 처리 (Windows)
- [x] Google Cloud Vision API 통합
- [x] 텍스트 정제 및 OCR 노이즈 제거
- [x] 의미 기반 청크 분할
- [x] 개인정보 필터링 (비활성화 상태)
- [x] T5 맞춤법 교정 (비활성화 상태)
- [x] JSON 형식 결과 저장

### 🚧 진행 중 (20%)
- [ ] 벡터 임베딩 모듈 (`embed.py`)
- [ ] 벡터 DB 업로드 (`upload_to_db.py`)
- [ ] RAG 검색 시스템
- [ ] FastAPI 서버
- [ ] 단위 테스트 작성

## 🎯 향후 계획

### Phase 1: RAG 시스템 완성
1. **벡터 임베딩** - Sentence-Transformers 통합
2. **벡터 DB 연결** - Chroma, Pinecone, Weaviate 중 선택
3. **검색 모듈** - 유사도 기반 문서 검색

### Phase 2: API 서버 구축
1. **FastAPI 서버** - REST API 엔드포인트
2. **LangChain 통합** - RAG 체인 구성
3. **질의응답 시스템** - LLM 연동 챗봇

### Phase 3: 품질 개선
1. **단위 테스트** - pytest 기반 테스트 스위트
2. **에러 핸들링** - 안정성 강화
3. **성능 최적화** - 대용량 문서 처리

## 📚 참고 문서

- [설치 가이드](INSTALLATION_GUIDE.md) - 전체 시스템 설치 방법
- [Google Vision API 설정](GOOGLE_VISION_SETUP.md) - API 키 발급 및 설정
- [마이그레이션 기록](MIGRATION_SUMMARY.md) - Upstage → Google Vision 전환 과정

## 🤝 기여하기

버그 리포트, 기능 제안, 풀 리퀘스트 환영합니다!

## 📝 라이선스

MIT License

## 📧 문의

이슈를 등록해주세요.

---

**Made with ❤️ for RAG Chatbot Development**
