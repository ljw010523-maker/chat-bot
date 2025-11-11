"""
HWP 파일 처리 모듈 (Windows 전용)
back/scripts/ingest/hwp_processor.py
"""

from pathlib import Path
from typing import List, Dict, Optional
import platform
import tempfile
import uuid


class HwpProcessor:
    """HWP/HWPX 파일 처리 클래스 (Windows 전용)"""

    def __init__(self, config, text_cleaner):
        """
        Args:
            config: 설정 객체 (upstage_api_key 등)
            text_cleaner: TextCleaner 인스턴스
        """
        self.config = config
        self.text_cleaner = text_cleaner

    # ============================================
    # HWP 텍스트 검증
    # ============================================

    def _is_valid_korean_text(self, text: str) -> bool:
        """한글 텍스트 유효성 검증 (깨진 텍스트 필터링)"""
        if not text or len(text.strip()) < 10:
            return False

        # 한글, 영문, 숫자, 기본 특수문자만 추출
        valid_chars = [
            c
            for c in text
            if (
                "\uac00" <= c <= "\ud7a3"  # 한글 완성형
                or "a" <= c.lower() <= "z"  # 영문
                or c.isdigit()  # 숫자
                or c in " \n\t.,!?-()[]{}:;@#%&*+=/<>\"'"  # 기본 특수문자
            )
        ]

        if not valid_chars:
            return False

        # 유효한 문자 비율 체크
        valid_ratio = len(valid_chars) / len(text)

        # 한글 비율 체크
        korean_chars = sum(1 for c in text if "\uac00" <= c <= "\ud7a3")
        korean_ratio = korean_chars / len(text) if text else 0

        # 영문/숫자 비율
        alnum_chars = sum(1 for c in text if c.isalnum())
        alnum_ratio = alnum_chars / len(text) if text else 0

        # 유효 조건 (하나라도 만족하면 OK)
        conditions = [
            valid_ratio >= 0.5,  # 유효 문자 50% 이상
            korean_ratio >= 0.05,  # 한글 5% 이상
            (korean_chars >= 3),  # 한글 3자 이상
            (alnum_chars >= 10 and valid_ratio >= 0.3),  # 영문/숫자 10자 이상
        ]

        return any(conditions)

    # ============================================
    # HWP → PDF 변환 (win32com)
    # ============================================

    def _disable_hwp_security_via_registry(self):
        """레지스트리를 통해 한글 보안 수준 완전 비활성화"""
        try:
            import winreg

            # 한글 보안 설정 레지스트리 경로들
            reg_paths = [
                (winreg.HKEY_CURRENT_USER, r"Software\HNC\HwpAutomation"),
                (winreg.HKEY_CURRENT_USER, r"Software\HNC\Hwp\8.0\HncOle"),
                (winreg.HKEY_CURRENT_USER, r"Software\Hnc\Hwp\Automation"),
                (winreg.HKEY_CURRENT_USER, r"Software\HNC\Hwp\9.0"),
                (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\HNC\Hwp\9.0"),
            ]

            for hkey, reg_path in reg_paths:
                try:
                    key = winreg.CreateKey(hkey, reg_path)
                    # 모든 보안 관련 설정 비활성화
                    winreg.SetValueEx(key, "Security", 0, winreg.REG_DWORD, 0)
                    winreg.SetValueEx(key, "SecurityLevel", 0, winreg.REG_DWORD, 0)
                    winreg.SetValueEx(key, "TrustVBAProject", 0, winreg.REG_DWORD, 1)
                    winreg.SetValueEx(key, "DisableSecurityWarning", 0, winreg.REG_DWORD, 1)
                    winreg.CloseKey(key)
                except:
                    pass

        except Exception:
            pass

    def _auto_click_hwp_security_popup(self, timeout=10):
        """한글 보안 팝업 자동 클릭 (백그라운드 쓰레드 - 버튼 직접 클릭)"""
        import time
        import threading

        def click_popup():
            try:
                import win32gui
                import win32con

                start_time = time.time()
                clicked_count = 0

                while time.time() - start_time < timeout:
                    # 한글 보안 경고 창 찾기 (여러 제목 시도)
                    window_titles = ["호환", "보안 경고", "한글", "HWP", "알림", "경고"]
                    hwnd = 0

                    for title in window_titles:
                        hwnd = win32gui.FindWindow(None, title)
                        if hwnd != 0:
                            break

                    if hwnd != 0:
                        # 창 활성화 (포커스 주기) - 키보드 입력을 받을 수 있도록
                        try:
                            # 창을 전면으로 가져오기
                            win32gui.SetForegroundWindow(hwnd)
                            # 창 표시하기
                            win32gui.ShowWindow(hwnd, win32con.SW_SHOW)
                            # 짧은 대기 (창이 활성화될 시간)
                            time.sleep(0.1)
                        except:
                            pass

                        # 방법 1: 자식 버튼 찾아서 직접 클릭
                        button_clicked = False

                        def find_and_click_button(hwnd_child, _):
                            nonlocal button_clicked
                            try:
                                class_name = win32gui.GetClassName(hwnd_child)
                                text = win32gui.GetWindowText(hwnd_child)

                                # 버튼 클래스이고 "모두 허용" 또는 관련 텍스트
                                if "button" in class_name.lower():
                                    # "모두 허용(A)", "허용 완료(N)", "허용" 등
                                    if any(keyword in text for keyword in ["모두", "허용", "완료"]):
                                        # WM_LBUTTONDOWN + WM_LBUTTONUP으로 클릭 시뮬레이션
                                        win32gui.SendMessage(hwnd_child, win32con.WM_LBUTTONDOWN, 0, 0)
                                        win32gui.SendMessage(hwnd_child, win32con.WM_LBUTTONUP, 0, 0)
                                        # BM_CLICK도 시도
                                        win32gui.SendMessage(hwnd_child, win32con.BM_CLICK, 0, 0)
                                        print(f"    ✓ 버튼 클릭: '{text}'")
                                        button_clicked = True
                                        return False
                            except:
                                pass
                            return True

                        try:
                            win32gui.EnumChildWindows(hwnd, find_and_click_button, None)
                        except:
                            pass

                        if button_clicked:
                            clicked_count += 1
                            print(f"    ✓ 보안 팝업 자동 승인 완료 ({clicked_count}번째)")
                            time.sleep(0.3)
                            # 여러 번 나올 수 있으므로 계속 감시
                            if clicked_count >= 5:  # 최대 5번까지만
                                break
                        else:
                            # 방법 2: 키보드 입력 (Alt+A)
                            import win32api
                            win32api.keybd_event(win32con.VK_MENU, 0, 0, 0)  # Alt 누름
                            time.sleep(0.05)
                            win32api.keybd_event(0x41, 0, 0, 0)  # A 누름
                            time.sleep(0.05)
                            win32api.keybd_event(0x41, 0, win32con.KEYEVENTF_KEYUP, 0)  # A 뗌
                            win32api.keybd_event(win32con.VK_MENU, 0, win32con.KEYEVENTF_KEYUP, 0)  # Alt 뗌
                            print(f"    ✓ Alt+A 키 전송")
                            time.sleep(0.3)

                    time.sleep(0.1)  # 100ms마다 확인
            except Exception:
                pass

        # 백그라운드 쓰레드 시작
        thread = threading.Thread(target=click_popup, daemon=True)
        thread.start()
        return thread

    def _convert_hwp_to_pdf(self, hwp_path: Path) -> Optional[Path]:
        """HWP를 PDF로 변환 (한글 프로그램 자동화)"""
        print(f"  🔄 HWP → PDF 변환 중...")

        # 임시 PDF 파일 경로 (한글 경로 문제 방지를 위해 UUID 사용)
        temp_dir = Path(tempfile.gettempdir())
        pdf_path = temp_dir / f"hwp_temp_{uuid.uuid4().hex}.pdf"

        # 기존 파일 삭제
        if pdf_path.exists():
            pdf_path.unlink()

        # 레지스트리를 통한 보안 설정 비활성화 (사전 방지)
        self._disable_hwp_security_via_registry()

        # 보안 팝업 자동 클릭 쓰레드 시작 (2차 방어)
        self._auto_click_hwp_security_popup(timeout=15)

        try:
            # win32com 가용성 체크
            try:
                import win32com.client
                import pythoncom
            except ImportError:
                print(f"  ⚠️ pywin32 미설치")
                return None

            if platform.system() != "Windows":
                print(f"  ⚠️ Windows 환경이 아님")
                return None

            pythoncom.CoInitialize()

            # 한글 프로그램 실행 (백그라운드)
            hwp = win32com.client.Dispatch("HWPFrame.HwpObject")

            # 프로그램 창 완전히 숨기기 (모든 UI 비활성화)
            try:
                hwp.XFrameWindow.Visible = False  # 메인 창 숨김
                hwp.XFrameWindow.Active = 0       # 창 비활성화
            except:
                pass

            # 화면 업데이트 중지 (성능 향상 + 팝업 방지)
            try:
                hwp.SetPrivateInfoPath("", "")    # 개인정보 경로 무시
            except:
                pass

            # 보안 경고 완전 무시 (모든 메시지 박스 자동 처리)
            try:
                # 0x01000000 = 모든 메시지 박스 무시
                # 0x00020000 = 메시지 박스 자동 승인
                # 0x00010000 = 경고 메시지 무시
                hwp.SetMessageBoxMode(0x01000000 | 0x00020000 | 0x00010000)
            except:
                pass

            # 보안 모듈 무시 (파일 경로 검사 우회)
            try:
                hwp.RegisterModule("FilePathCheckDLL", "FilePathCheckerModuleExample")
            except:
                pass

            # 파일 열기 (모든 보안 확인 무시)
            open_params = "openreadonly:true;versionwarning:false;suspendpassword:true;lock:false;noconfirm:true"
            hwp.Open(str(hwp_path.absolute()), "HWP", open_params)

            # PDF로 저장
            hwp.HAction.GetDefault("FileSaveAsPdf", hwp.HParameterSet.HFileOpenSave.HSet)
            hwp.HParameterSet.HFileOpenSave.filename = str(pdf_path.absolute())
            hwp.HParameterSet.HFileOpenSave.Format = "PDF"
            hwp.HAction.Execute("FileSaveAsPdf", hwp.HParameterSet.HFileOpenSave.HSet)

            # 종료
            hwp.Quit()
            pythoncom.CoUninitialize()

            if pdf_path.exists():
                print(f"  ✅ PDF 변환 성공: {pdf_path}")
                return pdf_path
            else:
                print(f"  ❌ PDF 파일 생성 실패")
                return None

        except Exception as e:
            print(f"  ❌ HWP → PDF 변환 실패: {e}")
            return None

    # ============================================
    # HWP 처리 (olefile 우선, VLM OCR 폴백)
    # ============================================

    def load_hwp(self, file_path: Path, vlm_parser_func=None) -> List[Dict]:
        """
        HWP 파일 읽기 - olefile 우선, VLM OCR 폴백

        Args:
            file_path: HWP 파일 경로
            vlm_parser_func: VLM 파서 함수 (Optional)

        Returns:
            List[Dict]: [{'page_num': int, 'text': str, 'method': str}, ...]
        """
        print(f"\n  📄 HWP 파일 처리: {file_path.name}")

        # HWP 5.0 이상 (HWPX 형식)
        if file_path.suffix.lower() == ".hwpx":
            return self.load_hwpx(file_path, vlm_parser_func)

        # 방법 1: olefile로 PrvText 추출 시도 (팝업 없음, 빠름)
        print(f"  🔄 방법 1: olefile로 PrvText 추출 시도")
        olefile_result = None
        olefile_text_length = 0

        try:
            import olefile

            if olefile.isOleFile(file_path):
                ole = olefile.OleFileIO(file_path)
                texts = []

                # PrvText 추출
                if ole.exists("PrvText"):
                    try:
                        stream = ole.openstream("PrvText")
                        data = stream.read()
                        text = data.decode("utf-16le", errors="ignore")
                        text = text.replace("\x00", "")

                        if self._is_valid_korean_text(text):
                            texts.append(text.strip())
                            print(f"  ✓ PrvText 추출 성공 ({len(text)}자)")
                    except Exception as e:
                        print(f"  ⚠️ PrvText 추출 실패: {e}")

                ole.close()

                if texts:
                    full_text = "\n\n".join(texts)
                    full_text = self.text_cleaner.clean_ocr_text(full_text)
                    olefile_text_length = len(full_text)
                    olefile_result = [{"page_num": 1, "text": full_text, "method": "hwp_prvtext"}]
                    print(f"  ✅ olefile 추출 완료 ({olefile_text_length}자)")
        except ImportError:
            print(f"  ⚠️ olefile 미설치 (pip install olefile)")
        except Exception as e:
            print(f"  ⚠️ olefile 처리 실패: {e}")

        # olefile 결과 확인: 파일 크기 대비 텍스트가 충분하면 바로 반환
        # 파일 크기로 "얼마나 많이 남아있는지" 판단
        file_size_kb = file_path.stat().st_size / 1024
        # HWP 파일은 일반적으로 1KB당 약 100~200자의 텍스트 포함
        # PrvText는 전체의 약 30~50% 정도만 포함
        # 파일 크기 기반 + 최소 기준 둘 다 사용
        expected_min_chars = max(int(file_size_kb * 100), 1500)  # 최소 1500자 요구

        if olefile_result and olefile_text_length >= expected_min_chars:
            ratio = (olefile_text_length / expected_min_chars * 100) if expected_min_chars > 0 else 100
            print(f"  ✅ olefile로 충분한 텍스트 추출됨")
            print(f"     파일: {file_size_kb:.1f}KB, 추출: {olefile_text_length}자, 예상 최소: {expected_min_chars}자 ({ratio:.0f}%)")
            return olefile_result

        # 방법 2: olefile 실패 또는 텍스트 부족 → VLM OCR 폴백
        if olefile_result:
            shortage = expected_min_chars - olefile_text_length
            print(f"  ⚠️ olefile 텍스트 부족")
            print(f"     파일: {file_size_kb:.1f}KB, 추출: {olefile_text_length}자, 예상 최소: {expected_min_chars}자 (부족: {shortage}자)")
        else:
            print(f"  ⚠️ olefile 추출 실패")

        print(f"  🔄 방법 2: VLM OCR 폴백 (HWP → PDF → VLM)")

        if vlm_parser_func:
            # 2-1. HWP → PDF 변환
            pdf_path = self._convert_hwp_to_pdf(file_path)

            if pdf_path and pdf_path.exists():
                # 2-2. VLM으로 PDF 파싱
                result = vlm_parser_func(pdf_path)

                # 임시 PDF 삭제
                try:
                    pdf_path.unlink()
                    print(f"  🗑️ 임시 PDF 삭제됨")
                except:
                    pass

                if result:
                    print(f"  ✅ VLM OCR 성공")
                    return result
                else:
                    print(f"  ⚠️ VLM OCR 실패")

        # 방법 3: 모든 방법 실패 → olefile 결과라도 반환 (있으면)
        if olefile_result:
            print(f"  ⚠️ VLM OCR 실패, olefile 결과 사용 ({olefile_text_length}자)")
            print(f"  📌 PrvText는 문서 미리보기용으로 일부 내용만 포함됨")
            return olefile_result

        print(f"  ❌ 모든 HWP 처리 방법 실패")
        return []

    def load_hwpx(self, file_path: Path, vlm_parser_func=None) -> List[Dict]:
        """
        HWPX 파일 읽기 - PDF 변환 방식 우선

        Args:
            file_path: HWPX 파일 경로
            vlm_parser_func: VLM 파서 함수 (Optional)

        Returns:
            List[Dict]: [{'page_num': int, 'text': str, 'method': str}, ...]
        """
        print(f"\n  📄 HWPX 파일 처리: {file_path.name}")

        # 🆕 새로운 방식: HWPX → PDF 변환 후 처리
        print(f"  🔄 방법: HWPX → PDF 변환 후 기존 PDF 로직 사용")

        # 1. HWPX → PDF 변환
        pdf_path = self._convert_hwp_to_pdf(file_path)

        if pdf_path and pdf_path.exists():
            # 2. 변환된 PDF 처리 (VLM 파서 함수 사용)
            print(f"  📖 변환된 PDF 로드 중...")
            try:
                if vlm_parser_func:
                    result = vlm_parser_func(pdf_path)
                else:
                    result = []

                # 3. 임시 PDF 파일 삭제
                try:
                    pdf_path.unlink()
                    print(f"  🗑️ 임시 PDF 파일 삭제됨")
                except:
                    pass

                # 4. method를 'hwpx_via_pdf'로 표시
                for page in result:
                    page["method"] = "hwpx_via_pdf"

                print(f"  ✅ HWPX → PDF 변환 방식 처리 완료")
                return result

            except Exception as e:
                print(f"  ❌ 변환된 PDF 처리 실패: {e}")

                # 임시 파일 삭제 시도
                try:
                    if pdf_path.exists():
                        pdf_path.unlink()
                except:
                    pass

        # 변환 실패 시 기존 방식 폴백
        print(f"  ⚠️ PDF 변환 실패, 기존 방식(ZIP XML 파싱) 시도...")

        try:
            import zipfile
            import xml.etree.ElementTree as ET

            texts = []

            with zipfile.ZipFile(file_path, "r") as zip_ref:
                for name in zip_ref.namelist():
                    if name.startswith("Contents/section") and name.endswith(".xml"):
                        try:
                            xml_content = zip_ref.read(name)
                            root = ET.fromstring(xml_content)

                            section_texts = []
                            for elem in root.iter():
                                if elem.text and elem.text.strip():
                                    section_texts.append(elem.text.strip())
                                if elem.tail and elem.tail.strip():
                                    section_texts.append(elem.tail.strip())

                            section_text = "\n".join(section_texts)
                            if section_text and self._is_valid_korean_text(section_text):
                                texts.append(section_text)
                            else:
                                print(f"    ⚠️ 섹션 {name} 텍스트가 유효하지 않음 (건너뜀)")

                        except Exception as e:
                            print(f"    ⚠️ 섹션 {name} 파싱 실패: {e}")
                            continue

            if not texts:
                print("  ❌ 텍스트 추출 실패")
                return []

            full_text = "\n".join(texts)
            full_text = self.text_cleaner.clean_ocr_text(full_text)

            print(f"  ✓ HWPX 읽기 완료 (ZIP XML 폴백, {len(full_text)}자)")
            return [{"page_num": 1, "text": full_text, "method": "hwpx_xml"}]

        except Exception as e:
            print(f"  ❌ HWPX 읽기 실패: {e}")
            return []
