"""
통합 문서 처리 파이프라인
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from back.scripts.utils.config import Config
from back.scripts.ingest.document_loader import UniversalDocumentLoader  # ← 변경
from back.scripts.clean.text_cleaner import TextCleaner
from back.scripts.chunk.text_splitter import HybridTextSplitter
import json


class UniversalPipeline:
    """통합 문서 처리 파이프라인"""

    def __init__(self, config: Config):
        self.config = config
        self.doc_loader = UniversalDocumentLoader(config)  # ← 변경
        self.text_cleaner = TextCleaner(use_privacy_filter=config.use_privacy_filter)
        self.text_splitter = HybridTextSplitter(config)

        self.output_folder = Path(config.output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

    def process_document(self, doc_path: Path):
        """문서 파일 처리 (모든 형식 지원)"""
        print(f"\n{'='*60}")
        print(f"📄 처리 중: {doc_path.name}")
        print(f"{'='*60}")

        # 1. 문서 로드 (자동 형식 감지)
        print("\n[1단계] 문서 로드")
        try:
            pages_data = self.doc_loader.load(doc_path)
        except Exception as e:
            print(f"  ❌ 문서 로드 실패: {e}")
            return None

        if not pages_data:
            print("  ❌ 텍스트 추출 실패!")
            return None

        # 2. 텍스트 정제 + AI 자동 필터링
        print("\n[2단계] 텍스트 정제 및 AI 자동 필터링")
        privacy_reports = []

        for page in pages_data:
            if self.config.use_privacy_filter:
                result = self.text_cleaner.clean_with_privacy(page["text"])
                page["text"] = result["text"]

                if result["privacy_filtered"]:
                    privacy_reports.append(
                        {"page": page["page_num"], "findings": result["privacy_report"]}
                    )
                    print(
                        f"  🔒 페이지 {page['page_num']}: 민감정보 {len(result['privacy_report'])}건 자동 제거"
                    )
            else:
                page["text"] = self.text_cleaner.clean(page["text"])

        if privacy_reports:
            total_findings = sum(
                sum(item["count"] for item in report["findings"])
                for report in privacy_reports
            )
            print(f"  ✅ AI가 자동으로 총 {total_findings}건 제거 완료")

        # 3. 청크 분할
        print("\n[3단계] 청크 분할")
        chunks = self.text_splitter.split(pages_data)

        total_chars = sum(chunk.get("char_count", 0) for chunk in chunks)
        non_empty = sum(1 for c in chunks if c.get("text"))
        avg_size = total_chars / non_empty if non_empty > 0 else 0

        print(f"  ✓ 총 {len(chunks)}개 청크 생성")
        print(f"  ✓ 텍스트 있는 청크: {non_empty}개")
        print(f"  ✓ 총 추출 문자: {total_chars:,} 자")
        print(f"  ✓ 평균 청크 크기: {avg_size:.0f} 자")

        # 4. 결과 저장
        output_data = {
            "source_file": doc_path.name,
            "file_type": doc_path.suffix,
            "total_pages": len(pages_data),
            "total_chunks": len(chunks),
            "total_characters": total_chars,
            "average_chunk_size": round(avg_size, 2),
            "chunks": chunks,
            "processing_info": {
                "chunk_size": self.config.chunk_size,
                "chunk_overlap": self.config.chunk_overlap,
                "split_method": "langchain" if self.config.use_langchain else "basic",
                "methods_used": list(set(p["method"] for p in pages_data)),
                "privacy_filtering": self.config.use_privacy_filter,
                "privacy_method": "ai_auto",
                "privacy_findings": privacy_reports if privacy_reports else None,
            },
        }

        output_path = self.output_folder / f"{doc_path.stem}_chunks.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n  ✓ 저장 완료: {output_path}")
        return output_data

    def process_all(self):
        """폴더 내 모든 문서 처리"""
        raw_folder = Path(self.config.raw_folder)

        # 지원 형식
        patterns = [
            "*.pdf",
            "*.txt",
            "*.docx",
            "*.doc",
            "*.pptx",
            "*.ppt",
            "*.jpg",
            "*.jpeg",
            "*.png",
            "*.xlsx",
            "*.xls",
            "*.csv",
        ]

        all_files = []
        for pattern in patterns:
            all_files.extend(raw_folder.glob(pattern))

        if not all_files:
            print(f"\n❌ 문서 파일이 없습니다: {raw_folder.absolute()}")
            return []

        print(f"\n{'='*60}")
        print(f"🚀 통합 문서 처리 시작")
        print(f"{'='*60}")
        print(f"📁 대상 폴더: {raw_folder.absolute()}")
        print(f"📊 발견된 파일: {len(all_files)}개")
        print(f"{'='*60}")

        results = []
        success_count = 0

        for idx, doc_file in enumerate(all_files, 1):
            print(f"\n[{idx}/{len(all_files)}]")
            try:
                result = self.process_document(doc_file)
                if result:
                    results.append(result)
                    success_count += 1
            except Exception as e:
                print(f"\n❌ 오류 발생: {e}")
                import traceback

                traceback.print_exc()

        # 최종 요약
        print(f"\n{'='*60}")
        print(f"✅ 처리 완료!")
        print(f"{'='*60}")
        print(f"  성공: {success_count}/{len(all_files)}개")
        print(f"  실패: {len(all_files) - success_count}개")

        if results:
            total_chunks = sum(r["total_chunks"] for r in results)
            total_chars = sum(r["total_characters"] for r in results)
            print(f"  총 생성 청크: {total_chunks}개")
            print(f"  총 추출 문자: {total_chars:,}자")

        print(f"  저장 위치: {self.output_folder.absolute()}")
        print(f"{'='*60}\n")

        return results


def main():
    """메인 실행"""
    config = Config()
    pipeline = UniversalPipeline(config)
    pipeline.process_all()


if __name__ == "__main__":
    main()
