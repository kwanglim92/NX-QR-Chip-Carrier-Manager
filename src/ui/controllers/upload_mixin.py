"""서버 업로드 컨트롤러 — 로그인 + CSV/이미지 업로드."""
from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QThread, Signal, QObject
from PySide6.QtWidgets import QMessageBox

from src.core.server_uploader import ServerUploader, UploadResult


class _UploadWorker(QObject):
    """백그라운드 업로드 스레드."""
    finished = Signal(UploadResult)
    progress = Signal(str)  # 상태 메시지

    def __init__(self, uploader: ServerUploader, csv_path: str,
                 image_paths: list[str] | None, mode: str):
        super().__init__()
        self._uploader = uploader
        self._csv_path = csv_path
        self._image_paths = image_paths
        self._mode = mode

    def run(self):
        self.progress.emit("업로드 중...")
        result = self._uploader.upload(self._csv_path, self._image_paths, self._mode)
        self.finished.emit(result)


class UploadMixin:
    def _init_upload_state(self):
        self._uploader = ServerUploader()
        self._upload_thread: QThread | None = None

    # ─── 로그인 ───

    def _do_login(self):
        username = self.upload_id_input.text().strip()
        password = self.upload_pw_input.text().strip()

        if not username or not password:
            self.logger.warn("ID와 비밀번호를 입력하세요")
            return

        self.btn_login.setEnabled(False)
        self.upload_status_label.setText("Logging in...")
        self.upload_status_label.setStyleSheet("color: #fab387;")

        try:
            success = self._uploader.login(username, password)
            if success:
                self._update_login_status(True)
                self.logger.ok(f"서버 로그인 성공: {username}")
            else:
                self._update_login_status(False)
                self.logger.error("로그인 실패: 인증 정보를 확인하세요")
        except Exception as e:
            self._update_login_status(False)
            self.logger.error(f"로그인 실패: {e}")
        finally:
            self.btn_login.setEnabled(True)

    def _do_logout(self):
        self._uploader.logout()
        self._update_login_status(False)
        self.logger.info("서버 로그아웃")

    def _update_login_status(self, logged_in: bool):
        if logged_in:
            self.upload_status_label.setText(f"● Connected ({self._uploader.username})")
            self.upload_status_label.setStyleSheet("color: #a6e3a1;")
            self.btn_login.setText("Logout")
            self.btn_login.clicked.disconnect()
            self.btn_login.clicked.connect(self._do_logout)
            self.btn_upload_csv.setEnabled(True)
            self.btn_upload_all.setEnabled(True)
        else:
            self.upload_status_label.setText("○ Disconnected")
            self.upload_status_label.setStyleSheet("color: #a6adc8;")
            self.btn_login.setText("Login")
            self.btn_login.clicked.disconnect()
            self.btn_login.clicked.connect(self._do_login)
            self.btn_upload_csv.setEnabled(False)
            self.btn_upload_all.setEnabled(False)

    # ─── 업로드 ───

    def _upload_csv_only(self):
        self._start_upload(with_images=False)

    def _upload_csv_with_images(self):
        self._start_upload(with_images=True)

    def _start_upload(self, with_images: bool):
        if not self._uploader.logged_in:
            self.logger.warn("서버에 로그인하세요")
            return

        if not self.measurement_set:
            self.logger.warn("내보낼 데이터가 없습니다")
            return

        # 완성도 체크
        incomplete = [s for s in self.measurement_set.slots if not s.is_complete]
        if incomplete:
            reply = QMessageBox.question(
                self,
                "미완성 데이터",
                f"{len(incomplete)}개 슬롯의 데이터가 불완전합니다.\n"
                "QR ID가 있는 슬롯만 업로드하시겠습니까?",
                QMessageBox.Yes | QMessageBox.No,
            )
            if reply != QMessageBox.Yes:
                return

        # 임시 CSV 생성
        from src.core.csv_exporter import export_csv, generate_csv_rows
        import tempfile, os

        rows = generate_csv_rows(self.measurement_set)
        if len(rows) <= 1:
            self.logger.warn("업로드할 데이터가 없습니다 (QR ID가 매칭된 슬롯 없음)")
            return

        tmp_csv = tempfile.NamedTemporaryFile(
            mode="w", suffix=".csv", delete=False, encoding="utf-8-sig"
        )
        for row in rows:
            tmp_csv.write(",".join(row) + "\n")
        tmp_csv.close()
        csv_path = tmp_csv.name

        # 이미지 경로 수집
        image_paths = None
        if with_images:
            image_paths = []
            for slot in self.measurement_set.slots:
                if slot.qr_id and slot.image_path:
                    p = Path(slot.image_path)
                    if p.exists():
                        image_paths.append(str(p))

        # 업로드 모드 선택
        mode = "upload"

        # 백그라운드 스레드로 업로드
        self._upload_thread = QThread()
        self._upload_worker = _UploadWorker(
            self._uploader, csv_path, image_paths, mode
        )
        self._upload_worker.moveToThread(self._upload_thread)

        self._upload_thread.started.connect(self._upload_worker.run)
        self._upload_worker.progress.connect(self._on_upload_progress)
        self._upload_worker.finished.connect(
            lambda result: self._on_upload_finished(result, csv_path)
        )
        self._upload_worker.finished.connect(self._upload_thread.quit)

        # UI 비활성화
        self.btn_upload_csv.setEnabled(False)
        self.btn_upload_all.setEnabled(False)
        self.upload_progress.setVisible(True)
        self.upload_progress.setRange(0, 0)  # indeterminate

        self._upload_thread.start()

    def _on_upload_progress(self, message: str):
        self.logger.info(message)

    def _on_upload_finished(self, result: UploadResult, csv_path: str):
        # 임시 CSV 삭제
        import os
        try:
            os.unlink(csv_path)
        except OSError:
            pass

        # UI 복원
        self.upload_progress.setVisible(False)
        if self._uploader.logged_in:
            self.btn_upload_csv.setEnabled(True)
            self.btn_upload_all.setEnabled(True)

        if result.success:
            msg = f"업로드 성공: CSV"
            if result.image_count > 0:
                msg += f" + 이미지 {result.image_count}개"
            msg += f"\n서버 응답: {result.message}"
            self.logger.ok(msg)
            self._statusbar.showMessage("서버 업로드 완료")
        else:
            self.logger.error(f"업로드 실패: {result.message}")
            self._statusbar.showMessage("서버 업로드 실패")
