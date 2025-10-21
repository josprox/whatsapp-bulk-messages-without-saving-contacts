# view.py
import sys
import os
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QWidget, QVBoxLayout,
    QLabel, QLineEdit, QTextEdit, QMessageBox, QProgressBar,
    QHBoxLayout, QFileDialog, QApplication, QScrollArea
)
from PySide6.QtCore import Qt, Signal, Slot

class MainView(QMainWindow):
    """
    Vista: Define la interfaz gráfica y emite señales en interacciones del usuario.
    """
    # Señales emitidas por la vista hacia el controlador
    load_file_clicked = Signal()
    start_clicked = Signal()
    stop_clicked = Signal()
    confirm_login_clicked = Signal()
    template_text_changed = Signal(str) # Emite el nuevo texto de la plantilla

    def __init__(self):
        super().__init__()
        self.setWindowTitle("WhatsApp Bulk Sender (MVC)")
        self.setGeometry(100, 100, 700, 700)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # --- Sección 1: Carga de Archivo ---
        self.btn_load_file = QPushButton("Cargar Archivo de Destinatarios (.txt o .csv)")
        self.btn_load_file.clicked.connect(self.load_file_clicked) # Conecta a la señal
        self.lbl_file_path = QLabel("Archivo no cargado.")
        self.layout.addWidget(self.btn_load_file)
        self.layout.addWidget(self.lbl_file_path)

        # --- Sección 2: Variables Estáticas ---
        self.static_vars_inputs = {}
        static_vars_layout = QVBoxLayout()
        static_vars_layout.addWidget(QLabel("Variables Estáticas:"))
        static_vars_to_add = ["minombre", "miempresa"]
        for var_name in static_vars_to_add:
            hbox = QHBoxLayout(); label = QLabel(f"{var_name}:"); line_edit = QLineEdit()
            self.static_vars_inputs[var_name] = line_edit
            hbox.addWidget(label); hbox.addWidget(line_edit); static_vars_layout.addLayout(hbox)
        self.layout.addLayout(static_vars_layout)

        # --- Sección 3: Plantilla del Mensaje ---
        self.layout.addWidget(QLabel("Plantilla del Mensaje (usa {nombre_variable}):"))
        self.txt_template = QTextEdit()
        self.txt_template.setPlaceholderText("Ej: Hola {nombre}, de {miempresa}...")
        self.txt_template.setMinimumHeight(100)
        # Conecta textChanged a un lambda que emite la señal template_text_changed
        self.txt_template.textChanged.connect(lambda: self.template_text_changed.emit(self.txt_template.toPlainText()))
        self.layout.addWidget(self.txt_template)

        self.lbl_expected_format = QLabel("Formato esperado del archivo: numero;<variables_dinámicas>;")
        self.lbl_expected_format.setStyleSheet("font-style: italic; color: grey;")
        self.layout.addWidget(self.lbl_expected_format)

        # --- Sección 4: Controles ---
        self.lbl_login_status = QLabel("Listo para iniciar.")
        self.lbl_login_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_login_status)

        self.btn_confirm_login = QPushButton("Ya Escaneé QR y Cargaron Chats, Continuar Envío")
        self.btn_confirm_login.clicked.connect(self.confirm_login_clicked) # Conecta a la señal
        self.btn_confirm_login.setVisible(False)
        self.layout.addWidget(self.btn_confirm_login)

        self.btn_start = QPushButton("Iniciar Proceso y Abrir WhatsApp Web")
        self.btn_start.clicked.connect(self.start_clicked) # Conecta a la señal
        self.btn_stop = QPushButton("Detener Envío")
        self.btn_stop.clicked.connect(self.stop_clicked) # Conecta a la señal
        self.btn_stop.setEnabled(False)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.btn_start)
        buttons_layout.addWidget(self.btn_stop)
        self.layout.addLayout(buttons_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)

        # --- Sección 5: Log ---
        self.layout.addWidget(QLabel("Log:"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(150)
        scroll = QScrollArea(); scroll.setWidget(self.log_area); scroll.setWidgetResizable(True)
        self.layout.addWidget(scroll)

    # --- Métodos para obtener datos de la GUI (llamados por el Controlador) ---
    def get_template_text(self):
        return self.txt_template.toPlainText()

    def get_static_vars(self):
        return {name: input_widget.text().strip() for name, input_widget in self.static_vars_inputs.items()}

    # --- Slots para actualizar la GUI (llamados por el Controlador) ---
    @Slot(str)
    def set_file_label(self, text):
        self.lbl_file_path.setText(f"Archivo: {text}")

    @Slot(str)
    def set_expected_format_label(self, text):
        self.lbl_expected_format.setText(f"Formato esperado: {text}")

    @Slot(str)
    def update_log(self, message):
        self.log_area.append(message)
        scrollbar = self.log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    @Slot(int)
    def set_progress(self, value):
        self.progress_bar.setValue(value)

    @Slot(str)
    def set_status_label(self, text):
        self.lbl_login_status.setText(text)

    @Slot(bool)
    def show_confirm_button(self, show):
        self.btn_confirm_login.setVisible(show)
        self.btn_confirm_login.setEnabled(show) # Habilitar solo si se muestra

    @Slot(bool)
    def enable_start_button(self, enabled):
        self.btn_start.setEnabled(enabled)

    @Slot(bool)
    def enable_stop_button(self, enabled):
        self.btn_stop.setEnabled(enabled)

    @Slot(str, str)
    def show_warning(self, title, message):
        QMessageBox.warning(self, title, message)

    # --- Manejo de cierre (el Controlador podría conectarse a esto si necesita lógica extra) ---
    # close_signal = Signal() # Opcional: señal si el controlador necesita saber del cierre
    # def closeEvent(self, event):
    #     self.close_signal.emit()
    #     super().closeEvent(event) # Llama al comportamiento por defecto