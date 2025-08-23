from PySide6.QtWidgets import QApplication, QFileDialog
import sys
from src.main_window import MainWindow
from src.main_application import MainApplication

if __name__ == '__main__':
    if len(sys.argv) >= 2:
        window = MainWindow(sys.argv[1])
        window.show()
        sys.exit(MainApplication.app.exec())
    else:
        directory = QFileDialog.getExistingDirectory(caption='Open data folder', options=QFileDialog.ShowDirsOnly)
        window = MainWindow(directory)
    window.show()
    sys.exit(MainApplication.app.exec())
