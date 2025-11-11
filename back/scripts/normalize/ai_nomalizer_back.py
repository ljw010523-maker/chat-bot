"""
T5 기반 한국어 맞춤법 교정 모듈 (프롬프트 개선 버전)
마스킹 보호 강화
back/scripts/normalize/ai_normalizer.py
"""

from typing import Dict, List
import time
import re

try:
    from transformers import T5TokenizerFast, T5ForConditionalGeneration
    import torch

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False


class T5Normalizer:
    """T5 기반 텍스트 정규화 (마스킹 보호)"""

    def __init__(self, model_name: str = "j5ng/et5-typos-corrector"):
        if not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "Transformers 라이브러리 필요:\n" "  pip install transformers torch\n"
            )

        print("\n" + "=" * 70)
        print("🤖 T5 기반 한국어 텍스트 정규화 (프롬프트 개선)")
        print("=" * 70)
        print(f"✓ 모델: {model_name}")
        print("  - Transformer 기반 (Google T5)")
        print("  - 맞춤법 교정")
        print("  - 띄어쓰기 교정")
        print("  - 문법 교정")
        print("  - 🎯 마스크 보호 (프롬프트 개선)")
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

    def normalize_chunk(self, chunk: Dict) -> Dict:
        """청크 정규화 (마스킹 유지)"""
        if not chunk.get("text"):
            return chunk

        original_text = chunk["text"]

        try:
            # T5로 텍스트 정규화 (프롬프트 개선으로 마스크 보호)
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
        """T5 모델로 텍스트 교정 (프롬프트 개선)"""
        if not text or not text.strip():
            return text

        try:
            # 512 토큰 제한 처리
            if len(text) > 400:
                return self._split_and_correct(text)

            # 🆕 프롬프트 개선: 특수 토큰 보호 명시
            input_text = (
                f"다음 텍스트의 맞춤법과 띄어쓰기만 교정하세요. "
                f"대괄호 [ ] 안의 단어는 절대 변경하지 말고 그대로 유지하세요: {text}"
            )

            inputs = self.tokenizer(
                input_text,
                return_tensors="pt",
                max_length=512,
                truncation=True,
                padding=True,
            ).to(self.device)

            # 🆕 생성 파라미터 개선
            with torch.no_grad():
                outputs = self.model.generate(
                    **inputs,
                    max_length=512,
                    num_beams=5,  # 🆕 3 → 5 (더 정확)
                    early_stopping=True,
                    no_repeat_ngram_size=3,  # 🆕 2 → 3 (반복 방지 강화)
                    temperature=0.3,  # 🆕 보수적 생성
                    do_sample=False,  # 🆕 확정적 생성
                )

            # 디코딩
            corrected = self.tokenizer.decode(outputs[0], skip_special_tokens=True)

            return corrected.strip()

        except Exception as e:
            print(f"    T5 교정 오류: {e}")
            return text

    def _split_and_correct(self, text: str) -> str:
        """긴 텍스트를 분할하여 교정"""
        # 문장 단위로 분할
        sentences = re.split(r"([.!?]\s+|\n\n)", text)

        corrected_parts = []
        current_batch = ""

        for i, segment in enumerate(sentences):
            # 구분자는 그대로 유지
            if i % 2 == 1:  # 구분자
                corrected_parts.append(segment)
                continue

            segment = segment.strip()
            if not segment:
                continue

            # 배치가 너무 길어지면 처리
            if len(current_batch) + len(segment) > 300:
                if current_batch:
                    corrected = self._normalize_with_t5(current_batch)
                    corrected_parts.append(corrected)
                current_batch = segment
            else:
                current_batch += " " + segment if current_batch else segment

        # 마지막 배치 처리
        if current_batch:
            corrected = self._normalize_with_t5(current_batch)
            corrected_parts.append(corrected)

        return "".join(corrected_parts)

    def normalize_all_chunks(self, chunks: List[Dict]) -> List[Dict]:
        """모든 청크 정규화"""
        print(f"\n[T5 텍스트 정규화] 총 {len(chunks)}개 청크")
        print(f"  🎯 프롬프트 개선 (마스크 보호 강화)")

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

                    # 변화량 표시
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
        정규화된 청크들 (마스크 보호)
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
