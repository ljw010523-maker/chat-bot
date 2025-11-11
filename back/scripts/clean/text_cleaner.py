"""
텍스트 정제 모듈
back/scripts/clean/text_cleaner.py
"""

import re


class TextCleaner:
    """텍스트 정제 클래스 (기본 정제 + OCR 후처리)"""

    def __init__(self):
        print("✓ 텍스트 정제 모드 (기본 정제 + OCR 후처리)")

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

    def clean_ocr_text(self, text: str) -> str:
        """OCR 텍스트 후처리 (동적 노이즈 감지 및 제거)"""
        if not text:
            return ""

        lines = text.split("\n")
        cleaned_lines = []

        for line in lines:
            line = line.strip()

            # 1. 빈 라인 제거
            if not line:
                continue

            # 2. 너무 짧은 라인 (2자 미만)
            if len(line) < 2:
                continue

            # 3. 특수문자만으로 구성된 라인
            if re.match(r"^[^\w가-힣]+$", line):
                continue

            # 4. 의미있는 문자 비율 체크
            total_chars = len(line)
            meaningful_chars = sum(1 for c in line if c.isalnum() or "가" <= c <= "힣")

            # 의미있는 문자가 30% 미만이면 노이즈
            if total_chars > 0 and meaningful_chars / total_chars < 0.3:
                continue

            # 5. 짧은 라인의 추가 검증 (10자 미만)
            if len(line) < 10:
                # 한글 또는 영문이 최소 3자 이상 있어야 함
                korean_count = sum(1 for c in line if "가" <= c <= "힣")
                english_count = sum(1 for c in line if "a" <= c.lower() <= "z")

                if korean_count + english_count < 3:
                    continue

                # 숫자와 특수문자만 있는 경우 (예: "| 00 |")
                digit_special = sum(1 for c in line if c.isdigit() or not c.isalnum())
                if digit_special > len(line) * 0.7:
                    continue

            # 6. 반복되는 특수문자 패턴 제거
            if re.search(r"(.)\1{2,}", line) and not line[0].isalnum():
                continue

            # 7. 자음/모음만 있는 한글 제거
            jaeum_moeum = "ㄱㄴㄷㄹㅁㅂㅅㅇㅈㅊㅋㅌㅍㅎㅏㅑㅓㅕㅗㅛㅜㅠㅡㅣㅐㅔ"
            jaeum_moeum_count = sum(1 for c in line if c in jaeum_moeum)

            # 자음/모음이 전체의 20% 이상이면 노이즈
            if jaeum_moeum_count > len(line) * 0.2:
                continue

            # 8. 이상한 영문 패턴 제거
            english_only = "".join(c for c in line if "a" <= c.lower() <= "z")
            if english_only and len(english_only) >= 4:
                vowels = sum(1 for c in english_only.lower() if c in "aeiou")

                if len(english_only) > 0:
                    vowel_ratio = vowels / len(english_only)
                    if vowel_ratio < 0.15 or vowel_ratio > 0.85:
                        if len(english_only) < 8:
                            continue

            # 9. 연속된 공백 정리
            line = re.sub(r"\s+", " ", line)

            # 10. 표 구분선 통일
            if re.match(r"^[\-=_]{3,}$", line):
                line = "─" * 40

            cleaned_lines.append(line)

        return "\n".join(cleaned_lines)
