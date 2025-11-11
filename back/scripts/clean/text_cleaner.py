"""
텍스트 정제 모듈 (공백 처리만)
back/scripts/clean/text_cleaner.py
"""

import re


class TextCleaner:
    """기본 텍스트 정제만 수행 (민감정보 필터링 제거)"""

    def __init__(self):
        print("✓ 기본 텍스트 정제 모드 (공백 처리만)")

    def clean(self, text: str) -> str:
        """기본 텍스트 정제: 공백/줄바꿈만 처리"""
        if not text:
            return ""

        # 1. 연속된 공백을 하나로
        text = re.sub(r" +", " ", text)

        # 2. 탭 문자를 공백으로
        text = text.replace("\t", " ")

        # 3. 연속된 줄바꿈을 최대 2개로 제한
        text = re.sub(r"\n{3,}", "\n\n", text)

        # 4. 각 줄의 앞뒤 공백 제거
        lines = [line.strip() for line in text.split("\n")]
        text = "\n".join(line for line in lines if line)

        return text.strip()
