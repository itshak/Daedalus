"""Explicit, reusable multi-account selection for read-only/batch workflows.

Selection never changes game account enablement or grants mutation consent.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QScrollArea, QVBoxLayout, QWidget
from qfluentwidgets import BodyLabel, CaptionLabel, CheckBox, SubtitleLabel

from daedalus.desktop.design_system import METRICS


class AccountSelectionDialog(QDialog):
    """Select a bounded group of configured accounts, never their credentials."""

    def __init__(
        self, accounts: list[dict[str, object]], selected: list[str], parent=None,
        *, title: str = "Choose accounts", max_accounts: int | None = None,
        explanation: str | None = None,
    ):
        super().__init__(parent)
        self.setWindowTitle(title)
        self.resize(410, 500)
        self.setMinimumSize(340, 330)
        # A silent list cutoff would make "All accounts" dishonest. The
        # surrounding view decides whether an action needs a smaller safety
        # limit (for example, mutating batch dispatch).
        self._accounts = [
            dict(row) for row in accounts
            if isinstance(row.get("id"), str) and row["id"]
        ]
        if max_accounts is not None and len(self._accounts) > max_accounts:
            raise ValueError(
                f"Account picker has {len(self._accounts)} entries, "
                f"exceeding its declared limit of {max_accounts}"
            )
        selected_ids = set(selected)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(METRICS.xl, METRICS.lg, METRICS.xl, METRICS.lg)
        outer.setSpacing(METRICS.md)
        outer.addWidget(SubtitleLabel(title))
        note = CaptionLabel(
            explanation or
            "Select accounts to include in this action. Account permissions "
            "and any required confirmation are checked independently."
        )
        note.setWordWrap(True)
        outer.addWidget(note)

        self.all_checkbox = CheckBox("Select all")
        self.all_checkbox.setAccessibleName("Select all accounts")
        outer.addWidget(self.all_checkbox)
        self.all_checkbox.stateChanged.connect(self._select_all)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        holder = QWidget()
        entries = QVBoxLayout(holder)
        entries.setContentsMargins(0, 0, METRICS.md, 0)
        entries.setSpacing(METRICS.sm)
        self.checkboxes: dict[str, CheckBox] = {}
        for row in self._accounts:
            aid = str(row["id"])
            label = str(row.get("label") or row.get("player") or aid)
            world = str(row.get("world") or "")
            checkbox = CheckBox(f"{label}  ·  {world}" if world else label)
            checkbox.setChecked(aid in selected_ids)
            checkbox.setAccessibleName(f"Include {label} in selected accounts")
            checkbox.stateChanged.connect(self._update_count)
            self.checkboxes[aid] = checkbox
            entries.addWidget(checkbox)
        entries.addStretch(1)
        scroll.setWidget(holder)
        outer.addWidget(scroll, 1)
        self.count = BodyLabel()
        outer.addWidget(self.count)

        actions = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        actions.button(QDialogButtonBox.Ok).setText("Use selected accounts")
        actions.accepted.connect(self._accept_nonempty)
        actions.rejected.connect(self.reject)
        outer.addWidget(actions)
        self._update_count()

    def _select_all(self, state: int) -> None:
        checked = state == Qt.Checked.value
        for checkbox in self.checkboxes.values():
            checkbox.blockSignals(True)
            checkbox.setChecked(checked)
            checkbox.blockSignals(False)
        self._update_count()

    def _update_count(self, *_args: object) -> None:
        number = len(self.selected_ids())
        self.count.setText(f"{number} of {len(self.checkboxes)} accounts selected")
        self.all_checkbox.blockSignals(True)
        self.all_checkbox.setChecked(
            len(self.checkboxes) > 0 and number == len(self.checkboxes)
        )
        self.all_checkbox.blockSignals(False)

    def _accept_nonempty(self) -> None:
        if self.selected_ids():
            self.accept()
        else:
            self.count.setText("Choose at least one account.")

    def selected_ids(self) -> list[str]:
        return [aid for aid, checkbox in self.checkboxes.items() if checkbox.isChecked()]
