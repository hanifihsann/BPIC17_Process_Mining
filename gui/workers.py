"""Run one feature operation away from the Qt GUI thread."""

import logging
from collections.abc import Callable
from typing import Any

from PySide6.QtCore import QObject, QThread


LOGGER = logging.getLogger(__name__)


class TaskThread(QThread):
    """Expose the operation outcome after QThread emits finished."""

    def __init__(
        self, operation: Callable[[], Any], description: str, parent: QObject
    ) -> None:
        super().__init__(parent)
        self._operation = operation
        self._description = description
        self.result: Any = None
        self.error: str | None = None

    def run(self) -> None:
        try:
            self.result = self._operation()
        except Exception as error:
            LOGGER.exception("Operasi gagal: %s", self._description)
            self.error = str(error).strip() or type(error).__name__
