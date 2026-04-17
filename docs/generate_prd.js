const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  Header, Footer, AlignmentType, PageOrientation, LevelFormat,
  TabStopType, TabStopPosition, HeadingLevel, BorderStyle, WidthType,
  ShadingType, VerticalAlign, PageNumber, PageBreak,
} = require("docx");

// ---- Helpers ----
const H1 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_1,
    children: [new TextRun({ text, font: "Malgun Gothic" })],
  });

const H2 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_2,
    children: [new TextRun({ text, font: "Malgun Gothic" })],
  });

const H3 = (text) =>
  new Paragraph({
    heading: HeadingLevel.HEADING_3,
    children: [new TextRun({ text, font: "Malgun Gothic" })],
  });

const P = (text, opts = {}) =>
  new Paragraph({
    spacing: { after: 120 },
    children: [
      new TextRun({ text, font: "Malgun Gothic", size: 22, ...opts }),
    ],
  });

const Bullet = (text) =>
  new Paragraph({
    numbering: { reference: "bullets", level: 0 },
    children: [new TextRun({ text, font: "Malgun Gothic", size: 22 })],
  });

const SubBullet = (text) =>
  new Paragraph({
    numbering: { reference: "bullets", level: 1 },
    children: [new TextRun({ text, font: "Malgun Gothic", size: 22 })],
  });

const NumItem = (text) =>
  new Paragraph({
    numbering: { reference: "numbers", level: 0 },
    children: [new TextRun({ text, font: "Malgun Gothic", size: 22 })],
  });

const Code = (text) =>
  new Paragraph({
    spacing: { before: 80, after: 80 },
    shading: { fill: "F2F2F2", type: ShadingType.CLEAR },
    children: [
      new TextRun({ text, font: "Consolas", size: 20 }),
    ],
  });

const Blank = () => new Paragraph({ children: [new TextRun("")] });

const border = { style: BorderStyle.SINGLE, size: 4, color: "CCCCCC" };
const borders = { top: border, bottom: border, left: border, right: border };

const TCell = (text, opts = {}) =>
  new TableCell({
    borders,
    width: opts.width,
    shading: opts.shading,
    margins: { top: 80, bottom: 80, left: 120, right: 120 },
    verticalAlign: VerticalAlign.CENTER,
    children: [
      new Paragraph({
        alignment: opts.align || AlignmentType.LEFT,
        children: [
          new TextRun({
            text,
            font: "Malgun Gothic",
            size: 20,
            bold: opts.bold || false,
            color: opts.color,
          }),
        ],
      }),
    ],
  });

const makeTable = (columnWidths, rows) => {
  const total = columnWidths.reduce((a, b) => a + b, 0);
  return new Table({
    width: { size: total, type: WidthType.DXA },
    columnWidths,
    rows: rows.map(
      (cells, rowIdx) =>
        new TableRow({
          children: cells.map((cell, colIdx) => {
            if (cell && typeof cell === "object" && "__cell" in cell) {
              return TCell(cell.text, {
                width: { size: columnWidths[colIdx], type: WidthType.DXA },
                align: cell.align,
                bold: cell.bold,
                color: cell.color,
                shading: cell.shading,
              });
            }
            const isHeader = rowIdx === 0;
            return TCell(String(cell), {
              width: { size: columnWidths[colIdx], type: WidthType.DXA },
              bold: isHeader,
              shading: isHeader
                ? { fill: "D5E8F0", type: ShadingType.CLEAR }
                : undefined,
            });
          }),
        })
    ),
  });
};

// ---- Content ----
const today = "2026-04-17";

const children = [];

// Title
children.push(
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: 0, after: 240 },
    children: [
      new TextRun({
        text: "NX QR Chip Carrier Manager",
        font: "Malgun Gothic",
        size: 44,
        bold: true,
      }),
    ],
  })
);
children.push(
  new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { after: 240 },
    children: [
      new TextRun({
        text: "제품 요구사항 명세서 (PRD)",
        font: "Malgun Gothic",
        size: 30,
        bold: true,
      }),
    ],
  })
);

