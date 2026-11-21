"""Visual styles for the shared Qt shell and controls."""

STYLESHEET = """
QMainWindow, QWidget#workspace { background: #f3f6f8; color: #152d3a; }
QFrame#sidebar { background: #182d37; }
QLabel#brand { color: #ffffff; font-size: 23px; font-weight: 700; }
QLabel#brandSubtitle { color: #b7cbd5; font-size: 13px; }
QListWidget#navigation {
    background: transparent; border: none; color: #dce9ef; font-size: 14px;
    outline: none;
}
QListWidget#navigation::item { padding: 10px 8px; border-left: 3px solid transparent; }
QListWidget#navigation::item:hover { background: #213e4c; }
QListWidget#navigation::item:selected {
    background: #264b5d; color: white; border-left: 3px solid #85d0ea;
}
QListWidget#navigation:focus { border: 1px solid #85d0ea; }
QLabel#pageTitle { color: #152d3a; font-size: 24px; font-weight: 700; }
QFrame#datasetBar, QFrame#surface, QScrollArea#importScroll {
    background: white; border: 1px solid #dfe7ec; border-radius: 6px;
}
QLabel#datasetCaption { color: #49616e; font-weight: 600; }
QLabel#datasetName { color: #152d3a; }
QLabel#sectionTitle { color: #152d3a; font-size: 17px; font-weight: 600; }
QLabel#helpText { color: #49616e; }
QWidget#importOverviewPage { background: white; }
QWidget#importOverviewPage QGroupBox {
    margin-top: 10px; padding-top: 5px; border: 1px solid #dfe7ec; border-radius: 4px;
}
QWidget#importOverviewPage QGroupBox::title { subcontrol-origin: margin; left: 9px; }
QPushButton#primaryAction, QWidget#importOverviewPage QPushButton {
    background: #1c617e; color: white; border: 1px solid #1c617e;
    border-radius: 4px; padding: 6px 12px;
}
QPushButton#primaryAction:hover, QWidget#importOverviewPage QPushButton:hover {
    background: #174f67;
}
QPushButton#primaryAction:focus, QWidget#importOverviewPage QPushButton:focus {
    border: 1px solid #87cbe4;
}
QPushButton#primaryAction:disabled, QWidget#importOverviewPage QPushButton:disabled {
    background: #e1e9ed; color: #526771; border-color: #e1e9ed;
}
QStatusBar { background: white; border-top: 1px solid #dfe7ec; }
QLabel#feedback { color: #49616e; }
QLabel#feedback[tone="busy"] { color: #1c617e; }
QLabel#feedback[tone="success"] { color: #236043; }
QLabel#feedback[tone="error"] { color: #a3262c; }
QProgressBar { border: 1px solid #bdcfd8; border-radius: 4px; }
QProgressBar::chunk { background: #1c617e; }
"""
