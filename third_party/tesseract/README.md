# Tesseract Portable (F-14)

이 디렉터리에는 Manual 모드 이미지 OCR 기능(F-14)을 위한 **Tesseract 5.x Windows
포터블 바이너리**를 배치한다. 바이너리는 `.gitignore`로 제외되어 있으므로 각 설치 환경에서
별도로 다운로드/배치해야 한다.

## 필요한 파일

```
third_party/tesseract/
├── tesseract.exe                         (약 5 MB)
├── liblept-5.dll                         (UB Mannheim 빌드 동봉)
├── libtesseract-5.dll
├── ... (UB Mannheim 설치 시 동봉되는 다른 DLL들)
├── LICENSE                               (Apache-2.0, 필수 동봉)
└── tessdata/
    └── eng.traineddata                   (약 4 MB — 숫자 인식용이라 eng만 필요)
```

## 다운로드 방법

1. **UB Mannheim 빌드** (권장):
   <https://github.com/UB-Mannheim/tesseract/wiki>
   - `tesseract-ocr-w64-setup-5.x.x.exe` 설치 후 설치 폴더(보통
     `C:\Program Files\Tesseract-OCR\`)에서 위 파일들을 복사
2. `tessdata`는 설치 시 동봉되며 `eng.traineddata`만 있으면 충분 (숫자 전용 인식)
3. `LICENSE` 는 설치 폴더의 `licenses/` 하위에서 가져오기

## 미설치 시 동작

Tesseract 바이너리가 없으면 `image_parser.extract_measurements()` 가
`MeasurementReading(None, None)` 을 반환하며 Manual 모드는 **기존 수기 입력
워크플로우**가 그대로 동작한다. 앱 구동에는 지장 없음.

## 관련 코드

- `src/core/tesseract_setup.py` — 포터블 경로 등록
- `src/core/image_parser.py` — ROI 크롭 + OCR + 숫자 파싱
- `src/ui/controllers/manual_import_mixin.py` — 이미지 드롭 시 자동 호출
