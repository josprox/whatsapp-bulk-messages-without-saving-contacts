# main.py
import sys
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import Qt

# Importar componentes MVC
from model import SenderModel
from view import MainView
from controller import AppController

if __name__ == "__main__":
    # Configuraciones de DPI (opcional pero recomendado)
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)

    # Crear instancias MVC
    model = SenderModel()
    view = MainView()
    controller = AppController(model=model, view=view)

    # Mostrar la vista y ejecutar la aplicación
    view.show()
    sys.exit(app.exec())