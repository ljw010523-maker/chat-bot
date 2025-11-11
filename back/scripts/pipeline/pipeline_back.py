"""
개선된 통합 문서 처리 파이프라인
Privacy Filter → T5 Normalizer 분리 실행
"""

import sys
from pathlib import Path

project_root = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(project_root))

from back.scripts.utils.config import Config
from back.scripts.ingest.document_loader import UniversalDocumentLoader
from back.scripts.clean.text_cleaner import TextCleaner
from back.scripts.chunk.text_splitter import HybridTextSplitter
import json
from datetime import datetime


class EnhancedUniversalPipeline:
    """Privacy → T5 순차 처리 파이프라인"""

    def __init__(
        self,
        config: Config,
        use_ner_model: bool = True,
        ner_model_name: str = None,
        confidence_threshold: float = 0.6,
    ):
        self.config = config
        self.doc_loader = UniversalDocumentLoader(config)

        if ner_model_name is None:
            ner_model_name = "soddokayo/klue-roberta-large-klue-ner"
            print(f"\n🎯 KLUE 최고 성능 모델 자동 선택: {ner_model_name}")
            print(
                f"   F1: 0.836 | Precision: 0.829 | Recall: 0.844 | Accuracy: 96.6%\n"
            )

        # Privacy Filter 직접 초기화
        if config.use_privacy_filter:
            from back.scripts.clean.privacy_filter import PrivacyFilter

            self.privacy_filter = PrivacyFilter(
                use_ner_model=use_ner_model,
                ner_model_name=ner_model_name,
                use_gliner=True,
            )
            self.confidence_threshold = confidence_threshold
        else:
            self.privacy_filter = None

        # Text Cleaner (기본 정제만)
        self.text_cleaner = TextCleaner(
            use_privacy_filter=False,  # Privacy는 직접 처리
            use_ner_model=False,
            ner_model_name=None,
            confidence_threshold=confidence_threshold,
        )

        self.text_splitter = HybridTextSplitter(config)

        self.output_folder = Path(config.output_folder)
        self.output_folder.mkdir(parents=True, exist_ok=True)

    def process_document(self, doc_path: Path, save_privacy_report: bool = True):
        """문서 파일 처리"""
        print(f"\n{'='*60}")
        print(f"📄 처리 중: {doc_path.name}")
        print(f"{'='*60}")

        # 1. 문서 로드
        print("\n[1단계] 문서 로드")
        try:
            pages_data = self.doc_loader.load(doc_path)
        except Exception as e:
            print(f"  ❌ 문서 로드 실패: {e}")
            return None

        if not pages_data:
            print("  ❌ 텍스트 추출 실패!")
            return None

        # 2. 기본 정제만 수행 (공백 처리 X)
        print("\n[2단계] 기본 텍스트 정제 (특수문자만)")
        for page in pages_data:
            page["text"] = self.text_cleaner.clean(page["text"])

        # 3. 청크 분할
        print("\n[3단계] 청크 분할")
        chunks = self.text_splitter.split(pages_data)
        print(f"  ✓ 총 {len(chunks)}개 청크 생성")

        # 4. 🔧 Privacy Filter 직접 적용 (공백 처리 X)
        print("\n[4단계] Privacy Filter (개인정보만 제거)")
        privacy_reports = []
        detection_methods_used = set()
        total_privacy_findings = 0

        if self.privacy_filter:
            for i, chunk in enumerate(chunks, 1):
                if not chunk.get("text"):
                    continue

                # Privacy Filter 직접 호출
                result = self.privacy_filter.filter_text(
                    chunk["text"],
                    confidence_threshold=self.confidence_threshold,
                    gliner_confidence=0.5,
                )

                # 필터링된 텍스트로 교체
                chunk["text"] = result["filtered_text"]
                chunk["char_count"] = len(result["filtered_text"])

                # 통계 수집
                if result["changes_made"]:
                    chunk["privacy_filtered"] = True
                    chunk["privacy_items"] = len(result["found_items"])

                    total_privacy_findings += chunk["privacy_items"]
                    detection_methods_used.update(result["detection_methods"])

                    # 페이지별 리포트 수집
                    page_num = chunk["page_num"]
                    existing_report = next(
                        (r for r in privacy_reports if r["page"] == page_num), None
                    )

                    if existing_report:
                        existing_report["findings"].extend(result["found_items"])
                    else:
                        privacy_reports.append(
                            {
                                "page": page_num,
                                "findings": result["found_items"],
                                "methods": result["detection_methods"],
                            }
                        )

            print(f"  ✅ 필터링 완료:")
            print(f"     총 제거: {total_privacy_findings}건")
            print(f"     사용 모델: {', '.join(detection_methods_used)}")

            filtered_chunks = [c for c in chunks if c.get("privacy_filtered")]
            print(f"     필터링된 청크: {len(filtered_chunks)}/{len(chunks)}개")
        else:
            print(f"  ⊘ Privacy Filter 비활성화")

        # 5. 🆕 T5 텍스트 정규화 (공백/맞춤법/문법)
        print("\n[5단계] T5 텍스트 정규화")
        if self.config.use_hanspell_normalization:
            try:
                from back.scripts.normalize.ai_normalizer import normalize_with_t5

                chunks = normalize_with_t5(chunks)
            except ImportError:
                print(f"  ⚠️ Transformers 라이브러리 미설치")
                print(f"     설치: pip install transformers torch")
                print(f"     정규화 없이 계속 진행합니다.")
            except Exception as e:
                print(f"  ⚠️ T5 정규화 실패: {e}")
                print(f"     정규화 없이 계속 진행합니다.")
        else:
            print(f"  ⊘ T5 정규화 비활성화됨")

        # 6. 통계 계산
        total_chars = sum(chunk.get("char_count", 0) for chunk in chunks)
        non_empty = sum(1 for c in chunks if c.get("text"))
        avg_size = total_chars / non_empty if non_empty > 0 else 0

        print(f"\n[6단계] 최종 결과")
        print(f"  ✓ 텍스트 있는 청크: {non_empty}개")
        print(f"  ✓ 총 추출 문자: {total_chars:,} 자")
        print(f"  ✓ 평균 청크 크기: {avg_size:.0f} 자")

        # 7. 결과 저장
        output_data = {
            "source_file": doc_path.name,
            "file_type": doc_path.suffix,
            "processed_at": datetime.now().isoformat(),
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
                "privacy_filtering": {
                    "enabled": self.config.use_privacy_filter,
                    "model": "soddokayo/klue-roberta-large-klue-ner",
                    "model_performance": {
                        "f1": 0.836,
                        "precision": 0.829,
                        "recall": 0.844,
                        "accuracy": 0.966,
                    },
                    "detection_methods": list(detection_methods_used),
                    "total_findings": total_privacy_findings,
                    "chunks_affected": len(
                        [c for c in chunks if c.get("privacy_filtered")]
                    ),
                },
                "t5_normalization": {
                    "enabled": self.config.use_hanspell_normalization,
                    "model": "j5ng/et5-typos-corrector",
                    "chunks_normalized": len(
                        [c for c in chunks if c.get("normalized")]
                    ),
                },
            },
        }

        if save_privacy_report and privacy_reports:
            output_data["privacy_report"] = privacy_reports

        output_path = self.output_folder / f"{doc_path.stem}_chunks.json"
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        print(f"\n  ✓ 저장 완료: {output_path}")

        if save_privacy_report and privacy_reports:
            report_path = self.output_folder / f"{doc_path.stem}_privacy_report.json"
            with open(report_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "source_file": doc_path.name,
                        "processed_at": datetime.now().isoformat(),
                        "model_info": {
                            "name": "soddokayo/klue-roberta-large-klue-ner",
                            "f1_score": 0.836,
                            "precision": 0.829,
                            "recall": 0.844,
                            "accuracy": 0.966,
                        },
                        "detection_methods": list(detection_methods_used),
                        "total_findings": total_privacy_findings,
                        "reports": privacy_reports,
                    },
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            print(f"  ✓ 프라이버시 리포트: {report_path}")

        return output_data

    def process_all(self, save_privacy_reports: bool = True):
        """폴더 내 모든 문서 처리"""
        raw_folder = Path(self.config.raw_folder)

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
        print(f"🚀 Privacy → T5 순차 처리 파이프라인")
        print(f"{'='*60}")
        print(f"📁 대상 폴더: {raw_folder.absolute()}")
        print(f"📊 발견된 파일: {len(all_files)}개")
        print(f"{'='*60}")

        results = []
        success_count = 0
        total_privacy_findings = 0

        for idx, doc_file in enumerate(all_files, 1):
            print(f"\n[{idx}/{len(all_files)}]")
            try:
                result = self.process_document(doc_file, save_privacy_reports)
                if result:
                    results.append(result)
                    success_count += 1

                    if self.config.use_privacy_filter:
                        total_privacy_findings += result["processing_info"][
                            "privacy_filtering"
                        ]["total_findings"]
            except Exception as e:
                print(f"\n❌ 오류 발생: {e}")
                import traceback

                traceback.print_exc()

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

            if self.config.use_privacy_filter:
                print(f"  🎯 Privacy 제거: {total_privacy_findings}건")

            if self.config.use_hanspell_normalization:
                total_normalized = sum(
                    r["processing_info"]["t5_normalization"]["chunks_normalized"]
                    for r in results
                )
                print(f"  🤖 T5 정규화: {total_normalized}개 청크")

        print(f"  저장 위치: {self.output_folder.absolute()}")
        print(f"{'='*60}\n")

        return results


def main():
    """메인 실행"""
    config = Config()

    print("\n" + "=" * 60)
    print("🎯 Privacy Filter → T5 Normalizer 파이프라인")
    print("=" * 60)
    print("1단계: Privacy Filter (개인정보만 제거)")
    print("   - KLUE: soddokayo/klue-roberta-large-klue-ner")
    print("   - GLiNER: taeminlee/gliner_ko")
    print("2단계: T5 Normalizer (공백/맞춤법/문법)")
    print("   - T5: j5ng/et5-typos-corrector")
    print("=" * 60 + "\n")

    pipeline = EnhancedUniversalPipeline(
        config=config,
        use_ner_model=True,
        ner_model_name=None,
        confidence_threshold=0.6,
    )

    pipeline.process_all(save_privacy_reports=True)


if __name__ == "__main__":
    main()
