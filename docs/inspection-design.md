# MTC Inspection(등급 분류) 설계 — Phase 2-C

| 항목 | 내용 |
|---|---|
| **작성일** | 2026-09-09 (2.4.0 반영 2026-09-10) |
| **상태** | 구현 완료(2.4.0), 실앱 화면·fixture 확인 완료, 현장 검증 대기 |
| **관련** | [`PRD.md`](./PRD.md) F-22, [`HANDOFF_phase2.md`](./HANDOFF_phase2.md), 스크린샷 `assets/user-guide/inspection-mode.png` |

## 1. 배경과 목표

MTC 설비(ATX 4대 = TipExchanger1~4, 각 Port1/2 × Slot 12)는 슬롯별 픽업 → sweep → 풋백 결과를
런 폴더(`{YYYYMMDD}`)로 남긴다. 지금까지는 외부 "ATX Classification" 도구로 PASS/FAIL 을 나누고
Grouping 으로 `P2401002_12M_AC160` 로트 폴더를 만든 뒤, 그 폴더를 우리 앱 ATX 모드에서 열어 QR 을
태깅했다. 이 기능은 그 도구를 앱 안으로 흡수한다.

1. **등급 사다리**(산업용 → 연구용 → 재검사 → 불량) 템플릿으로 다단계 분류
2. sweep 곡선 형상 · Vision 팁 파손 **자동 판정**(사람은 이상 항목만 확인)
3. 로트 폴더 생성과 동시에 **ATX 모드 탭으로 바로 이어지는** 흐름(QR 태깅 → 이력 → 업로드)

확정 결정(2026-09-09): 등급 사다리 / 로트 폴더 + 앱 내부 전달 / 기준 슬롯 자동 + 수동 / 새 최상위
모드 Inspection(앱 다크 테마) / 산업용·연구용 각각 로트 / Unit No 로트마다 +1 / 단일 런 폴더 /
Sweep Shape 는 사다리 항목 / 파손은 Vision 자동 + 수동 override / Thermal Tune 제외 / 템플릿 별도 저장
+ 산업용 Freq/Q → Spec Limits 동기화.

## 2. 입력 데이터 계약 (런 폴더)

| 파일 | 키 | 항목 |
|---|---|---|
| `PSPD.txt` | Repeat / Tip Exchanger / Port / Slot (탭) | A+B, A-B, C-D (V) |
| `FreqSweep.txt`, `FreqSweep_ZoomOut.txt` | 〃 | Frequency (KHz), Set Point, Amplitude (nm), Drive (%), Q |
| `Vision.txt` | 〃 | Tip Focus (um), Tip X/Y (pxl), Match Score (%) |
| `Angle.txt` | `CantileverNo = {run}_{A}{P}{SS}` (행은 공백 구분) | Angle |
| `Exchange.txt` | 〃 | Delta Z (um) — **빈 슬롯도 전부 나열** → 슬롯 존재 판정에 쓰지 않음 |
| `Vision/Repeat1/TipExchanger{A}/Port{P}_{S}_pickUp.png`, `_putBack.png` | | 이미지 |
| `FreqSweep/Repeat1/TipExchanger{A}/Port{P}_{S}.jpg`, `_ZoomOut.jpg`, `.txt`(100점), `_ZoomOut.txt`(500점) | | 이미지 + 측정 원본 |

- 슬롯 존재 = PSPD ∪ FreqSweep ∪ ZoomOut ∪ Vision ∪ Angle. 줌인 sweep 이 없는 슬롯(예: 3112) = `No Sweep`.
- 슬롯 코드 `{A}{P}{SS}` 는 기존 `slot_mapper.parse_slot_code` 와 동일 → 로트 폴더/ATX 모드와 그대로 호환.
- 픽셀 → um: 스크린샷 역산 **0.345 um/px**(RefX−X 21.269 um = 61.65 px). 템플릿 `um_per_pixel` 로 편집.

