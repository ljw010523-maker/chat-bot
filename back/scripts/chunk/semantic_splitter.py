"""
의미 기반 텍스트 청크 분할 모듈
- 다국어 문장 분리 (spaCy)
- 문서 구조 인식 (제목, 표, 리스트, 섹션)
- 메타데이터 추출 (문서명, 날짜, 부서, 승인자)
- 의미 단위 병합 (문장 중간에서 안 자름)
"""

from typing import List, Dict, Optional, Tuple
import re
from datetime import datetime

# 언어 감지
try:
    from langdetect import detect, LangDetectException
    LANGDETECT_AVAILABLE = True
except ImportError:
    LANGDETECT_AVAILABLE = False

# spaCy (다국어 문장 분리)
try:
    import spacy
    SPACY_AVAILABLE = True
except ImportError:
    SPACY_AVAILABLE = False


class SemanticTextSplitter:
    """의미 기반 텍스트 분할기"""

    def __init__(self, config):
        self.config = config
        self.chunk_size = config.chunk_size
        self.chunk_overlap = config.chunk_overlap

        # spaCy 모델 로드
        self.nlp_models = {}
        if SPACY_AVAILABLE:
            try:
                self.nlp_models['ko'] = spacy.load("ko_core_news_sm")
                print("  ✓ spaCy 한국어 모델 로드 완료")
            except:
                print("  ⚠️ spaCy 한국어 모델 미설치")

            try:
                self.nlp_models['en'] = spacy.load("en_core_web_sm")
                print("  ✓ spaCy 영어 모델 로드 완료")
            except:
                print("  ⚠️ spaCy 영어 모델 미설치")

        if not self.nlp_models:
            print("  ⚠️ spaCy 모델이 없어 기본 분할 사용")

    def detect_language(self, text: str) -> str:
        """언어 감지 (한국어, 영어, 일본어 등)"""
        if not LANGDETECT_AVAILABLE or not text.strip():
            return 'ko'  # 기본값: 한국어

        try:
            lang = detect(text)
            # ko, en, ja 등
            return lang if lang in ['ko', 'en', 'ja'] else 'ko'
        except LangDetectException:
            return 'ko'

    def extract_metadata(self, text: str) -> Dict:
        """문서에서 메타데이터 추출"""
        metadata = {}

        # 문서 제목 추출 (첫 줄이 짧고 독립적인 경우)
        lines = text.split('\n')
        if lines and len(lines[0].strip()) < 100:
            potential_title = lines[0].strip()
            if potential_title and not potential_title.endswith(('.', '。', '?', '!')):
                metadata['title'] = potential_title

        # 날짜 패턴 추출
        date_patterns = [
            r'\d{4}[-년./]\s*\d{1,2}[-월./]\s*\d{1,2}',  # 2025-01-15, 2025년 1월 15일
            r'\d{4}\.\s*\d{1,2}\.\s*\d{1,2}',  # 2025. 1. 15
            r'\d{4}/\d{1,2}/\d{1,2}',  # 2025/01/15
        ]

        for pattern in date_patterns:
            match = re.search(pattern, text)
            if match:
                metadata['date'] = match.group(0)
                break

        # 부서/팀 추출
        dept_patterns = [
            r'(소속|부서|팀)\s*[:：]?\s*([가-힣]+(?:팀|부|과|센터))',
            r'([가-힣]+(?:팀|부|과|센터))',
        ]

        for pattern in dept_patterns:
            match = re.search(pattern, text)
            if match:
                metadata['department'] = match.group(2) if match.lastindex >= 2 else match.group(1)
                break

        # 작성자 추출
        author_patterns = [
            r'(작성자|기안자|담당자)\s*[:：]?\s*([가-힣]{2,4})\s*(팀원|대리|과장|차장|부장|이사)?',
        ]

        for pattern in author_patterns:
            match = re.search(pattern, text)
            if match:
                name = match.group(2)
                position = match.group(3) if match.lastindex >= 3 else ''
                metadata['author'] = f"{name} {position}".strip()
                break

        # 문서 타입 감지
        doc_type_keywords = {
            '회의록': ['회의록', '미팅', '회의'],
            '요청서': ['요청서', '신청서', '의뢰서'],
            '보고서': ['보고서', '결과 보고', '진행 보고'],
            '계획서': ['계획서', '기획서', '제안서'],
            '승인문서': ['승인', '결재', '기안'],
        }

        for doc_type, keywords in doc_type_keywords.items():
            if any(keyword in text[:200] for keyword in keywords):
                metadata['doc_type'] = doc_type
                break

        return metadata

    def detect_structure(self, text: str) -> List[Dict]:
        """문서 구조 분석 (제목, 표, 리스트, 섹션)"""
        structures = []
        lines = text.split('\n')

        for i, line in enumerate(lines):
            line = line.strip()
            if not line:
                continue

            # 제목 감지 (짧고 번호가 있거나 독립적)
            if len(line) < 100:
                # "1. 제목", "가. 제목", "[제목]" 패턴
                if re.match(r'^[\d가-힣]+[\.\)]\s*[가-힣]', line) or re.match(r'^\[.+\]$', line):
                    structures.append({
                        'type': 'heading',
                        'line': i,
                        'text': line
                    })

            # 표 감지 (탭이나 파이프로 구분)
            if '\t' in line or '|' in line or '│' in line:
                structures.append({
                    'type': 'table',
                    'line': i,
                    'text': line
                })

            # 리스트 감지 (-, *, 번호)
            if re.match(r'^[\s]*[-\*•]\s', line) or re.match(r'^[\s]*\d+[\.\)]\s', line):
                structures.append({
                    'type': 'list',
                    'line': i,
                    'text': line
                })

        return structures

    def split_sentences(self, text: str, language: str = 'ko') -> List[str]:
        """문장 단위로 분리 (spaCy 사용)"""
        if language in self.nlp_models:
            nlp = self.nlp_models[language]
            doc = nlp(text)
            sentences = [sent.text.strip() for sent in doc.sents if sent.text.strip()]
            return sentences
        else:
            # spaCy 없을 때 폴백: 간단한 정규식 분리
            return self._fallback_sentence_split(text)

    def _fallback_sentence_split(self, text: str) -> List[str]:
        """spaCy 없을 때 간단한 문장 분리"""
        # 한국어/영어 문장 종결 기호로 분리
        sentences = re.split(r'([.!?。！？]+[\s\n]+)', text)

        # 문장 + 구분자 합치기
        result = []
        for i in range(0, len(sentences)-1, 2):
            sent = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else '')
            if sent.strip():
                result.append(sent.strip())

        # 마지막 문장
        if len(sentences) % 2 == 1 and sentences[-1].strip():
            result.append(sentences[-1].strip())

        return result

    def merge_chunks_semantically(
        self,
        sentences: List[str],
        structures: List[Dict],
        max_chunk_size: int = None
    ) -> List[str]:
        """의미 단위로 문장들을 청크로 병합"""
        if max_chunk_size is None:
            max_chunk_size = self.chunk_size

        chunks = []
        current_chunk = []
        current_size = 0

        for sentence in sentences:
            sent_size = len(sentence)

            # 청크 크기 초과 시 새 청크 시작
            if current_size + sent_size > max_chunk_size and current_chunk:
                # 현재 청크 저장
                chunks.append(' '.join(current_chunk))

                # 오버랩: 마지막 1~2 문장 유지
                overlap_size = 0
                overlap_sents = []
                for sent in reversed(current_chunk):
                    if overlap_size + len(sent) <= self.chunk_overlap:
                        overlap_sents.insert(0, sent)
                        overlap_size += len(sent)
                    else:
                        break

                current_chunk = overlap_sents
                current_size = overlap_size

            current_chunk.append(sentence)
            current_size += sent_size

        # 마지막 청크
        if current_chunk:
            chunks.append(' '.join(current_chunk))

        return chunks

    def split(self, pages_data: List[Dict]) -> List[Dict]:
        """페이지 데이터를 의미 단위 청크로 분할"""
        all_chunks = []
        chunk_id = 0

        print(f"\n🔄 SemanticTextSplitter 시작")
        print(f"  - 청크 크기: {self.chunk_size}자")
        print(f"  - 오버랩: {self.chunk_overlap}자")

        for page in pages_data:
            page_num = page.get('page_num', 1)
            text = page.get('text', '')

            if not text or not text.strip():
                all_chunks.append({
                    'chunk_id': chunk_id,
                    'page_num': page_num,
                    'text': '',
                    'char_count': 0,
                    'split_method': 'semantic',
                    'warning': 'no_text'
                })
                chunk_id += 1
                continue

            # 1. 언어 감지
            language = self.detect_language(text)

            # 2. 메타데이터 추출
            metadata = self.extract_metadata(text)

            # 3. 문서 구조 분석
            structures = self.detect_structure(text)

            # 4. 문장 단위 분리
            sentences = self.split_sentences(text, language)

            # 5. 의미 단위로 청크 병합
            chunk_texts = self.merge_chunks_semantically(sentences, structures)

            # 6. 청크 생성
            for chunk_text in chunk_texts:
                chunk_data = {
                    'chunk_id': chunk_id,
                    'page_num': page_num,
                    'text': chunk_text,
                    'char_count': len(chunk_text),
                    'split_method': 'semantic',
                    'language': language,
                }

                # 메타데이터 추가
                if metadata:
                    chunk_data['metadata'] = metadata

                # 구조 정보 추가
                if structures:
                    chunk_data['has_structure'] = True
                    chunk_data['structure_types'] = list(set(s['type'] for s in structures))

                all_chunks.append(chunk_data)
                chunk_id += 1

        print(f"  ✓ 총 {len(all_chunks)}개 청크 생성")

        return all_chunks