// Document info table
children.push(
  makeTable(
    [2340, 7020],
    [
      ["항목", "내용"],
      ["문서 버전", "v1.0 (코드 기반 초안)"],
      ["작성일", today],
      ["작성자", "Levi.beak"],
      ["대상 제품", "NX QR Chip Carrier Manager"],
      ["현재 단계", "Phase 1~3 완료 · Phase 4 이전 피드백 수집 중"],
      ["관련 코드", "main.py → src/core, src/ui"],
    ]
  )
);
children.push(Blank());
children.push(new Paragraph({ children: [new PageBreak()] }));

// 1. 개요
children.push(H1("1. 개요"));

children.push(H2("1.1 배경"));
children.push(
  P(
    "AFM(Atomic Force Microscope) 측정 환경에서는 칩 캐리어 단위로 프로브(probe) 특성을 측정하고, " +
      "결과(Frequency, Drive, Q-factor)를 캐리어별 QR 코드와 연결해 관리한다. 기존에는 측정 결과 CSV와 QR ID " +
      "매칭을 사람이 수작업으로 수행해 오탈자·누락이 잦았고, 서버 업로드도 별도 수동 프로세스였다."
  )
);
children.push(H2("1.2 목적"));
children.push(
  P(
    "본 프로그램은 AFM 칩 캐리어 QR 코드와 측정 데이터를 한 화면에서 매칭·검증·업로드하는 데스크톱 도구로, " +
      "다음을 목표로 한다."
  )
);
children.push(Bullet("측정 데이터(ATX 자동/수동)와 QR 코드의 1:1 매칭 정확도 확보"));
children.push(Bullet("CSV + 이미지 파일을 서버 표준 포맷으로 일괄 업로드"));
children.push(Bullet("Catppuccin Mocha 다크 테마 기반의 시각적 부담 완화"));
children.push(Bullet("반복 작업(다중 슬롯 QR 입력)의 단계 수 최소화"));

children.push(H2("1.3 대상 사용자"));
children.push(
  makeTable(
    [2340, 3510, 3510],
    [
      ["사용자", "주요 업무", "본 제품 사용 맥락"],
      [
        "측정 엔지니어 (주 사용자)",
        "AFM 장비로 프로브 특성 측정 · 결과 정리",
        "ATX 폴더 로드 → QR 스캔 → 서버 업로드 (일일 다수 캐리어)",
      ],
      [
        "생산·품질 담당자",
        "수동 측정 결과 기록 · 보고",
        "Manual Mode로 데이터 입력 → 이미지 첨부 → CSV 내보내기",
      ],
      [
        "시스템 관리자",
        "서버 연동 · 계정 관리",
        "업로드 실패 로그 확인, 인증 자격 관리",
      ],
    ]
  )
);
children.push(Blank());

// 2. 제품 정의
children.push(H1("2. 제품 정의"));

children.push(H2("2.1 한 줄 소개"));
children.push(
  P(
    "AFM 칩 캐리어에 부착된 QR 코드를 스캔해 측정 데이터(Frequency / Drive / Q-factor)와 이미지를 " +
      "매칭하고, 사내 서버에 일괄 업로드하는 PySide6 기반 데스크톱 프로그램."
  )
);

children.push(H2("2.2 제품 범위 (Scope)"));
children.push(H3("포함 (In-Scope)"));
children.push(Bullet("ATX 결과 폴더 파싱(Summary.csv + FreqSweep 이미지)"));
children.push(Bullet("사용자 수기 입력 측정 모드 (Manual Mode)"));
children.push(Bullet("외장 바코드 스캐너(키보드 에뮬레이션) 기반 QR 입력"));
children.push(Bullet("CSV 표준 포맷 내보내기 및 이미지 재명명/정리"));
children.push(Bullet("Django 기반 서버 로그인 및 CSRF + multipart 업로드"));