## 3. 판정식 (원 도구와 동일)

| 항목 | 종류 | 판정 |
|---|---|---|
| A+B, A-B, C-D (V) | offset | `ref − offset ≤ value ≤ ref + offset` |
| Drive (%), Q, Frequency (kHz) | range | `min ≤ value ≤ max` (빈 쪽 무제한) |
| X/Y Offset (um) | range | `(ref_px − px) × um_per_pixel ∈ [min, max]` |
| Angle Offset (degree) | offset | `|angle − ref_angle| ≤ degree` |
| **Sweep Shape** (신규) | min | 형상 점수 `≥ min` |
| **Vision Match** (신규) | min | Match Score `≥ min` |
| **Broken** (자동) | — | Vision 파손이면 사다리와 무관하게 불량 |

Thermal Tune 은 런 폴더에 데이터가 없어 제외. 값이 없는 항목(None)은 활성 시 실패(bound `N/A`).

### 3.1 등급 사다리

산업용 → 연구용 → 재검사 순으로 **활성 항목을 전부** 검사해 첫 통과 등급을 부여, 전부 실패 = 불량.
모든 등급의 실패 항목을 기록하므로 Error 열은 **산업용 기준 실패 항목**(예: `A+B, Q, Sweep Shape`),
`Broken`, `No Sweep` 중 하나다. 우클릭 수동 지정(등급/파손)은 재판정·기준 변경 후에도 유지된다.

### 3.2 기본 템플릿 (AC160)

| 항목 | 산업용 | 연구용 | 재검사 |
|---|---|---|---|
| A+B offset | 1.0 | 1.5 | 2.0 |
| A-B / C-D offset | (off) 0 | (off) | (off) |
| Drive | (off) 0~80 | (off) | (off) |
| Q | 200~700 | 100~800 | 50~1000 |
| Frequency | 200~400 | 150~450 | 100~500 |
| X/Y Offset | (off) −10~10 | (off) | (off) |
| Angle | 3 | 5 | 8 |
| Sweep Shape | ≥ 70 | ≥ 50 | ≥ 30 |
| Vision Match | ≥ 95 | ≥ 90 | ≥ 80 |

산업용 값은 스크린샷 그대로. 실런 20260909(85슬롯) 결과: 산업용 46 / 연구용 16 / 재검사 8 / 불량 15
(원 도구 FAIL 31 + Sweep Shape 추가 감지).

## 4. sweep 형상 자동 판정 (`sweep_shape.py`, 수치 기반)

이미지에는 측정 곡선(굵은 선)과 Lorentzian 피팅(가는 선)이 같이 그려져 있으므로, 이미지 비교 대신
`Port{P}_{S}.txt`(100점) · `_ZoomOut.txt`(500점) 수치로 판정한다.

| 지표 | 계산 | 감점 |
|---|---|---|
| 피크 수 | 3점 이동평균 후 최대의 30% 이상·prominence 8% 이상인 국소 최대 | 35 × (n−1), 최대 70 |
| Lorentzian R² | `A(f) = b + (A0−b)/(1+((f−f0)/γ)²)`, f0(피크 ±3점)·b·A0·γ 격자 탐색(numpy) | (1−R²) × 300, 최대 45 |
| 비대칭 | 반높이 교차점까지 좌/우 거리비 | (asym − 1.15) × 40, 최대 20 |
| ZoomOut 부피크 | 주피크 ±10 kHz 밖 최대 진폭 / 주피크 진폭 | (ratio − 0.5) × 40, 최대 30 |

점수 = 100 − 감점(0~100). 정상 곡선 ≈ 85~95, 어깨 왜곡 + 288 kHz 부피크(3212) ≈ 19, 잡음 다봉(1102) = 0.
근거는 `reasons`(예: `fit R2 0.89, asym 2.16, side peak 1.24× @288kHz`)로 Error·차트 오버레이·리포트에 표시.
85슬롯 0.4초.

