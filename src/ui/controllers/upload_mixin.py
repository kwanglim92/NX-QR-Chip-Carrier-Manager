"""서버 업로드 컨트롤러 — 로그인 다이얼로그 + CSV/이미지 업로드."""
from __future__ import annotations

import csv

from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from src.core.csv_exporter import (
    CSV_EXPORT_QR_ONLY,
    generate_csv_rows,
    upload_image_files,
)
from src.core.server_uploader import ServerUploader, UploadResult
from src.ui.theme import FG2, GREEN
from src.ui.widgets.login_dialog import LoginDialog

_MODE_LABEL = {"upload": "신규 업로드", "update": "서버 수정(Update)"}


class _UploadWorker(QObject):
    """백그라운드 업로드 스레드."""
    finished = Signal(UploadResult)
    progress = Signal(str)

    def __init__(self, uploader: ServerUploader, csv_path: str,
                 image_files: list[tuple[str, str]] | None, mode: str):
        super().__init__()
        self._uploader = uploader
        self._csv_path = csv_path
        self._image_files = image_files
        self._mode = mode

    def run(self):
        self.progress.emit(f"{_MODE_LABEL.get(self._mode, self._mode)} 중...")
        result = self._uploader.upload(self._csv_path, self._image_files, self._mode)
        self.finished.emit(result)