class HybridSemanticSplitter:
    """하이브리드 분할기: Semantic 우선, LangChain 폴백"""

    def __init__(self, config):
        self.config = config
        self.semantic_splitter = None
        self.langchain_splitter = None

        # Semantic Splitter 시도
        if SPACY_AVAILABLE and LANGDETECT_AVAILABLE:
            try:
                self.semantic_splitter = SemanticTextSplitter(config)
                print("✓ SemanticTextSplitter 활성화 (의미 기반 분할)")
            except Exception as e:
                print(f"⚠️ SemanticTextSplitter 초기화 실패: {e}")

        # LangChain 폴백
        if not self.semantic_splitter:
            try:
                from langchain.text_splitter import RecursiveCharacterTextSplitter
                self.langchain_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=config.chunk_size,
                    chunk_overlap=config.chunk_overlap,
                    separators=["\n\n", "\n", "。", ". ", "! ", "? ", ", ", " ", ""],
                )
                print("✓ LangChain 분할 모드 (폴백)")
            except ImportError:
                print("⚠️ LangChain 미설치, 기본 분할 사용")

    def split(self, pages_data: List[Dict]) -> List[Dict]:
        """분할 실행"""
        if self.semantic_splitter:
            return self.semantic_splitter.split(pages_data)
        elif self.langchain_splitter:
            return self._split_langchain(pages_data)
        else:
            return self._split_basic(pages_data)

    def _split_langchain(self, pages_data: List[Dict]) -> List[Dict]:
        """LangChain 분할"""
        chunks = []
        chunk_id = 0

        for page in pages_data:
            page_num = page['page_num']
            text = str(page['text'])

            if not text.strip():
                chunks.append({
                    'chunk_id': chunk_id,
                    'page_num': page_num,
                    'text': '',
                    'char_count': 0,
                    'split_method': 'langchain',
                    'warning': 'no_text'
                })
                chunk_id += 1
                continue

            split_texts = self.langchain_splitter.split_text(text)

            for split_text in split_texts:
                chunks.append({
                    'chunk_id': chunk_id,
                    'page_num': page_num,
                    'text': split_text,
                    'char_count': len(split_text),
                    'split_method': 'langchain',
                })
                chunk_id += 1

        return chunks

    def _split_basic(self, pages_data: List[Dict]) -> List[Dict]:
        """기본 분할"""
        chunks = []
        chunk_id = 0

        for page in pages_data:
            page_num = page['page_num']
            text = str(page['text'])

            if not text.strip():
                chunks.append({
                    'chunk_id': chunk_id,
                    'page_num': page_num,
                    'text': '',
                    'char_count': 0,
                    'split_method': 'basic',
                    'warning': 'no_text'
                })
                chunk_id += 1
                continue

            # 단순 고정 길이 분할
            start = 0
            while start < len(text):
                end = min(start + self.config.chunk_size, len(text))
                chunk_text = text[start:end]

                chunks.append({
                    'chunk_id': chunk_id,
                    'page_num': page_num,
                    'text': chunk_text,
                    'char_count': len(chunk_text),
                    'split_method': 'basic',
                })
                chunk_id += 1

                if end >= len(text):
                    break

                start = end - self.config.chunk_overlap

        return chunks