## 5. Vision 파손 자동 판정 (`vision_check.py`)

pickUp PNG(그레이)에서 ① 어두운 픽셀 비율 ≥ 50% 인 마지막 행 = 칩 몸체 하단 기준선, ② 기준선 아래
외곽선 구간(3%)을 건너뛰고 10% 까지의 행에서 어두운 열 범위 = 캔틸레버 밴드, ③ 밴드 안 마지막 어두운 행
− 기준선 = **팁 길이**, 밴드 안 어두운 픽셀 수 = 면적. 기준 슬롯 대비 길이 < 70% 또는 면적 < 60% 면
파손(해상도 무관). 기준이 없으면 이미지 높이 대비 15% 미만. Match Score 임계는 `Vision Match` 항목.
85장 1.3초(워커 스레드).

## 6. 기준 캔틸레버 (`reference.py`)

(ATX, Port, Slot) 순서상 sweep·PSPD·Vision·Angle 이 모두 있고 Match ≥ 99 인 첫 슬롯. 없으면 sweep+Vision
만 있는 첫 슬롯. 우클릭 `기준 캔틸레버로 지정` 또는 `현재 슬롯을 기준으로` 로 변경하면 오프셋·Vision
비율을 재계산해 즉시 재판정.

## 7. 로트 생성 (`lot_builder.py`)

- 대상 = Grouping 등급(산업용/연구용) 통과 슬롯 중 아직 로트로 내보내지 않은 것, (ATX, Port, Slot) 순.
- 계획 `12M × n, 10M × m, 5M × k`(큰 로트 먼저). 합계 > 통과 수 → `INVALID`.
- 폴더 `{UnitNo}_{qty}M_{TipID}`: `Summary.csv`(`Batch,{batch}_{code},…` / `Freq` / `Q`, 후행 콤마),
  `FreqSweep/{n}_{batch}_{code}.jpg|_ZoomOut.jpg|.txt|_ZoomOut.txt`, `Vision/{n}_{batch}_{code}_pickUp.png|_putBack.png`.
  **기존 `load_atx_folder` 가 그대로 읽는 형식**(라운드트립 테스트).
- Unit No 는 로트마다 뒤 숫자 +1(자릿수 유지). Batch 기본 `{tip소문자}({run})`.
- 생성된 로트는 `ATXImportMixin._atx_open_set_in_tab` 으로 즉시 탭 오픈(DB 자동 저장, Drive 포함) → ATX 모드
  전환. 내보낸 슬롯은 표 Error 열에 `→ P2401002` 로 표시되고 다음 Grouping 대상에서 빠진다.
- `Save` = 검사 리포트 CSV(`Inspection_{run}.csv`, 전 슬롯 등급·Error·원시값·오프셋·sweep 점수·vision).

### 7.1 기존 로트 폴더와의 대조 (2026-09-09)

`P2601001_12M_AC160`·`P2601002_12M_AC160` 과 비교: 폴더명·Summary.csv·FreqSweep/Vision 파일명·채우기 순서((ATX, Port, Slot)
오름차순, 12개씩) 모두 일치. 차이는 두 가지 — ① Batch 문자열 `ac160(0001~0004)` 의 범위 의미는 미확인(→ 자유 텍스트,
마지막 입력값 기억), ② `{Unit}_{12}M_{모델명}TS.xlsx` 체크시트(Unit, Type `AC160TS`, SEM/SPEC 이미지, Backside·A+B·
Unipeak·Noise·Frequency Sweep Pass/Fail, Batch 1(L)~12(R) Frequency/Q, 보증 문구).

### 7.2 체크시트 (`check_sheet.py`)

