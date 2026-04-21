"""서버 로그인 다이얼로그."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit,
    QDialogButtonBox, QLabel,
)

from src.ui.theme import BG, BG2, BG3, FG, FG2


class LoginDialog(QDialog):
    def __init__(self, parent=None, saved_id: str = ""):
        super().__init__(parent)
        self.setWindowTitle("Server Login")
        self.setFixedWidth(320)

        layout = QVBoxLayout(self)

        form = QFormLayout()
        self.id_input = QLineEdit()
        self.id_input.setPlaceholderText("Server ID")
        if saved_id:
            self.id_input.setText(saved_id)
        form.addRow("ID:", self.id_input)

        self.pw_input = QLineEdit()
        self.pw_input.setEchoMode(QLineEdit.Password)
        self.pw_input.setPlaceholderText("Password")
        form.addRow("PW:", self.pw_input)

        layout.addLayout(form)

        self.status_label = QLabel("")
        self.status_label.setStyleSheet(f"color: {FG2};")
        layout.addWidget(self.status_label)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.button(QDialogButtonBox.Ok).setText("Login")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # 포커스: ID 있으면 PW로, 없으면 ID로
        if saved_id:
            self.pw_input.setFocus()
        else:
            self.id_input.setFocus()

    def get_credentials(self) -> tuple[str, str] | None:
        """다이얼로그 실행 후 (id, pw) 반환. 취소 시 None."""
        if self.exec() == QDialog.Accepted:
            uid = self.id_input.text().strip()
            pwd = self.pw_input.text().strip()
            if uid and pwd:
                return uid, pwd
        return None
