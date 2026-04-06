---
name: 백그라운드 스레딩 & 데이터 파이프라인
description: QThread Signal/Slot 패턴 — 비차단 데이터 로딩, UI 스레드 안전
version: 1.0
---
# SKILL 13 — 백그라운드 스레딩
## 두 가지 패턴
### QThread (Signal/Slot)
- `DataLoaderThread(QThread)` — `finished = Signal(object, object, float)`
- Signal 자동 마샬링 → 수신 QObject의 스레드에서 Slot 실행
### stdlib Thread (daemon)
- `threading.Thread(target=run, daemon=True)` — PDF 내보내기 등
- `QTimer.singleShot(0, lambda: ...)` → UI 스레드 브리징
## 주의사항
- 워커 스레드에서 **절대** Qt 위젯 직접 접근 금지
- `self._loader_thread` 참조 유지 (GC 방지)
- lambda 캡처 주의: `lambda e=e: ...` (값 캡처)
## 관련 파일
`ui/workers/data_loader_thread.py`, `ui/controllers/scan_controller.py`, `ui/controllers/export_controller.py`
