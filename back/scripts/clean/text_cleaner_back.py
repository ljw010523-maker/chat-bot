"""텍스트 정제 모듈"""

import re
from .privacy_filter import PrivacyFilter


class TextCleaner:
    def __init__(
        self,
        use_privacy_filter: bool = True,
        use_ner_model: bool = True,
        ner_model_name: str = None,
        confidence_threshold: float = 0.6,
    ):
        self.use_privacy_filter = use_privacy_filter
        self.confidence_threshold = confidence_threshold

        if self.use_privacy_filter:
            self.privacy_filter = PrivacyFilter(
                use_ner_model=use_ner_model, ner_model_name=ner_model_name
            )
            print("✓ 민감정보 필터링 활성화")

    def clean(self, text: str) -> str:
        if not text:
            return ""
        text = re.sub(r" +", " ", text)
        text = text.replace("\t", " ")
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(line for line in lines if line)
        return text.strip()

    def clean_with_privacy(self, text: str) -> dict:
        cleaned = self.clean(text)

        if self.use_privacy_filter:
            result = self.privacy_filter.filter_text(
                cleaned, confidence_threshold=self.confidence_threshold
            )
            return {
                "text": result["filtered_text"],
                "privacy_report": result["found_items"],
                "privacy_filtered": result["changes_made"],
                "detection_methods": result["detection_methods"],
            }
        else:
            return {
                "text": cleaned,
                "privacy_report": [],
                "privacy_filtered": False,
                "detection_methods": [],
            }