템플릿 xlsx 를 openpyxl 로 열면 이미지가 사라지므로 **zip 안의 `sheet1.xml` 셀만 교체**(문자열 = inlineStr, 숫자 = v).
B4 Unit · B5 Type(템플릿의 `정식 모델명`, 예 AC160TS) · L/M26 Backside(템플릿 유지) · L/M28 A+B · L/M31 Unipeak ·
L/M32 Noise · L/M34 Frequency Sweep · B41~M41 Frequency · B42~M42 Q. 로트가 12개 미만이면 남는 열은 비움.
판정(산업용 기준, 로트 내 전부 통과 시 ■): A+B = A+B 항목 통과, Unipeak = 피크 1개, Noise = Sweep 점수 ≥ 산업용 min,
Frequency Sweep = Frequency 범위 통과. 템플릿 경로가 비어 있거나 없으면 체크시트는 건너뛴다(로그 경고).

## 8. 구성 파일

```
src/core/inspection/   mtc_parser · sweep_shape · vision_check · reference · templates · grading · lot_builder
src/ui/controllers/inspection_mixin.py      상태·이벤트 + InspectionWorker(QThread)
src/ui/widgets/inspection_page.py           3열 레이아웃(뷰 전용)
src/ui/widgets/sweep_verdict_chart.py       matplotlib 판정 차트 (더블클릭 → Explorer)
src/ui/widgets/sweep_explorer_window.py     pyqtgraph 인터랙티브 창(크로스헤어·피크 표·공진 세로선·기준 오버레이)
src/ui/dialogs/image_popup_dialog.py        이미지 더블클릭 확대 창
src/ui/widgets/inspection_layout_window.py  레이아웃 보기(ATX 2×2 · Port 상하 실물 배치, 색 기준 콤보)
src/ui/dialogs/inspection_template_dialog.py  템플릿 New
tests/fixtures/mtc/20260909/                실런 7슬롯 발췌(PNG 800×600 축소)
tests/test_mtc_parser · test_sweep_shape · test_vision_check · test_inspection_grading · test_lot_builder · test_inspection_mixin
```

설정 키: `app_settings.inspection_templates`({tip_id: template}), `inspection_last_tip`, `inspection_lot_dir`.
템플릿 Save 시 산업용 Frequency/Q 가 `spec_limits[tip_id]` 에 반영되어 History 수율·Pass Pool 과 기준이 같아진다.

### 8.1 Sweep Explorer (읽기 전용)

판정 차트 더블클릭 → 비모달 창(여러 개 동시). 위 ZoomOut·아래 줌인, 크로스헤어는 최근접 데이터 점에 스냅해
주파수·진폭 표시. 공진 세로선 = MTC Frequency(주황) · 측정 최대 피크(빨강) · Lorentzian f0(청록).
피크 표는 `sweep_shape.peak_details`(prominence, 반높이 FWHM, Q 추정 = f/FWHM). 판정 값은 바꾸지 않는다.

### 8.2 레이아웃 보기

`레이아웃 보기` 버튼 → 비모달 창 1개. ATX1 좌상·ATX2 우상·ATX3 좌하·ATX4 우하, ATX 안은 Port2 위·Port1 아래(상하),
Port 는 `slot_mapper.slot_to_grid`(Slot 1 좌하단) 규칙. 셀 배경 = 등급 색(기본) 또는 Sweep 점수·Frequency·Q 그라데이션,
빈 슬롯 = 점선. 결과표의 등급 필터(기본 전부 표시, 체크 해제 = 숨김)는 레이아웃에서 흐림으로 반영되고,
셀 클릭은 표 행 선택과 같은 경로(`row_selected`)를 타므로 상세·Explorer·우클릭 메뉴가 그대로 동작한다.

## 9. 후속 (미구현)

- 다중 런 폴더 합산(스크린샷 "and 0 more") — 남은 칩을 다음 런과 모아 12M 채우기
- 어깨(shoulder) 전용 검출, 임계 자동 캘리브레이션(정상 분포 기반)
- Vision 파손 판정의 실제 파손 샘플 검증(현재 합성 이미지 테스트만)
- 사용자 가이드 PDF 재생성 완료(2026-09-10, `docs/MC_QR_Manager_User_Guide_v2.4.0.pdf`)
