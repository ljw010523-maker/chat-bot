"""
T5 기반 한국어 맞춤법 교정 모듈 (안전 프롬프트 + 마스크 보호 + 토큰 분할)
back/scripts/normalize/ai_normalizer.py
"""

from typing import Dict, List
import time
import re
import contextlib

# transformers 가용성 플래그 이름 분리 (다른 모듈과 충돌 방지)
try:
    from transformers import T5TokenizerFast, T5ForConditionalGeneration
    import torch

    HF_T5_AVAILABLE = True
except ImportError:
    HF_T5_AVAILABLE = False


class T5Normalizer:
    """T5 기반 텍스트 정규화 (마스킹 유지)"""

    # 마스크 보호용 패턴/센티넬
    MASK_PATTERN = re.compile(r"\[(?:[A-Z가-힣_]+)\]")
    SENTINEL_PREFIX = "<KEEP_"
    SENTINEL_SUFFIX = ">"

    def __init__(self, model_name: str = "j5ng/et5-typos-corrector"):
        if not HF_T5_AVAILABLE:
            raise ImportError(
                "Transformers 라이브러리 필요:\n  pip install transformers torch\n"
            )

        print("\n" + "=" * 70)
        print("🤖 T5 기반 한국어 텍스트 정규화 (안전 프롬프트/마스크 보호/토큰 분할)")
        print("=" * 70)
        print(f"✓ 모델: {model_name}")
        print("  - Transformer 기반 (Google T5)")
        print("  - 맞춤법/띄어쓰기/간단 문법 교정")
        print("  - 🎯 마스크 유지 (센티넬 보호)")
        print("=" * 70)

        print("\n  🔄 모델 로딩 중... (최초 1회만 다운로드)")
        try:
            self.device = "cuda" if torch.cuda.is_available() else "cpu"
            print(f"  📍 Device: {self.device.upper()}")

            self.tokenizer = T5TokenizerFast.from_pretrained(model_name)
            self.model = T5ForConditionalGeneration.from_pretrained(model_name).to(
                self.device
            )
            self.model.eval()

            print(f"  ✅ 모델 로드 완료!\n")
            print("=" * 70 + "\n")
        except Exception as e:
            print(f"  ❌ 모델 로드 실패: {e}")
            raise

    # ---------- 마스크 보호/복원 ----------
    def _protect_masks(self, text: str):
        mapping = {}
        idx = 0

        def repl(m):
            nonlocal idx
            tok = f"{self.SENTINEL_PREFIX}{idx}{self.SENTINEL_SUFFIX}"
            mapping[tok] = m.group(0)
            idx += 1
            return tok

        return self.MASK_PATTERN.sub(repl, text), mapping

    def _restore_masks(self, text: str, mapping: Dict[str, str]):
        for k, v in mapping.items():
            text = text.replace(k, v)
        return text

    # ---------- 토큰 길이/분할 ----------
    def _token_len(self, text: str) -> int:
        # special tokens 포함하여 실제 생성 한도 체크
        return len(self.tokenizer.encode(text, add_special_tokens=True))

    def _split_and_correct_by_tokens(
        self, text: str, max_tokens: int = 448, overlap: int = 64
    ) -> str:
        # special tokens 제외로 고정 길이 분할
        ids = self.tokenizer.encode(text, add_special_tokens=False)
        out, start = [], 0
        while start < len(ids):
            end = min(len(ids), start + max_tokens)
            chunk_ids = ids[start:end]
            chunk_text = self.tokenizer.decode(chunk_ids)
            out.append(self._normalize_with_t5(chunk_text))  # 재귀
            if end == len(ids):
                break
            start = max(0, end - overlap)
        return "".join(out)

    # ---------- 퍼블릭 API ----------
    def normalize_chunk(self, chunk: Dict) -> Dict:
        """청크 정규화 (마스킹 유지)"""
        if not chunk.get("text"):
            return chunk

        original_text = chunk["text"]

        try:
            normalized_text = self._normalize_with_t5(original_text)

            chunk["text"] = normalized_text
            chunk["char_count"] = len(normalized_text)
            chunk["normalized"] = True
            chunk["original_length"] = len(original_text)

        except Exception as e:
            print(f"  ⚠️ 정규화 실패: {e}")
            chunk["normalized"] = False
            chunk["normalization_error"] = str(e)

        return chunk

    def _normalize_with_t5(self, text: str) -> str:
        """T5 모델로 텍스트 교정 (안전 프롬프트 + 마스크 보호 + 토큰 분할)"""
        if not text or not text.strip():
            return text

        try:
            # 1) 토큰 길이 기준: 모델 한도(512)에 여유를 두고 분할
            if self._token_len(text) > 448:
                return self._split_and_correct_by_tokens(
                    text, max_tokens=448, overlap=64
                )

            # 2) 마스크 보호(센티넬로 치환)
            protected, mapping = self._protect_masks(text)

            # 3) 안전 프롬프트(의미/숫자/기호/마스크 비변형)
            input_text = (
                "다음 문장의 철자와 띄어쓰기만 교정하고, 의미/숫자/기호/마스크는 바꾸지 마세요:\n"
                + protected
            )

            inputs = self.tokenizer(
                input_text,
                return_tensors="pt",
                max_length=512,
                truncation=True,
                padding=True,
            ).to(self.device)

            # 4) 추론 (안정 우선: num_beams=1, fp16 자동 캐스트)
            with torch.inference_mode():
                autocast_ctx = (
                    torch.cuda.amp.autocast
                    if self.device == "cuda"
                    else contextlib.nullcontext
                )
                with autocast_ctx():
                    outputs = self.model.generate(
                        **inputs,
                        max_length=512,
                        num_beams=1,  # 필요 시 3으로 조정
                        early_stopping=True,
                        no_repeat_ngram_size=2,
                    )

            corrected = self.tokenizer.decode(
                outputs[0], skip_special_tokens=True
            ).strip()

            # 5) 마스크 복원
            return self._restore_masks(corrected, mapping)

        except Exception as e:
            print(f"    T5 교정 오류: {e}")
            return text

    # 기존 문장 단위 분할은 보조로 유지(토큰 분할 우선 적용)
    def _split_and_correct(self, text: str) -> str:
        """긴 텍스트를 문장 단위로 분할하여 교정 (보조 경로)"""
        sentences = re.split(r"([.!?]\s+|\n\n)", text)
        corrected_parts = []
        current_batch = ""

        for i, segment in enumerate(sentences):
            if i % 2 == 1:  # 구분자
                corrected_parts.append(segment)
                continue

            segment = segment.strip()
            if not segment:
                continue

            if len(current_batch) + len(segment) > 300:
                if current_batch:
                    corrected = self._normalize_with_t5(current_batch)
                    corrected_parts.append(corrected)
                current_batch = segment
            else:
                current_batch += " " + segment if current_batch else segment

        if current_batch:
            corrected = self._normalize_with_t5(current_batch)
            corrected_parts.append(corrected)

        return "".join(corrected_parts)

    def normalize_all_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """모든 청크 정규화"""
        print(f"\n[T5 텍스트 정규화] 총 {len(chunks)}개 청크")
        print(f"  🎯 안전 프롬프트 (마스크 유지)")

        normalized_chunks = []
        success_count = 0
        error_count = 0
        total_time = 0

        for i, chunk in enumerate(chunks, 1):
            if chunk.get("text"):
                print(f"  청크 {i}/{len(chunks)}...", end=" ")

                start = time.time()
                normalized = self.normalize_chunk(chunk)
                elapsed = time.time() - start

                if normalized.get("normalized"):
                    success_count += 1
                    total_time += elapsed

                    original_len = normalized.get("original_length", 0)
                    new_len = normalized.get("char_count", 0)
                    diff = new_len - original_len
                    diff_str = f"{diff:+d}" if diff != 0 else "±0"

                    print(f"✓ ({elapsed:.2f}초, {diff_str}자)")
                else:
                    error_count += 1
                    print(f"✗")

                normalized_chunks.append(normalized)
            else:
                normalized_chunks.append(chunk)

        print(f"\n  ✅ 정규화 완료:")
        print(f"     성공: {success_count}/{len(chunks)}개")
        if error_count > 0:
            print(f"     실패: {error_count}개")
        if success_count > 0:
            print(f"     총 소요: {total_time:.2f}초")
            print(f"     평균: {total_time/success_count:.2f}초/청크")

        return normalized_chunks


def normalize_with_t5(chunks: List[Dict]) -> List[Dict]:
    """
    파이프라인에 T5 정규화 통합

    Args:
        chunks: 마스킹 완료된 청크들

    Returns:
        정규화된 청크들 (마스크 유지)
    """
    try:
        normalizer = T5Normalizer(model_name="j5ng/et5-typos-corrector")
        return normalizer.normalize_all_chunks(chunks)
    except ImportError:
        print(f"\n⚠️ Transformers 라이브러리가 설치되지 않았습니다.")
        print(f"   설치: pip install transformers torch")
        print(f"   정규화 없이 계속 진행합니다.\n")
        return chunks
    except Exception as e:
        print(f"\n⚠️ T5 정규화 초기화 실패: {e}")
        print(f"   정규화 없이 계속 진행합니다.\n")
        return chunks