class UploadMixin:
    def _init_upload_state(self):
        self._uploader = ServerUploader()
        self._upload_thread: QThread | None = None
        self._upload_worker: _UploadWorker | None = None

    # ─── 로그인 ───

    def _do_login(self):
        """로그인 다이얼로그 팝업."""
        if self._uploader.logged_in:
            self._do_logout()
            return

        saved_id = self._settings.get("server_id", "") if hasattr(self, "_settings") else ""
        dlg = LoginDialog(self, saved_id=saved_id)
        creds = dlg.get_credentials()
        if not creds:
            return

        username, password = creds

        try:
            success = self._uploader.login(username, password)
            # 비밀번호는 로그인 호출 직후 참조 해제 — 이후 로그/설정에 섞이지 않게
            del password, creds
            if success:
                self._update_login_status(True)
                # 서버 ID 설정에 저장
                if hasattr(self, "_settings"):
                    self._settings["server_id"] = username
                self.logger.ok(f"서버 로그인 성공: {username}")
            else:
                self._update_login_status(False)
                self.logger.error("로그인 실패: 인증 정보를 확인하세요")
        except Exception as e:
            self._update_login_status(False)
            self.logger.error(f"로그인 실패: {e}")

    def _do_logout(self):
        self._uploader.logout()
        self._update_login_status(False)
        self.logger.info("서버 로그아웃")

    def _update_login_status(self, logged_in: bool):
        if logged_in:
            self.lbl_server_status.setText(f"● Connected ({self._uploader.username})")
            self.lbl_server_status.setStyleSheet(f"color: {GREEN};")
            self.btn_server_toggle.setText("Logout")
        else:
            self.lbl_server_status.setText("○ Disconnected")
            self.lbl_server_status.setStyleSheet(f"color: {FG2};")
            self.btn_server_toggle.setText("Login")

    def _ensure_logged_in(self) -> bool:
        """로그인 상태 확인. 안 됐거나 서버 세션이 만료됐으면 로그인 다이얼로그 자동 팝업."""
        if self._uploader.logged_in:
            if self._uploader.is_session_alive():
                return True
            self._update_login_status(False)
            self.logger.warn("서버 세션 만료 — 다시 로그인하세요")
        self._do_login()
        return self._uploader.logged_in

    # ─── 업로드 ───

    def _upload_csv_only(self):
        if self._ensure_logged_in():
            self._start_upload(with_images=False)

    def _upload_csv_with_images(self):
        if self._ensure_logged_in():
            self._start_upload(with_images=True)

    def _update_csv_only(self):
        if self._ensure_logged_in():
            self._start_upload(with_images=False, mode="update")

    def _update_csv_with_images(self):
        if self._ensure_logged_in():
            self._start_upload(with_images=True, mode="update")

    def _confirm_update_mode(self, row_count: int) -> bool:
        """Update(서버 수정)는 기존 서버 데이터를 덮어쓰므로 실행 전 확인."""
        reply = QMessageBox.warning(
            self,
            "서버 데이터 수정",
            f"서버에 이미 등록된 QR {row_count}건의 데이터를 현재 값으로 덮어씁니다.\n"
            "이 작업은 되돌릴 수 없습니다. 계속할까요?",
            QMessageBox.Yes | QMessageBox.No,
            QMessageBox.No,
        )
        return reply == QMessageBox.Yes

    def _get_upload_measurement_set(self):
        if (
            getattr(self, "current_mode", "") == "export"
            and hasattr(self, "_get_export_measurement_set")
        ):
            return self._get_export_measurement_set()
        return self.measurement_set

    def _merge_upload(self):
        """여러 파트(시리얼)를 묶어 하나의 배치로 업로드 (이미지 포함)."""
        if not self._ensure_logged_in():
            return
        parts = self._manual_parts_summary()
        if not parts:
            self.logger.warn("머지할 Manual 데이터가 없습니다")
            return

        from src.ui.dialogs.merge_export_dialog import MergeExportDialog

        dlg = MergeExportDialog(parts, self)
        if dlg.exec() != QDialog.Accepted:
            return
        merged = self._build_merged_ms(dlg.selected_serials(), dlg.box_serial())
        if not merged.slots:
            self.logger.warn("선택된 파트에 데이터가 없습니다")
            return
        self._start_upload(with_images=True, ms=merged)

    def _start_upload(self, with_images: bool, ms=None, mode: str = "upload"):
        if self._upload_thread is not None and self._upload_thread.isRunning():
            self.logger.warn("업로드가 진행 중입니다. 완료 후 다시 시도하세요.")
            return
        if ms is None:
            ms = self._get_upload_measurement_set()
        if not ms or not ms.slots:
            self.logger.warn("내보낼 데이터가 없습니다")
            return

        policy = self._choose_incomplete_export_policy(
            ms,
            "QR 있는 값만 업로드",
            "전체 슬롯 업로드",
        )
        if policy is None:
            return
        if policy == CSV_EXPORT_QR_ONLY and not any(s.qr_id for s in ms.slots):
            self.logger.warn("업로드할 데이터가 없습니다 (QR ID가 매칭된 슬롯 없음)")
            return

        # 임시 CSV 생성
        import tempfile

        rows = generate_csv_rows(ms, policy)
        if len(rows) <= 1:
            self.logger.warn("업로드할 데이터가 없습니다 (QR ID가 매칭된 슬롯 없음)")
            return

        if mode == "update" and not self._confirm_update_mode(len(rows) - 1):
            self.logger.info("서버 수정(Update) 취소")
            return

        tmp_csv = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig"
        )
        writer = csv.writer(tmp_csv)
        writer.writerows(rows)
        tmp_csv.close()
        csv_path = tmp_csv.name

        # 이미지 수집 — 전송 파일명은 CSV+Images 반출과 동일 규격({QR ID}.png)
        image_files = upload_image_files(ms, policy) if with_images else None

        # 백그라운드 스레드로 업로드
        self._upload_thread = QThread()
        self._upload_worker = _UploadWorker(
            self._uploader, csv_path, image_files, mode
        )
        self._upload_worker.moveToThread(self._upload_thread)

        self._upload_thread.started.connect(self._upload_worker.run)
        self._upload_worker.progress.connect(self._on_upload_progress)
        self._upload_worker.finished.connect(
            lambda result, db_id=ms.db_id: self._on_upload_finished(result, csv_path, db_id)
        )
        self._upload_worker.finished.connect(self._upload_thread.quit)
        # 스레드/워커 수명 정리 — 재진입 시 참조 유실로 인한
        # 'QThread: Destroyed while running' 및 객체 누수 방지
        self._upload_worker.finished.connect(self._upload_worker.deleteLater)
        self._upload_thread.finished.connect(self._upload_thread.deleteLater)

        # UI: 업로드 진행 표시 + 중복 업로드 방지
        self.btn_upload.setEnabled(False)
        self.upload_progress.setVisible(True)
        self.upload_progress.setRange(0, 0)  # indeterminate

        self._upload_thread.start()

    def _on_upload_progress(self, message: str):
        self.logger.info(message)

    def _on_upload_finished(self, result: UploadResult, csv_path: str, ms_db_id: int | None):
        import os
        try:
            os.unlink(csv_path)
        except OSError:
            pass

        self.upload_progress.setVisible(False)
        self.btn_upload.setEnabled(True)
        self._upload_thread = None
        self._upload_worker = None

        mode_label = _MODE_LABEL.get(result.mode, result.mode)
        if result.success:
            msg = f"{mode_label} 성공: CSV"
            if result.image_count > 0:
                msg += f" + 이미지 {result.image_count}개"
            msg += f"\n서버 응답: {result.message}"
            self.logger.ok(msg)
            self._statusbar.showMessage(f"서버 {mode_label} 완료")

            if ms_db_id:
                from src.core.database import update_upload_status
                from datetime import datetime
                update_upload_status(
                    self._db_conn,
                    ms_db_id,
                    "uploaded",
                    datetime.now().isoformat(),
                )
        else:
            self.logger.error(f"{mode_label} 실패: {result.message}")
            self._statusbar.showMessage(f"서버 {mode_label} 실패")
            if not self._uploader.logged_in:
                # 세션 만료로 실패한 경우 UI 상태를 서버 상태와 맞춘다
                self._update_login_status(False)

            if ms_db_id:
                from src.core.database import update_upload_status
                update_upload_status(
                    self._db_conn,
                    ms_db_id,
                    "failed",
                )
