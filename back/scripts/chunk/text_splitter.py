"""
텍스트 청크 분할 모듈 (오버랩 강화 버전)
back/scripts/chunk/text_splitter.py
"""

from typing import List, Dict

try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter

    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False


class HybridTextSplitter:
    """하이브리드 텍스트 분할기"""

    def __init__(self, config):
        self.config = config
        self.use_langchain = config.use_langchain and LANGCHAIN_AVAILABLE

        if self.use_langchain:
            self.splitter = RecursiveCharacterTextSplitter(
                chunk_size=config.chunk_size,
                chunk_overlap=config.chunk_overlap,
                separators=["\n\n", "\n", "。", ". ", "! ", "? ", ", ", " ", ""],
                length_function=len,
                is_separator_regex=False,
            )
            print(f"✓ LangChain 분할 모드 활성화 (오버랩: {config.chunk_overlap}자)")
        else:
            print("✓ 기본 분할 모드")

    def split(self, pages_data: List[Dict]) -> List[Dict]:
        """텍스트 분할"""
        if self.use_langchain:
            return self._split_langchain(pages_data)
        else:
            return self._split_basic(pages_data)

    def _split_langchain(self, pages_data: List[Dict]) -> List[Dict]:
        """LangChain 분할 (오버랩 보장)"""
        chunks = []
        chunk_id = 0

        for page in pages_data:
            page_num = page["page_num"]
            text = str(page["text"])

            if not text or not text.strip():
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "page_num": page_num,
                        "text": "",
                        "char_count": 0,
                        "warning": "no_text",
                        "split_method": "langchain",
                    }
                )
                chunk_id += 1
                continue

            try:
                # LangChain의 split_text는 자동으로 오버랩 적용
                split_texts = self.splitter.split_text(text)

                # 🔍 오버랩 확인 (디버깅용)
                if len(split_texts) > 1:
                    overlap_check = any(
                        split_texts[i][-30:] in split_texts[i + 1][:100]
                        for i in range(len(split_texts) - 1)
                    )
                    if not overlap_check:
                        print(
                            f"      ⚠️ 페이지 {page_num}: 오버랩 미적용 감지, 수동 처리"
                        )
                        split_texts = self._manual_split_with_overlap(text)

            except Exception as e:
                print(f"  ⚠️ LangChain 분할 실패: {e}, 수동 분할 사용")
                split_texts = self._manual_split_with_overlap(text)

            for split_text in split_texts:
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "page_num": page_num,
                        "text": split_text,
                        "char_count": len(split_text),
                        "split_method": "langchain",
                    }
                )
                chunk_id += 1

        return chunks

    def _manual_split_with_overlap(self, text: str) -> List[str]:
        """수동 오버랩 분할 (폴백)"""
        chunks = []
        start = 0
        chunk_size = self.config.chunk_size
        overlap = self.config.chunk_overlap

        while start < len(text):
            end = min(start + chunk_size, len(text))
            chunks.append(text[start:end])

            if end >= len(text):
                break

            # 오버랩 적용
            start = end - overlap

        return chunks

    def _split_basic(self, pages_data: List[Dict]) -> List[Dict]:
        """기본 분할 (오버랩 보장)"""
        chunks = []
        chunk_id = 0

        for page in pages_data:
            page_num = page["page_num"]
            text = str(page["text"])

            if not text or not text.strip():
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "page_num": page_num,
                        "text": "",
                        "char_count": 0,
                        "warning": "no_text",
                        "split_method": "basic",
                    }
                )
                chunk_id += 1
                continue

            if len(text) <= self.config.chunk_size:
                chunks.append(
                    {
                        "chunk_id": chunk_id,
                        "page_num": page_num,
                        "text": text,
                        "char_count": len(text),
                        "split_method": "basic",
                    }
                )
                chunk_id += 1
            else:
                # 오버랩 방식 분할
                start = 0
                while start < len(text):
                    end = min(start + self.config.chunk_size, len(text))
                    chunk_text = text[start:end]

                    chunks.append(
                        {
                            "chunk_id": chunk_id,
                            "page_num": page_num,
                            "text": chunk_text,
                            "char_count": len(chunk_text),
                            "split_method": "basic",
                        }
                    )

                    chunk_id += 1

                    if end >= len(text):
                        break

                    # 🔧 오버랩 적용
                    start = end - self.config.chunk_overlap

        return chunks
