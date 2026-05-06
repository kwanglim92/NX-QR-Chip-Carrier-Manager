"""ATX slot edit dialog."""
from __future__ import annotations

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from src.core.models import SlotData, truncate_measurement_value
from src.core.slot_mapper import format_full_label


class SlotEditDialog(QDialog):
    """Edit a single ATX slot without mutating the original SlotData."""

    def __init__(self, slot: SlotData, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Slot")
        self.setModal(True)

        self._slot_index = slot.slot_index
        self._slot_code = slot.slot_code
        self._drive = slot.drive
        self._image_path = slot.image_path

        outer = QVBoxLayout(self)
        form = QFormLayout()

        try:
            slot_label = format_full_label(slot.slot_code)
        except (ValueError, IndexError):
            slot_label = f"#{slot.slot_index + 1}"

        self.slot_label = QLabel(slot_label)
        form.addRow("Slot:", self.slot_label)

        self.probe_input = QLineEdit(slot.probe_type or "")
        form.addRow("Probe Type:", self.probe_input)

        self.freq_input = QSpinBox()
        self.freq_input.setRange(0, 999999)
        self.freq_input.setSpecialValueText(" ")
        self.freq_input.setValue(truncate_measurement_value(slot.frequency) or 0)
        form.addRow("Frequency (KHz):", self.freq_input)

        self.q_input = QSpinBox()
        self.q_input.setRange(0, 999999)
        self.q_input.setSpecialValueText(" ")
        self.q_input.setValue(truncate_measurement_value(slot.q_factor) or 0)
        form.addRow("Q:", self.q_input)

        self.qr_input = QLineEdit(slot.qr_id or "")
        form.addRow("QR ID:", self.qr_input)

        self.source_combo = QComboBox()
        self.source_combo.addItem("ATX Summary", "summary_csv")
        self.source_combo.addItem("Manual", "manual_entry")
        source_idx = self.source_combo.findData(slot.source or "summary_csv")
        self.source_combo.setCurrentIndex(source_idx if source_idx >= 0 else 0)
        form.addRow("Source:", self.source_combo)

        outer.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

    def result_data(self) -> SlotData:
        """Return an edited copy of the slot data."""
        freq = truncate_measurement_value(self.freq_input.value())
        q_factor = truncate_measurement_value(self.q_input.value())

        return SlotData(
            slot_index=self._slot_index,
            slot_code=self._slot_code,
            frequency=freq if freq is not None and freq > 0 else None,
            drive=self._drive,
            q_factor=q_factor if q_factor is not None and q_factor > 0 else None,
            qr_id=self.qr_input.text().strip() or None,
            image_path=self._image_path,
            source=self.source_combo.currentData() or "summary_csv",
            probe_type=self.probe_input.text().strip() or None,
        )

    def focus_qr_input(self) -> None:
        self.qr_input.setFocus()
        self.qr_input.selectAll()
