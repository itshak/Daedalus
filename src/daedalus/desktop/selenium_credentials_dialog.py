"""Secure first-run Gameforge credential prompt for automatic Selenium login."""
from __future__ import annotations

from PySide6.QtWidgets import QDialog, QFormLayout, QHBoxLayout, QLineEdit, QVBoxLayout
from qfluentwidgets import (
    BodyLabel,
    CaptionLabel,
    CheckBox,
    LineEdit,
    PrimaryPushButton,
    PushButton,
    SubtitleLabel,
)

from daedalus.desktop.selenium_auth import GameforgeCredentials, SeleniumLoginUnavailable


class SeleniumCredentialsDialog(QDialog):
    def __init__(self, *, player: str, world: str, email: str = "", parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set up automatic Gameforge sign-in")
        self.resize(480, 300)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(22, 22, 22, 22)
        layout.setSpacing(12)
        layout.addWidget(SubtitleLabel(f"Automatic login — {player} ({world})"))
        note = CaptionLabel(
            "Enter this Gameforge account once. Selenium signs in with Chrome in "
            "headless mode; a window opens only for a CAPTCHA. Your password "
            "is sealed using macOS Keychain before encrypted server backup."
        )
        note.setWordWrap(True)
        layout.addWidget(note)
        form = QFormLayout()
        self.email_input = LineEdit(self)
        self.email_input.setPlaceholderText("Gameforge email")
        self.email_input.setAccessibleName("Gameforge account email")
        self.email_input.setText(email if isinstance(email, str) else "")
        form.addRow(BodyLabel("Email"), self.email_input)
        self.password_input = LineEdit(self)
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setPlaceholderText("Gameforge password")
        self.password_input.setAccessibleName("Gameforge password")
        form.addRow(BodyLabel("Password"), self.password_input)
        layout.addLayout(form)
        self.remember = CheckBox("Remember securely in Keychain and encrypted server backup")
        self.remember.setChecked(True)
        layout.addWidget(self.remember)
        self.error_label = CaptionLabel("")
        layout.addWidget(self.error_label)
        actions = QHBoxLayout()
        cancel = PushButton("Cancel")
        cancel.clicked.connect(self.reject)
        actions.addWidget(cancel)
        submit = PrimaryPushButton("Sign in headlessly")
        submit.clicked.connect(self._accept)
        actions.addWidget(submit)
        layout.addLayout(actions)

    def _accept(self) -> None:
        try:
            self.credentials()
        except SeleniumLoginUnavailable:
            self.error_label.setText("Enter a valid email and password to continue.")
            return
        self.accept()

    def credentials(self) -> GameforgeCredentials:
        if self.result() != QDialog.Accepted and self.error_label.text():
            raise SeleniumLoginUnavailable("No valid login was entered")
        return GameforgeCredentials(
            self.email_input.text().strip(), self.password_input.text()
        )

    def discard(self) -> None:
        self.email_input.clear()
        self.password_input.clear()
