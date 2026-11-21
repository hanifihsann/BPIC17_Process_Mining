"""Dataset context and application-wide status feedback."""

from PySide6.QtCore import Qt
from PySide6.QtGui import QResizeEvent
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QSizePolicy,
    QStatusBar,
    QWidget,
)

from gui.app_state import ActiveDataset


class ElidedLabel(QLabel):
    """Show the full value in a tooltip without widening the window."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._full_text = ""
        self.setTextFormat(Qt.TextFormat.PlainText)
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)

    def set_message(self, text: str) -> None:
        self._full_text = text
        self.setToolTip(text)
        self.setAccessibleName(text)
        self._update_visible_text()

    def resizeEvent(self, event: QResizeEvent) -> None:
        super().resizeEvent(event)
        self._update_visible_text()

    def _update_visible_text(self) -> None:
        self.setText(
            self.fontMetrics().elidedText(
                self._full_text, Qt.TextElideMode.ElideRight, self.contentsRect().width()
            )
        )


class DatasetBar(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("datasetBar")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(12, 8, 12, 8)
        layout.setSpacing(12)
        caption = QLabel("Dataset aktif")
        caption.setObjectName("datasetCaption")
        self.name_label = ElidedLabel()
        self.name_label.setObjectName("datasetName")
        self.counts_label = QLabel()
        layout.addWidget(caption)
        layout.addWidget(self.name_label, 1)
        layout.addWidget(self.counts_label)
        self.set_dataset(None)

    def set_dataset(self, dataset: ActiveDataset | None) -> None:
        if dataset is None:
            self.name_label.set_message("Belum ada dataset")
            self.counts_label.clear()
            self.counts_label.hide()
            return

        metadata = dataset.metadata
        self.name_label.set_message(metadata["file_name"])
        self.counts_label.setText(
            f"{metadata['case_count']:,} case  /  {metadata['event_count']:,} event"
        )
        self.counts_label.show()


class FeedbackBar(QStatusBar):
    """Show operation status and an indeterminate progress indicator."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setSizeGripEnabled(False)
        self.message_label = ElidedLabel()
        self.message_label.setObjectName("feedback")
        self.message_label.setContentsMargins(12, 3, 4, 3)
        self.progress = QProgressBar()
        self.progress.setAccessibleName("Proses sedang berjalan")
        self.progress.setRange(0, 0)
        self.progress.setTextVisible(False)
        self.progress.setFixedSize(96, 8)
        self.progress.hide()
        self.addWidget(self.message_label, 1)
        self.addPermanentWidget(self.progress)

    def display(self, message: str, tone: str = "info") -> None:
        self.message_label.set_message(message)
        if self.message_label.property("tone") != tone:
            self.message_label.setProperty("tone", tone)
            self.message_label.style().unpolish(self.message_label)
            self.message_label.style().polish(self.message_label)
        self.progress.setVisible(tone == "busy")
