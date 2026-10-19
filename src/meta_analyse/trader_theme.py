"""Accessible, low-glare dark trading workstation palette."""
TRADER_QSS = """
QWidget { background-color: #0C1422; color: #DCE6F4; font-family: 'Segoe UI'; font-size: 12px; }
QTabWidget::pane { border: 1px solid #273449; border-radius: 8px; background: #101B2C; }
QTabBar::tab { background: #131F31; color: #8FA3BD; padding: 11px 20px; border: 1px solid #273449; }
QTabBar::tab:selected { background: #20334B; color: #F3F7FF; border-bottom: 2px solid #44B9D3; }
QPushButton { background: #233B55; border: 1px solid #365572; border-radius: 6px;
              padding: 9px 13px; font-weight: 600; color: #EAF4FF; }
QPushButton:hover { background: #315472; border-color: #55C4DB; }
QPushButton:pressed { background: #152B42; }
QPushButton:disabled { color: #738399; background: #172435; }
QTableWidget { background: #101C2D; alternate-background-color: #16263A;
               gridline-color: #26384C; border: 1px solid #2B4058;
               selection-background-color: #234C67; selection-color: #FFFFFF; }
QHeaderView::section { background: #1B2D42; color: #AFC8DF; padding: 9px;
                       border: 0; border-right: 1px solid #2B4058; font-weight: 600; }
QListWidget { background: #111E2F; border: 1px solid #2B4058; border-radius: 6px; }
QListWidget::item { padding: 7px; }
QListWidget::item:selected { background: #244761; color: white; }
QLabel { background: transparent; }
QDoubleSpinBox { background: #192C42; border: 1px solid #37516A;
                 border-radius: 5px; padding: 5px; color: #EDF5FF; }
QCheckBox { spacing: 8px; }
QToolTip { background: #243B54; color: white; border: 1px solid #4C708B; }
"""
