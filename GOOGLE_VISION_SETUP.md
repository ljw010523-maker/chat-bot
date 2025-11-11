# Google Cloud Vision API 설정 가이드

## 📋 개요

Google Cloud Vision API를 사용하여 문서 OCR 처리를 진행합니다.
- **무료 할당량**: 월 1,000회 호출 무료
- **특징**: 표, 도장, 날인 등 문서 구조 인식 우수
- **지원 언어**: 한국어 포함 50+ 언어

---

## 🚀 1단계: Google Cloud 프로젝트 생성

### 1.1 Google Cloud Console 접속
1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. Google 계정으로 로그인

### 1.2 새 프로젝트 생성
1. 상단 메뉴에서 **프로젝트 선택** 클릭
2. **새 프로젝트** 클릭
3. 프로젝트 이름 입력 (예: `document-ocr-project`)
4. **만들기** 클릭

---

## 🔑 2단계: Vision API 활성화 및 API 키 생성

### 2.1 Vision API 활성화
1. [Vision API 페이지](https://console.cloud.google.com/apis/library/vision.googleapis.com) 접속
2. 생성한 프로젝트 선택
3. **사용 설정** 클릭

### 2.2 서비스 계정 생성
1. [서비스 계정 페이지](https://console.cloud.google.com/iam-admin/serviceaccounts) 접속
2. **서비스 계정 만들기** 클릭
3. 서비스 계정 세부정보 입력:
   - **이름**: `vision-api-service`
   - **설명**: `Document OCR Service Account`
4. **만들기 및 계속하기** 클릭
5. 역할 부여:
   - **Cloud Vision API 사용자** 선택
6. **계속** 클릭
7. **완료** 클릭

### 2.3 JSON 키 파일 다운로드
1. 생성된 서비스 계정 클릭
2. **키** 탭 선택
3. **키 추가** → **새 키 만들기** 클릭
4. **JSON** 선택
5. **만들기** 클릭
6. JSON 키 파일이 자동으로 다운로드됩니다

**중요**: 이 JSON 파일은 안전하게 보관하세요!

---

## 💻 3단계: 환경 설정

### 3.1 필요 패키지 설치

```bash
pip install google-cloud-vision
```

### 3.2 인증 설정

#### 방법 1: 환경 변수 설정 (권장)

**Windows (PowerShell):**
```powershell
$env:GOOGLE_APPLICATION_CREDENTIALS="C:\path\to\your\service-account-key.json"
```

**Windows (명령 프롬프트):**
```cmd
set GOOGLE_APPLICATION_CREDENTIALS=C:\path\to\your\service-account-key.json
```

**Linux/Mac:**
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
```

#### 방법 2: 영구 설정

**Windows:**
1. **시스템 속성** → **고급** → **환경 변수** 클릭
2. **시스템 변수** 또는 **사용자 변수**에서 **새로 만들기** 클릭
3. 변수 이름: `GOOGLE_APPLICATION_CREDENTIALS`
4. 변수 값: JSON 키 파일 경로 (예: `C:\keys\vision-api-key.json`)
5. **확인** 클릭

**Linux/Mac:**
`~/.bashrc` 또는 `~/.zshrc` 파일에 추가:
```bash
export GOOGLE_APPLICATION_CREDENTIALS="/path/to/your/service-account-key.json"
```

그리고 적용:
```bash
source ~/.bashrc  # 또는 source ~/.zshrc
```

---

## 🧪 4단계: 테스트

### 4.1 Python 코드로 테스트

```python
from google.cloud import vision
import io

# 클라이언트 생성
client = vision.ImageAnnotatorClient()

# 테스트 이미지 파일
file_path = "test_image.png"

with io.open(file_path, 'rb') as image_file:
    content = image_file.read()

image = vision.Image(content=content)

# 텍스트 감지
response = client.text_detection(image=image)
texts = response.text_annotations

if texts:
    print("감지된 텍스트:")
    print(texts[0].description)
else:
    print("텍스트를 찾을 수 없습니다.")

if response.error.message:
    raise Exception(f'Error: {response.error.message}')
```

### 4.2 파이프라인 실행

이제 기존 파이프라인을 실행하면 Google Vision API가 자동으로 사용됩니다:

```bash
cd c:\Users\bravo\Desktop\test\back\scripts\pipeline
python pipeline.py
```

---

## 📊 5단계: 사용량 모니터링

### 5.1 할당량 확인
1. [Google Cloud Console - API 대시보드](https://console.cloud.google.com/apis/dashboard) 접속
2. **Vision API** 클릭
3. **할당량** 탭에서 사용량 확인

### 5.2 무료 할당량
- **문서 텍스트 감지**: 월 1,000회 무료
- **초과 시 비용**: 1,000회당 $1.50

### 5.3 비용 알림 설정
1. [결제 > 예산 및 알림](https://console.cloud.google.com/billing/budget) 접속
2. **예산 만들기** 클릭
3. 월 예산 금액 설정 (예: $5)
4. 알림 임계값 설정 (50%, 90%, 100%)
5. 이메일 알림 활성화

---

## 🔧 트러블슈팅

### 문제 1: "Could not automatically determine credentials"
**원인**: 환경 변수가 설정되지 않았거나 JSON 파일 경로가 잘못됨

**해결**:
```python
# 직접 키 파일 경로 지정
import os
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = r'C:\path\to\key.json'
```

### 문제 2: "Permission denied" 오류
**원인**: 서비스 계정에 Vision API 권한이 없음

**해결**:
1. [IAM 페이지](https://console.cloud.google.com/iam-admin/iam) 접속
2. 서비스 계정 찾기
3. **역할 수정** 클릭
4. **Cloud Vision API 사용자** 역할 추가

### 문제 3: API가 활성화되지 않음
**원인**: Vision API가 프로젝트에서 활성화되지 않음

**해결**:
```bash
# gcloud CLI로 활성화
gcloud services enable vision.googleapis.com
```

또는 [Vision API 페이지](https://console.cloud.google.com/apis/library/vision.googleapis.com)에서 수동 활성화

---

## 📚 참고 자료

- [Google Cloud Vision API 공식 문서](https://cloud.google.com/vision/docs)
- [Python 클라이언트 라이브러리](https://cloud.google.com/python/docs/reference/vision/latest)
- [가격 정책](https://cloud.google.com/vision/pricing)
- [할당량 및 한도](https://cloud.google.com/vision/quotas)

---

## ✅ 체크리스트

설정 완료 후 확인:

- [ ] Google Cloud 프로젝트 생성
- [ ] Vision API 활성화
- [ ] 서비스 계정 생성
- [ ] JSON 키 파일 다운로드
- [ ] `GOOGLE_APPLICATION_CREDENTIALS` 환경 변수 설정
- [ ] `google-cloud-vision` 패키지 설치
- [ ] 테스트 코드 실행 성공
- [ ] 파이프라인 실행 성공

---

## 🎯 다음 단계

Google Vision API 설정이 완료되면:

1. **문서 처리 테스트**: 스캔본 PDF/HWP 파일로 테스트
2. **결과 확인**: `data/chunks/` 폴더에서 추출 결과 확인
3. **성능 비교**: Tesseract OCR vs Google Vision API 비교
4. **비용 모니터링**: 사용량 체크 및 예산 관리

문제가 발생하면 위 트러블슈팅 섹션을 참고하세요!
