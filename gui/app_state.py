"""Shared dataset and results for the current desktop session."""

from dataclasses import dataclass
from typing import Any

from PySide6.QtCore import QObject, Signal


@dataclass(frozen=True, eq=False, slots=True)
class ActiveDataset:
    """References to the objects returned by the import panel."""

    log: Any
    metadata: dict[str, Any]
    overview: dict[str, Any]


class AppState(QObject):
    """Update the active dataset and results on the GUI thread."""

    dataset_changed = Signal(object)
    result_changed = Signal(str)

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._dataset: ActiveDataset | None = None
        self._results: dict[str, Any] = {}

    @property
    def dataset(self) -> ActiveDataset | None:
        return self._dataset

    def activate(self, dataset: ActiveDataset) -> None:
        """Replace the dataset and invalidate its previous results together."""
        previous_pages = tuple(self._results)
        self._results.clear()
        self._dataset = dataset
        self.dataset_changed.emit(dataset)
        for page_key in previous_pages:
            self.result_changed.emit(page_key)

    def has_result(self, page_key: str) -> bool:
        return page_key in self._results

    def result(self, page_key: str) -> Any:
        return self._results.get(page_key)

    def save_result(self, dataset: ActiveDataset, page_key: str, result: Any) -> bool:
        """Publish a result only when it belongs to the current import."""
        if dataset is not self._dataset:
            return False
        self._results[page_key] = result
        self.result_changed.emit(page_key)
        return True

    def clear_result(self, page_key: str) -> None:
        if page_key in self._results:
            del self._results[page_key]
            self.result_changed.emit(page_key)
