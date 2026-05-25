import sys

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication

from app.config_manager import ConfigManager, save_config
from app.ui.main_window import MainWindow


def _apply_dark_palette(app: QApplication):
    palette = QPalette()
    palette.setColor(QPalette.ColorRole.Window, QColor("#2B2B2B"))
    palette.setColor(QPalette.ColorRole.WindowText, QColor("#CCCCCC"))
    palette.setColor(QPalette.ColorRole.Base, QColor("#1E1E1E"))
    palette.setColor(QPalette.ColorRole.AlternateBase, QColor("#2B2B2B"))
    palette.setColor(QPalette.ColorRole.ToolTipBase, QColor("#3C3F41"))
    palette.setColor(QPalette.ColorRole.ToolTipText, QColor("#CCCCCC"))
    palette.setColor(QPalette.ColorRole.Text, QColor("#CCCCCC"))
    palette.setColor(QPalette.ColorRole.Button, QColor("#3C3F41"))
    palette.setColor(QPalette.ColorRole.ButtonText, QColor("#CCCCCC"))
    palette.setColor(QPalette.ColorRole.BrightText, QColor("#FFFFFF"))
    palette.setColor(QPalette.ColorRole.Link, QColor("#4A90E2"))
    palette.setColor(QPalette.ColorRole.Highlight, QColor("#4A90E2"))
    palette.setColor(QPalette.ColorRole.HighlightedText, QColor("#FFFFFF"))
    # Disabled state
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.Text, QColor("#666666"))
    palette.setColor(QPalette.ColorGroup.Disabled, QPalette.ColorRole.ButtonText, QColor("#666666"))
    app.setPalette(palette)


def main():
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("Prompt Image")
    app.setOrganizationName("prompt_image")
    app.setStyle("Fusion")
    _apply_dark_palette(app)

    ConfigManager.instance()  # load config before any widget

    try:
        window = MainWindow()
        window.show()
        result = app.exec()
    finally:
        save_config()

    sys.exit(result)


if __name__ == "__main__":
    main()