children.push(H3("제외 (Out-of-Scope, 현시점)"));
children.push(Bullet("카메라 기반 실시간 QR 인식(현재는 외장 스캐너 전제)"));
children.push(Bullet("장비(AFM 컨트롤러) 직접 제어"));
children.push(Bullet("로컬 DB를 이용한 세션 이어쓰기 / 이력 조회"));
children.push(Bullet("다국어(i18n) 동적 전환 - 현재는 영문 하드코딩"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// 3. 현재 구현 기능
children.push(H1("3. 현재 구현 기능 (v1.0 = Phase 1~3)"));

children.push(H2("3.1 Phase 1 - ATX 기반 매칭"));
children.push(Bullet("ATX 결과 폴더 로드: {PO}_{Qty}M_{ProbeType} 네이밍 규칙 파싱"));
children.push(Bullet("Summary.csv의 Frequency, Q-factor를 슬롯 단위로 파싱"));
children.push(Bullet("슬롯 그리드(Port-grouped section) 시각화"));
children.push(Bullet("슬롯 선택 → FreqSweep 이미지 뷰어 표시"));
children.push(Bullet("QR 스캔 시 중복 방지 검사 후 현재 슬롯에 ID 배정"));
children.push(Bullet("매칭 완료 시 자동으로 다음 미매칭 슬롯으로 포커스 이동"));

children.push(H2("3.2 Phase 2 - 수동 측정 워크플로우"));
children.push(Bullet("Probe Type 탭 동적 생성 (예: AC160)"));
children.push(Bullet("이미지 드래그 앤 드롭 → ManualCard 자동 생성"));
children.push(Bullet("Frequency / Drive / Q-factor 수기 입력 + Apply"));
children.push(Bullet("카드 상태 배지: EMPTY → INCOMPLETE → PASS"));
children.push(Bullet("Overview 탭: 모든 Probe Type의 집계 현황"));

children.push(H2("3.3 Phase 3 - 서버 연동 + 영문화 + 버그 수정"));
children.push(Bullet("Django 로그인(CSRF 토큰 추출) + 세션 쿠키 유지"));
children.push(Bullet("표준 CSV 생성(utf-8-sig) + 이미지 QR ID로 재명명"));
children.push(Bullet("ZOOMIN 폴더에 이미지 재구성 후 multipart 업로드"));
children.push(Bullet("전 UI 영문 로컬라이즈"));
children.push(Bullet("다중 QR 입력 시 경로 인코딩 · 중복 처리 버그 수정"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// 4. 핵심 사용자 여정
children.push(H1("4. 핵심 사용자 여정 (User Flows)"));

children.push(H2("4.1 ATX Mode 플로우"));
children.push(NumItem('"Load ATX Folder" 클릭 → {PO}_{Qty}M_{ProbeType} 폴더 선택'));
children.push(NumItem("Summary.csv가 파싱되어 12개 슬롯 카드가 Port 그룹 단위로 그리드에 표시됨"));
children.push(NumItem("사용자가 슬롯을 클릭 → FreqSweep 이미지가 좌측 뷰어에 표시됨"));
children.push(NumItem("외장 QR 스캐너로 캐리어 QR 코드 스캔 → QR Input Widget에 입력됨"));
children.push(NumItem("중복 검사 통과 시 현재 슬롯에 QR ID 배정, 배지가 PASS로 갱신"));
children.push(NumItem("포커스가 다음 미매칭 슬롯으로 자동 이동"));
children.push(NumItem('12개 슬롯 완료 후 "Export & Upload"로 서버 업로드'));

children.push(H2("4.2 Manual Mode 플로우"));
children.push(NumItem('"+ New Probe Type" 로 탭 생성 (예: AC160)'));
children.push(NumItem("이미지 파일을 탭에 드래그 앤 드롭 → ManualCard 자동 생성"));
children.push(NumItem("카드 선택 → 좌측 뷰어에 이미지 표시, 입력 폼 활성화"));
children.push(NumItem("Frequency / Drive / Q 입력 → Apply → 배지 INCOMPLETE"));
children.push(NumItem("QR 스캔 → 배지 PASS, 다음 카드로 포커스 이동"));
children.push(NumItem("Overview 탭에서 전체 완료 여부 확인 → CSV 내보내기"));

children.push(H2("4.3 서버 업로드 플로우"));
children.push(
  Code(
    "[1] GET /accounts/login/         → HTML에서 csrfmiddlewaretoken 추출\n" +
      "[2] POST /accounts/login/        → username/password + csrf token\n" +
      "[3] export_with_images()         → CSV 생성 + 이미지 QR ID로 재명명\n" +
      "[4] POST /chip/login/probe/update/file (multipart)\n" +
      "     · csrfmiddlewaretoken\n" +
      "     · test_file: chip_carrier.csv (utf-8-sig)\n" +
      "     · image_files[]: <QR_ID>.jpg ...\n" +
      "[5] 응답 HTML에서 error/fail/오류/실패 키워드로 성공 여부 판정"
  )
);

children.push(new Paragraph({ children: [new PageBreak()] }));

// 5. 기능 요구사항
children.push(H1("5. 기능 요구사항 (Functional Requirements)"));
children.push(
  makeTable(
    [1080, 2700, 4580, 1000],
    [
      ["ID", "기능", "요구사항", "상태"],
      ["F-01", "ATX 폴더 로드", "폴더명에서 PO/Qty/ProbeType 추출, Summary.csv를 다중 인코딩으로 파싱", "완료"],
      ["F-02", "슬롯 그리드 표시", "12개 슬롯을 Port 그룹 단위로 시각화, 상태 배지 표시", "완료"],
      ["F-03", "FreqSweep 이미지 표시", "슬롯 선택 시 해당 이미지 뷰어 노출", "완료"],
      ["F-04", "QR 중복 방지", "스캔한 QR이 이미 다른 슬롯에 할당되었는지 검사", "완료"],
      ["F-05", "자동 다음 슬롯 포커스", "매칭 완료 시 비어 있는 다음 슬롯으로 이동", "완료"],
      ["F-06", "Manual Probe Type 탭", "사용자가 Probe Type을 런타임에 추가 가능", "완료"],
      ["F-07", "이미지 드래그 앤 드롭", "파일 탐색기에서 이미지를 끌어다 놓아 카드 생성", "완료"],
      ["F-08", "수기 측정 입력", "Frequency / Drive / Q 3개 값 입력 + Apply", "완료"],
      ["F-09", "CSV 내보내기", "QR ID, 생산일자, Freq, Drive, Q, Probe Type 6컬럼 · utf-8-sig", "완료"],
      ["F-10", "이미지 QR ID 재명명", "원본 파일을 QR ID 기반으로 복제 및 ZOOMIN 폴더로 이동", "완료"],
      ["F-11", "서버 로그인", "Django CSRF 토큰 추출 및 세션 쿠키 유지", "완료"],
      ["F-12", "일괄 업로드", "CSV + 이미지 파일을 multipart/form-data로 전송", "완료"],
      ["F-13", "시스템 로그", "색상 구분 로그 영역에 진행·경고·오류 표시", "완료"],
      ["F-14", "다중 QR 일괄 파싱", "한 이미지에서 여러 QR을 인식해 자동 매칭", "후보(Phase 4)"],
      ["F-15", "세션 저장/복원", "작업 중단 시점 이후 재시작", "후보(Phase 4)"],
      ["F-16", "측정 이력 조회", "과거 업로드 결과를 로컬에서 조회", "후보(Phase 4)"],
    ]
  )
);
children.push(Blank());

children.push(new Paragraph({ children: [new PageBreak()] }));

// 6. 비기능 요구사항
children.push(H1("6. 비기능 요구사항 (Non-Functional Requirements)"));
children.push(
  makeTable(
    [2160, 7200],
    [
      ["분류", "요구사항"],
      ["성능", "12슬롯 ATX 폴더 로드 < 2초, 이미지 썸네일 표시 < 500ms"],
      ["업로드 성능", "CSV 1건 + 이미지 12장 업로드 < 10초 (사내망 기준)"],
      ["신뢰성", "업로드 실패 시 시스템 로그에 원인 키워드와 HTTP 상태 기록"],
      ["사용성", "Catppuccin Mocha 다크 테마 · 키보드 중심 워크플로우"],
      ["호환성", "Windows 10/11 · Python 3.11+ · PySide6 6.6+"],
      ["보안", "SSL verify=False는 내부망 전제 · 외부망 적용 시 인증서 검증 필요"],
      ["국제화", "현재 UI 전체 영문 · 로케일 전환은 향후 과제"],
    ]
  )
);
children.push(Blank());

// 7. 데이터 모델
children.push(H1("7. 데이터 모델"));
children.push(P("src/core/models.py 기준 주요 엔터티."));

children.push(H2("7.1 SlotData"));
children.push(
  Code(
    "@dataclass\nclass SlotData:\n" +
      "    slot_index: int          # 0-11\n" +
      "    slot_code: str           # 예: \"_1102\"\n" +
      "    frequency: float | None\n" +
      "    drive: float | None\n" +
      "    q_factor: float | None\n" +
      "    qr_id: str | None        # 스캔 배정\n" +
      "    image_path: str | None   # FreqSweep JPG 경로\n" +
      "    source: str              # \"summary_csv\" | \"manual\"\n" +
      "    probe_type: str | None\n" +
      "\n    @property\n    def is_complete(self) -> bool: ...\n" +
      "    @property\n    def grid_position(self) -> tuple[int, int]: ..."
  )
);

children.push(H2("7.2 MeasurementSet"));
children.push(
  Code(
    "@dataclass\nclass MeasurementSet:\n" +
      "    po_number: str           # 예: \"P2601001\"\n" +
      "    quantity: int            # Qty M (보통 12)\n" +
      "    probe_type: str          # 예: \"AC160\"\n" +
      "    production_date: str     # YYYYMMDD\n" +
      "    slots: list[SlotData]\n" +
      "    source_folder: str\n" +
      "    mode: str                # \"atx\" | \"manual\"\n" +
      "\n    @property\n    def matched_count(self) -> int: ...\n" +
      "    @property\n    def all_complete(self) -> bool: ..."
  )
);

children.push(new Paragraph({ children: [new PageBreak()] }));

// 8. UI 구성
children.push(H1("8. UI 구성"));
children.push(P("QStackedWidget 기반 3페이지 + 상시 표시 영역으로 구성."));
children.push(
  makeTable(
    [2160, 7200],
    [
      ["화면", "주요 구성요소"],
      [
        "ATX Mode (Index 0)",
        "Folder Browser · Slot Grid(Port-grouped) · FreqSweep Viewer · Drive Input · QR Scanner · Log",
      ],
      [
        "Manual Mode (Index 1)",
        "Image Viewer · Measurement Input Form · Probe Type Tabs · ManualGrid · Overview",
      ],
      [
        "CSV Export (Index 2)",
        "CSV Preview Table · Export Buttons(CSV-only / CSV+Images)",
      ],
      ["Toolbar (항상 표시)", "Mode 전환 버튼 · Production Date Picker"],
      ["Bottom Bar (항상 표시)", "QR Input Widget · Progress Bar · Status Indicators"],
    ]
  )
);
children.push(Blank());

// 9. 서버 API
children.push(H1("9. 서버 API 사양"));
children.push(H2("9.1 엔드포인트"));
children.push(
  Code(
    "Base URL : https://probe-info.parksystems.com\n" +
      "Login    : GET/POST /accounts/login/\n" +
      "Upload   : POST     /chip/login/probe/update/file"
  )
);

children.push(H2("9.2 업로드 페이로드 (multipart/form-data)"));
children.push(
  Code(
    "csrfmiddlewaretoken : <token>\n" +
      "upload              : \"\"                (신규) 또는 update: \"\" (갱신)\n" +
      "test_file           : chip_carrier.csv  (text/csv, utf-8-sig)\n" +
      "image_files[]       : <QR_ID>.jpg ...   (image/jpeg | image/png)"
  )
);

children.push(H2("9.3 CSV 포맷"));
children.push(
  Code(
    "QR ID,생산일자[YYYYMMDD],Frequency (KHz),Drive (%),Q,Probe Type\n" +
      "QRCODE001,20260417,327.6,5.2,614,AC160\n" +
      "QRCODE002,20260417,306.6,4.8,420,AC160"
  )
);

children.push(new Paragraph({ children: [new PageBreak()] }));

// 10. 기술 스택
children.push(H1("10. 기술 스택"));
children.push(
  makeTable(
    [2160, 1800, 5400],
    [
      ["카테고리", "선택", "비고"],
      ["UI 프레임워크", "PySide6 ≥ 6.6", "QMainWindow + QStackedWidget + QSplitter"],
      ["시각화", "Matplotlib", "현재는 이미지 뷰어에 집중, 차트 용도 미활용"],
      ["HTTP 클라이언트", "requests ≥ 2.31", "세션 기반 Django 로그인"],
      ["HTML 파싱", "beautifulsoup4 ≥ 4.12", "CSRF 토큰 추출"],
      ["Excel", "openpyxl ≥ 3.1", "의존성만 존재, 적극 사용 X"],
      ["언어", "Python 3.11+", "PEP 604 union type 사용"],
      ["테마", "Catppuccin Mocha (자체 구현)", "src/ui/theme.py"],
      ["QR 입력", "외장 바코드 스캐너", "키보드 에뮬레이션 전제"],
    ]
  )
);
children.push(Blank());

// 11. 알려진 한계
children.push(H1("11. 알려진 한계와 개선 과제"));
children.push(H2("11.1 사용자 핵심 고민: 다중 QR 파싱"));
children.push(
  P(
    "현재 워크플로우는 한 번의 스캔 = 한 슬롯 배정이다. 한 장의 이미지(또는 한 화면)에서 " +
      "여러 칩 캐리어 QR 코드가 동시에 인식되는 상황은 지원하지 않는다. 고처리량 운용 시 " +
      "슬롯을 수동으로 선택하고 QR을 순차 스캔하는 단계가 병목이 된다."
  )
);
children.push(P("검토 가능한 접근:"));
children.push(Bullet("이미지 입력 기반 pyzbar/opencv로 다중 QR을 배치 디코딩 후 슬롯에 일괄 배정"));
children.push(Bullet("QR의 접미/접두 패턴으로 슬롯 번호를 유추(예: QR 뒤 2자리가 슬롯 인덱스)"));
children.push(Bullet("스캐너가 연속 입력한 여러 QR을 개행 구분자로 받아 큐에 적재, 순서 기반 자동 배정"));
children.push(Bullet("사용자 확인용 프리뷰(어느 QR이 어느 슬롯에 매칭될지) 다이얼로그 추가"));

children.push(H2("11.2 기타 한계"));
children.push(Bullet("데이터 영속성 부재: 앱 종료 시 모든 작업 상태 소실 (세션 저장/복원 없음)"));
children.push(Bullet("오류 감지 휴리스틱: 서버 응답 HTML에서 키워드 매칭으로 성공/실패 판별 - 취약"));
children.push(Bullet("SSL 검증 비활성화: verify=False, 사내망 전제 (외부망 이관 시 재검토 필요)"));
children.push(Bullet("이력 조회 기능 없음: 업로드한 결과를 앱 내에서 다시 볼 수 없음"));
children.push(Bullet("다국어 전환 불가: 영문 하드코딩으로 한글 UI 요구 시 재작업 필요"));
children.push(Bullet("카메라/라이브 인식 미지원: 외장 스캐너 없이 사용 불가"));

children.push(new Paragraph({ children: [new PageBreak()] }));

// 12. 다음 단계
children.push(H1("12. 다음 단계 (Next Steps)"));
children.push(H2("12.1 단기: 사용자 피드백 수집"));
children.push(Bullet("현장 사용자(측정 엔지니어 3~5명) 관찰 세션으로 워크플로우 병목 파악"));
children.push(Bullet("Manual Mode vs ATX Mode 사용 비율 측정 → 개선 우선순위 결정"));
children.push(Bullet("업로드 실패 케이스 로그 수집 후 오류 분류 체계화"));

children.push(H2("12.2 중기: Phase 4 후보 기능"));
children.push(
  makeTable(
    [720, 3240, 2160, 3240],
    [
      ["우선", "기능", "유형", "기대 효과"],
      ["P0", "다중 QR 이미지 디코딩", "신규 기능", "QR 배정 시간 단축, 오타 방지"],
      ["P0", "세션 저장 / 복원 (SQLite)", "안정성", "앱 중단 복구, 이력 기반 보고"],
      ["P1", "업로드 실패 재시도 큐", "안정성", "네트워크 일시 장애 대응"],
      ["P1", "구조화된 서버 응답 (JSON)", "서버 연동", "오류 분기 정확도 향상"],
      ["P2", "측정 이력 조회 화면", "신규 기능", "과거 데이터 검증"],
      ["P2", "한국어/영문 동적 토글", "국제화", "현지 사용자 편의"],
      ["P3", "카메라 기반 실시간 QR 인식", "신규 기능", "외장 스캐너 미보유 현장 대응"],
    ]
  )
);
children.push(Blank());

// 13. 성공 지표
children.push(H1("13. 성공 지표 (Success Metrics)"));
children.push(
  makeTable(
    [3600, 2880, 2880],
    [
      ["지표", "현재 (추정)", "목표 (Phase 4 이후)"],
      ["캐리어 1개당 QR 매칭 시간", "~60초 (12슬롯)", "< 20초"],
      ["QR 매칭 오류율", "미계측", "< 0.5%"],
      ["업로드 1회 성공률", "미계측", "> 99%"],
      ["사용자 만족도 (1~5)", "미계측", "> 4.0"],
      ["일일 처리 캐리어 수 / 사용자", "미계측", "현재 대비 +50%"],
    ]
  )
);
children.push(Blank());

// 14. 리스크
children.push(H1("14. 리스크 및 가정"));
children.push(Bullet("가정: 측정 엔지니어는 외장 바코드 스캐너를 보유·사용한다"));
children.push(Bullet("가정: 서버 API(/chip/login/probe/update/file)의 폼 구조는 안정적으로 유지된다"));
children.push(Bullet("리스크: 서버 UI 개편 시 HTML 파싱(CSRF, 성공 키워드)이 깨질 수 있음"));
children.push(Bullet("리스크: 다중 QR 인식 정확도가 낮으면 사용자가 수동 스캔으로 되돌아갈 수 있음"));
children.push(Bullet("리스크: 로컬 데이터 영속성 추가 시 기존 메모리 기반 코드의 리팩터링 범위가 큼"));

// 15. 부록
children.push(new Paragraph({ children: [new PageBreak()] }));
children.push(H1("15. 부록 (Appendix)"));

children.push(H2("15.1 디렉토리 구조"));
children.push(
  Code(
    "/\n" +
      "├── main.py\n" +
      "├── requirements.txt\n" +
      "└── src/\n" +
      "    ├── core/\n" +
      "    │   ├── models.py           # SlotData, MeasurementSet\n" +
      "    │   ├── atx_parser.py       # ATX 폴더 / Summary.csv 파싱\n" +
      "    │   ├── csv_exporter.py     # CSV 생성 + 이미지 정리\n" +
      "    │   ├── slot_mapper.py      # 슬롯 코드 <-> 그리드 좌표\n" +
      "    │   └── server_uploader.py  # Django 로그인 + multipart 업로드\n" +
      "    └── ui/\n" +
      "        ├── main_window.py      # Mixin 컴포지션 기반 메인 윈도우\n" +
      "        ├── theme.py            # Catppuccin Mocha 색상\n" +
      "        ├── controllers/        # *_mixin.py (UI 빌더, import, QR, export, upload)\n" +
      "        └── widgets/            # QR Input, Slot Grid, Manual Card, Image Viewer 등"
  )
);

children.push(H2("15.2 의존성"));
children.push(
  makeTable(
    [2700, 1620, 5040],
    [
      ["패키지", "버전", "용도"],
      ["PySide6", "≥ 6.6", "Qt6 기반 UI"],
      ["requests", "≥ 2.31", "HTTP (로그인, 업로드)"],
      ["beautifulsoup4", "≥ 4.12", "HTML 파싱 (CSRF 토큰)"],
      ["openpyxl", "≥ 3.1", "엑셀 지원 (현재 미활용)"],
    ]
  )
);
children.push(Blank());

children.push(H2("15.3 참고 경로"));
children.push(Bullet("엔트리: main.py:10-22"));
children.push(Bullet("QR 매칭 로직: src/ui/controllers/qr_match_mixin.py:8-56"));
children.push(Bullet("서버 업로드: src/core/server_uploader.py:39-68"));
children.push(Bullet("CSV 포맷: src/core/csv_exporter.py:14-31"));
children.push(Bullet("데이터 모델: src/core/models.py:6-80"));

// ---- Assemble document ----
const doc = new Document({
  creator: "Levi.beak",
  title: "NX QR Chip Carrier Manager PRD",
  styles: {
    default: {
      document: { run: { font: "Malgun Gothic", size: 22 } },
    },
    paragraphStyles: [
      {
        id: "Heading1",
        name: "Heading 1",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 36, bold: true, font: "Malgun Gothic", color: "1F3864" },
        paragraph: { spacing: { before: 360, after: 240 }, outlineLevel: 0 },
      },
      {
        id: "Heading2",
        name: "Heading 2",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 28, bold: true, font: "Malgun Gothic", color: "2E74B5" },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 },
      },
      {
        id: "Heading3",
        name: "Heading 3",
        basedOn: "Normal",
        next: "Normal",
        quickFormat: true,
        run: { size: 24, bold: true, font: "Malgun Gothic", color: "2E74B5" },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 },
      },
    ],
  },
  numbering: {
    config: [
      {
        reference: "bullets",
        levels: [
          {
            level: 0,
            format: LevelFormat.BULLET,
            text: "•",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
          {
            level: 1,
            format: LevelFormat.BULLET,
            text: "◦",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 1440, hanging: 360 } } },
          },
        ],
      },
      {
        reference: "numbers",
        levels: [
          {
            level: 0,
            format: LevelFormat.DECIMAL,
            text: "%1.",
            alignment: AlignmentType.LEFT,
            style: { paragraph: { indent: { left: 720, hanging: 360 } } },
          },
        ],
      },
    ],
  },
  sections: [
    {
      properties: {
        page: {
          size: { width: 11906, height: 16838 }, // A4
          margin: { top: 1440, right: 1440, bottom: 1440, left: 1440 },
        },
      },
      headers: {
        default: new Header({
          children: [
            new Paragraph({
              alignment: AlignmentType.RIGHT,
              children: [
                new TextRun({
                  text: "NX QR Chip Carrier Manager PRD",
                  font: "Malgun Gothic",
                  size: 18,
                  color: "808080",
                }),
              ],
            }),
          ],
        }),
      },
      footers: {
        default: new Footer({
          children: [
            new Paragraph({
              alignment: AlignmentType.CENTER,
              children: [
                new TextRun({ text: "- ", font: "Malgun Gothic", size: 18 }),
                new TextRun({
                  children: [PageNumber.CURRENT],
                  font: "Malgun Gothic",
                  size: 18,
                }),
                new TextRun({ text: " -", font: "Malgun Gothic", size: 18 }),
              ],
            }),
          ],
        }),
      },
      children,
    },
  ],
});

const outPath = path.join(__dirname, "NX_QR_ChipCarrier_Manager_PRD.docx");
Packer.toBuffer(doc).then((buffer) => {
  fs.writeFileSync(outPath, buffer);
  console.log("Saved:", outPath);
});
