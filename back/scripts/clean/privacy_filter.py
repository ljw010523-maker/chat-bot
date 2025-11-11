"""
개인정보 필터링 모듈 (KLUE + GLiNER 하이브리드)
🔧 마스킹 전용 - 하드코딩 제거
"""

import re
from typing import Dict, List, Tuple, Optional

try:
    from presidio_analyzer import AnalyzerEngine
    from presidio_anonymizer import AnonymizerEngine

    PRESIDIO_AVAILABLE = True
except ImportError:
    PRESIDIO_AVAILABLE = False

try:
    from transformers import pipeline

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False

try:
    from gliner import GLiNER

    GLINER_AVAILABLE = True
except ImportError:
    GLINER_AVAILABLE = False


class PrivacyFilter:
    """마스킹 전용 필터 (하드코딩 없음, T5가 모든 정리 담당)"""

    def __init__(
        self,
        use_ner_model: bool = True,
        ner_model_name: str = None,
        use_gliner: bool = True,
        custom_gliner_labels: List[str] = None,
    ):
        self.use_presidio = PRESIDIO_AVAILABLE
        self.use_ner = use_ner_model and TRANSFORMERS_AVAILABLE
        self.use_gliner = use_gliner and GLINER_AVAILABLE

        self.ner_pipeline = None
        self.gliner_model = None

        print("\n" + "=" * 70)
        print("🔒 KLUE + GLiNER 하이브리드 필터 (마스킹 전용)")
        print("=" * 70)

        # 1. Presidio
        if self.use_presidio:
            print("\n✓ Presidio AI 초기화 중...")
            try:
                self.analyzer = AnalyzerEngine()
                self.anonymizer = AnonymizerEngine()
                print("  ✓ Presidio 로드 완료")
            except Exception as e:
                print(f"  ⚠️ Presidio 로드 실패: {e}")
                self.use_presidio = False

        # 2. KLUE NER
        if self.use_ner:
            print("\n✓ KLUE NER 모델 초기화 중...")
            model_candidates = [
                ner_model_name,
                "soddokayo/klue-roberta-large-klue-ner",
                "vitus9988/klue-roberta-large-ner-identified",
                "Leo97/KoELECTRA-small-v3-modu-ner",
            ]

            ner_loaded = False
            for model_name_try in model_candidates:
                if model_name_try is None:
                    continue

                try:
                    print(f"  → 시도: {model_name_try}")
                    self.ner_pipeline = pipeline(
                        "ner", model=model_name_try, aggregation_strategy="simple"
                    )
                    print(f"  ✓ KLUE 로드 완료: {model_name_try}")

                    if "soddokayo" in model_name_try:
                        print(f"     📊 F1 0.836 | Precision 0.829 | Recall 0.844")

                    ner_loaded = True
                    break
                except Exception:
                    print(f"  ⚠️ 실패, 다음 시도...")
                    continue

            if not ner_loaded:
                print("  ⚠️ KLUE 모델 로드 실패")
                self.use_ner = False

        # 3. GLiNER
        if self.use_gliner:
            print("\n✓ GLiNER 모델 초기화 중...")
            try:
                print(f"  → 시도: taeminlee/gliner_ko")
                self.gliner_model = GLiNER.from_pretrained("taeminlee/gliner_ko")
                print(f"  ✓ GLiNER 로드 완료")

                self.gliner_labels = custom_gliner_labels or [
                    "직급",
                    "직함",
                    "부서",
                    "연봉",
                    "평가등급",
                    "사번",
                    "전화번호",
                    "계좌번호",
                ]

                print(f"     📋 GLiNER 라벨: {', '.join(self.gliner_labels)}")

            except Exception as e:
                print(f"  ⚠️ GLiNER 로드 실패: {e}")
                self.use_gliner = False

        print("\n" + "=" * 70)
        print("📊 활성화된 필터:")
        print("=" * 70)
        print(f"  - Presidio: {'✓' if self.use_presidio else '✗'}")
        print(f"  - KLUE NER: {'✓' if self.use_ner else '✗'}")
        print(f"  - GLiNER: {'✓' if self.use_gliner else '✗'}")
        print(f"  - 마스킹 전용: ✓ (하드코딩 없음)")
        print("=" * 70 + "\n")

    def filter_text(
        self,
        text: str,
        confidence_threshold: float = 0.6,
        gliner_confidence: float = 0.5,
        custom_labels: Optional[List[str]] = None,
        filter_simple_numbers: bool = False,
    ) -> Dict:
        """텍스트에서 개인정보 필터링 (마스킹 방식)"""
        if not text:
            return {
                "filtered_text": "",
                "found_items": [],
                "changes_made": False,
                "detection_methods": [],
            }

        all_detections = []
        methods_used = []

        # 1. Presidio
        if self.use_presidio:
            detections = self._detect_with_presidio(text)
            all_detections.extend(detections)
            if detections:
                methods_used.append("presidio")

        # 2. KLUE
        if self.use_ner:
            detections = self._detect_with_ner(
                text, confidence_threshold, filter_simple_numbers
            )
            all_detections.extend(detections)
            if detections:
                methods_used.append("klue_ner_model")

        # 3. GLiNER
        if self.use_gliner:
            labels = custom_labels or self.gliner_labels
            detections = self._detect_with_gliner(text, labels, gliner_confidence)
            all_detections.extend(detections)
            if detections:
                methods_used.append("gliner_zeroshot")

        merged = self._merge_detections(all_detections)

        # 마스킹 처리 (후처리 없음, T5가 처리)
        filtered_text = self._mask_detections(text, merged)

        found_items = self._format_findings(merged)

        return {
            "filtered_text": filtered_text,
            "found_items": found_items,
            "changes_made": len(merged) > 0,
            "detection_methods": methods_used,
        }

    def _detect_with_presidio(self, text: str) -> List[Tuple]:
        """Presidio로 이메일, 전화번호 검출"""
        detections = []
        try:
            results = self.analyzer.analyze(
                text=text,
                language="en",
                entities=["EMAIL_ADDRESS", "PHONE_NUMBER"],
                return_decision_process=False,
            )
            for result in results:
                entity_text = text[result.start : result.end]
                detections.append(
                    (
                        result.start,
                        result.end,
                        entity_text,
                        result.entity_type,
                        float(result.score),
                    )
                )
        except Exception:
            pass
        return detections

    def _detect_with_ner(
        self, text: str, threshold: float, filter_simple_numbers: bool
    ) -> List[Tuple]:
        """KLUE NER로 이름, 날짜 등 검출"""
        detections = []
        try:
            ner_results = self.ner_pipeline(text)
            for entity in ner_results:
                if entity["score"] >= threshold:
                    entity_type = self._map_ner_label(entity["entity_group"])
                    entity_text = entity["word"].replace("##", "")

                    if entity_type == "QUANTITY" and not filter_simple_numbers:
                        if (
                            entity_text.strip().isdigit()
                            and len(entity_text.strip()) <= 2
                        ):
                            continue

                    detections.append(
                        (
                            entity["start"],
                            entity["end"],
                            entity_text,
                            entity_type,
                            float(entity["score"]),
                        )
                    )
        except Exception:
            pass
        return detections

    def _detect_with_gliner(
        self, text: str, labels: List[str], threshold: float
    ) -> List[Tuple]:
        """GLiNER로 직급 등 검출"""
        detections = []
        try:
            entities = self.gliner_model.predict_entities(
                text, labels, threshold=threshold
            )

            for entity in entities:
                entity_text = entity["text"]
                entity_label = entity["label"]
                entity_score = float(entity["score"])

                # 사번 필터링
                if entity_label == "사번":
                    if entity_text.strip().isdigit() or len(entity_text.strip()) < 3:
                        continue

                # 직급/직함 통합
                if entity_label in ["직급", "직함"]:
                    entity_label = "직급"

                detections.append(
                    (
                        entity["start"],
                        entity["end"],
                        entity_text,
                        entity_label,
                        entity_score,
                    )
                )
        except Exception as e:
            print(f"    ⚠️ GLiNER 검출 중 오류: {e}")

        return detections

    def _map_ner_label(self, label: str) -> str:
        """NER 라벨 매핑"""
        label_map = {
            "PER": "PERSON",
            "PERSON": "PERSON",
            "PS": "PERSON",
            "LOC": "LOCATION",
            "LOCATION": "LOCATION",
            "LC": "LOCATION",
            "ORG": "ORGANIZATION",
            "ORGANIZATION": "ORGANIZATION",
            "OG": "ORGANIZATION",
            "DAT": "DATE",
            "DATE": "DATE",
            "DT": "DATE",
            "TIM": "TIME",
            "TIME": "TIME",
            "TI": "TIME",
            "QT": "QUANTITY",
            "QUANTITY": "QUANTITY",
        }
        return label_map.get(label.upper(), label)

    def _merge_detections(self, detections: List[Tuple]) -> List[Tuple]:
        """중복 검출 병합"""
        if not detections:
            return []

        sorted_detections = sorted(detections, key=lambda x: (x[0], -x[1]))
        merged = []

        for detection in sorted_detections:
            start, end, text, entity_type, score = detection
            overlap = False

            for i, (m_start, m_end, m_text, m_type, m_score) in enumerate(merged):
                if start >= m_start and end <= m_end:
                    overlap = True
                    if score > m_score:
                        merged[i] = detection
                    break
                elif start < m_end and end > m_start:
                    overlap = True
                    if (end - start) > (m_end - m_start):
                        merged[i] = detection
                    break

            if not overlap:
                merged.append(detection)

        return merged

    def _mask_detections(self, text: str, detections: List[Tuple]) -> str:
        """검출된 개인정보를 마스크로 대체 (후처리 없음)"""
        sorted_detections = sorted(detections, key=lambda x: x[0], reverse=True)
        for start, end, _, entity_type, _ in sorted_detections:
            mask = f"[{entity_type}]"
            text = text[:start] + mask + text[end:]
        return text

    def _format_findings(self, detections: List[Tuple]) -> List[Dict]:
        """검출 결과 포맷팅"""
        findings_by_type = {}

        for _, _, text, entity_type, score in detections:
            if entity_type not in findings_by_type:
                findings_by_type[entity_type] = {"items": [], "scores": []}
            findings_by_type[entity_type]["items"].append(text)
            findings_by_type[entity_type]["scores"].append(score)

        result = []
        for entity_type, data in findings_by_type.items():
            avg_score = sum(data["scores"]) / len(data["scores"])
            result.append(
                {
                    "type": entity_type,
                    "count": len(data["items"]),
                    "examples": data["items"][:5],
                    "avg_confidence": round(avg_score, 3),
                    "method": "hybrid",
                }
            )
        return result
