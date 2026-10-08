"""서버 업로드 컨트롤러 — 상태 바 ``● Server`` 칩 + 서버 설정 다이얼로그(로그인) + CSV/이미지 업로드."""
from __future__ import annotations

import csv

from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtWidgets import QDialog, QMessageBox

from src.core.csv_exporter import (
    CSV_EXPORT_QR_ONLY,
    generate_csv_rows,
    upload_image_files,
)
from src.core.qr_code import UPLOAD_QR_VERSION, summarize_qr_versions
from src.core.server_uploader import BASE_URL, ServerUploader, UploadResult
from src.ui.theme import BG2, FG2, GREEN, ORANGE, TEAL

_MODE_LABEL = {"upload": "신규 업로드", "update": "서버 수정(Update)"}

# 세션 상태 → (칩 글자색, 라벨). ServerSettingsDialog.SESSION_STATES 와 동일
_SERVER_STATE_STYLE = {
    "logged_out": (FG2, "미로그인"),
    "logged_in": (GREEN, "로그인됨"),
    "expired": (ORANGE, "세션 만료"),
    "uploading": (TEAL, "업로드 중"),
}


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
        self._server_dialog = None   # 열려 있는 서버 설정 창(상태 갱신 전달용)
        self._update_server_chip("logged_out")

    # ─── 상태 칩 · 서버 설정 창 · 로그인 ───

    def _update_server_chip(self, state: str) -> None:
        """상태 바 ``● Server`` 칩 갱신 (QRReaderMixin._update_reader_chip 과 같은 스타일)."""
        if not hasattr(self, "btn_server_status"):
            return
        color, label = _SERVER_STATE_STYLE.get(state, (FG2, state))
        user = self._uploader.username
        suffix = f" ({user})" if state == "logged_in" and user else ""
        self.btn_server_status.setText(f"● Server {label}{suffix}")
        self.btn_server_status.setStyleSheet(
            f"QPushButton {{ background: transparent; border: 1px solid {BG2}; border-radius: 3px; "
            f"padding: 2px 8px; font-size: 11px; color: {color}; }}"
            f"QPushButton:hover {{ border-color: {color}; }}"
        )
        self.btn_server_status.setToolTip(f"{BASE_URL} — {label}{suffix}\n클릭하면 서버 설정을 엽니다.")
        if self._server_dialog is not None:
            self._server_dialog.set_session_state(state, user)

    def _open_server_settings(self, section: str = "login", close_on_login: bool = False) -> bool:
        """서버 설정 창(모달). 반환값은 닫힌 뒤의 로그인 여부."""
        from src.ui.dialogs.server_settings_dialog import ServerSettingsDialog

        state = "logged_in" if self._uploader.logged_in else "logged_out"
        saved_id = self._settings.get("server_id", "") if hasattr(self, "_settings") else ""
        dlg = ServerSettingsDialog(saved_id, state, self._uploader.username, self,
                                   section=section, close_on_login=close_on_login)
        dlg.login_requested.connect(self._on_login_requested)
        dlg.logout_requested.connect(self._do_logout)
        dlg.session_check_requested.connect(self._on_session_check_requested)
        self._server_dialog = dlg
        try:
            dlg.exec()
        finally:
            self._server_dialog = None
            dlg.deleteLater()
        return self._uploader.logged_in

    def _on_login_requested(self, username: str, password: str) -> None:
        try:
            success = self._uploader.login(username, password)
        except Exception as e:
            self._update_server_chip("logged_out")
            self.logger.error(f"로그인 실패: {e}")
            return
        finally:
            # 비밀번호는 로그인 호출 직후 참조 해제 — 이후 로그/설정에 섞이지 않게
            del password
        if success:
            if hasattr(self, "_settings"):
                self._settings["server_id"] = username
            self.logger.ok(f"서버 로그인 성공: {username}")
            self._update_server_chip("logged_in")
        else:
            self._update_server_chip("logged_out")
            self.logger.error("로그인 실패: 인증 정보를 확인하세요")

    def _on_session_check_requested(self) -> None:
        was_logged_in = self._uploader.logged_in
        alive = self._uploader.is_session_alive()
        if alive:
            self._update_server_chip("logged_in")
            self.logger.ok("서버 세션 유효")
        else:
            self._update_server_chip("expired" if was_logged_in else "logged_out")
            self.logger.warn("서버 세션 없음/만료 — 다시 로그인하세요")

    def _do_logout(self):
        self._uploader.logout()
        self._update_server_chip("logged_out")
        self.logger.info("서버 로그아웃")

    def _ensure_logged_in(self) -> bool:
        """로그인 상태 확인. 안 됐거나 서버 세션이 만료됐으면 서버 설정 창(로그인 섹션)을 띄운다."""
        if self._uploader.logged_in:
            if self._uploader.is_session_alive():
                return True
            self._update_server_chip("expired")
            self.logger.warn("서버 세션 만료 — 다시 로그인하세요")
        return self._open_server_settings(section="login", close_on_login=True)

    def _shutdown_upload(self) -> None:
        """앱 종료 시 서버 세션 종료 (오류 무시)."""
        up = getattr(self, "_uploader", None)
        if up is not None and up.logged_in:
            try:
                up.logout()
            except Exception:
                pass

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

        # QR 버전 게이트 — 현재 서버는 QR 2.0 전용. 2.1 등 다른 버전이 섞이면 차단, 해독 불가는 경고만
        counts, undecodable = summarize_qr_versions(r[0] for r in rows[1:])
        foreign = {v: n for v, n in counts.items() if v != UPLOAD_QR_VERSION}
        if foreign:
            detail = ", ".join(f"QR {v}: {n}건" for v, n in sorted(foreign.items()))
            QMessageBox.warning(
                self,
                "업로드 차단",
                f"현재 서버({BASE_URL})는 QR {UPLOAD_QR_VERSION} 코드만 받습니다.\n"
                f"다른 버전 코드가 포함되어 업로드를 중단합니다 — {detail} "
                f"(QR {UPLOAD_QR_VERSION}: {counts.get(UPLOAD_QR_VERSION, 0)}건)\n\n"
                "QR 2.1 서버(cantilever-info)는 추후 지원 예정입니다. 서버 설정 → 서버 주소 참고.",
            )
            self.logger.error(f"업로드 차단 — QR 버전 불일치: {detail}")
            return
        if undecodable:
            self.logger.warn(f"QR 형식 해독 불가 {undecodable}건 (10자리 16진수 아님) — 그대로 업로드합니다")

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
        self._update_server_chip("uploading")

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
        # 세션 만료로 실패한 경우 칩을 서버 상태와 맞춘다
        self._update_server_chip("logged_in" if self._uploader.logged_in else "expired")

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

            if ms_db_id:
                from src.core.database import update_upload_status
                update_upload_status(
                    self._db_conn,
                    ms_db_id,
                    "failed",
                )
