# view.py
import sys
import os
import platform
import subprocess
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QWidget, QVBoxLayout,
    QLabel, QLineEdit, QTextEdit, QMessageBox, QProgressBar,
    QHBoxLayout, QFileDialog, QApplication, QScrollArea,
    # --- Añadidos para Pestañas y Visor ---
    QTabWidget, QTableView, QComboBox, QHeaderView
)
from PySide6.QtCore import Qt, Signal, Slot
from PySide6.QtGui import QStandardItemModel # Importar para el slot

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

    # --- Nuevas Señales para el Visor de Logs ---
    refresh_logs_list_clicked = Signal()
    log_file_selected = Signal(str) # Emite la RUTA COMPLETA del archivo
    # --- Fin de Nuevas Señales ---

    def __init__(self):
        super().__init__()
        self.setWindowTitle("AuraSend - Joss Dev")
        self.setGeometry(100, 100, 700, 750) # Ventana un poco más alta

        # --- Contenedor Principal: Pestañas ---
        self.tab_widget = QTabWidget()
        self.setCentralWidget(self.tab_widget)
        
        # --- Pestaña 1: Envío (Interfaz principal) ---
        self.main_tab = QWidget()
        self.tab_widget.addTab(self.main_tab, "Envío")
        self.main_layout = QVBoxLayout(self.main_tab) # Layout para la pestaña 1

        # --- Pestaña 2: Visor de Logs ---
        self.logs_tab = QWidget()
        self.tab_widget.addTab(self.logs_tab, "Visor de Logs de Errores")
        self.logs_layout = QVBoxLayout(self.logs_tab) # Layout para la pestaña 2

        # =======================================================
        # --- Contenido de la Pestaña 1 (Envío) ---
        # =======================================================

        # --- Sección 1: Carga de Archivo ---
        self.btn_load_file = QPushButton("Cargar Archivo de Destinatarios (.txt o .csv)")
        self.btn_load_file.clicked.connect(self.load_file_clicked) # Conecta a la señal
        self.lbl_file_path = QLabel("Archivo no cargado.")
        self.main_layout.addWidget(self.btn_load_file)
        self.main_layout.addWidget(self.lbl_file_path)

        # --- Sección 2: Variables Estáticas ---
        self.static_vars_inputs = {}
        static_vars_layout = QVBoxLayout()
        static_vars_layout.addWidget(QLabel("Variables Estáticas (Opcionales):"))
        static_vars_to_add = ["minombre", "miempresa"]
        for var_name in static_vars_to_add:
            hbox = QHBoxLayout(); label = QLabel(f"{var_name}:"); line_edit = QLineEdit()
            self.static_vars_inputs[var_name] = line_edit
            hbox.addWidget(label); hbox.addWidget(line_edit); static_vars_layout.addLayout(hbox)
        self.main_layout.addLayout(static_vars_layout)

        # --- Sección 3: Plantilla del Mensaje ---
        self.main_layout.addWidget(QLabel("Plantilla del Mensaje (usa {nombre_variable}):"))
        self.txt_template = QTextEdit()
        self.txt_template.setPlaceholderText("Ej: Hola {nombre}, de {miempresa}...")
        self.txt_template.setMinimumHeight(100)
        self.txt_template.textChanged.connect(lambda: self.template_text_changed.emit(self.txt_template.toPlainText()))
        self.main_layout.addWidget(self.txt_template)

        self.lbl_expected_format = QLabel("Formato esperado del archivo: numero;<variables_dinámicas>;")
        self.lbl_expected_format.setStyleSheet("font-style: italic; color: grey;")
        self.main_layout.addWidget(self.lbl_expected_format)

        # --- Sección 4: Controles ---
        self.lbl_login_status = QLabel("Listo para iniciar.")
        self.lbl_login_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.main_layout.addWidget(self.lbl_login_status)

        self.btn_confirm_login = QPushButton("Ya Escaneé QR y Cargaron Chats, Continuar Envío")
        self.btn_confirm_login.clicked.connect(self.confirm_login_clicked) # Conecta a la señal
        self.btn_confirm_login.setVisible(False)
        self.main_layout.addWidget(self.btn_confirm_login)

        self.btn_start = QPushButton("Iniciar Proceso y Abrir WhatsApp Web")
        self.btn_start.clicked.connect(self.start_clicked) # Conecta a la señal
        self.btn_stop = QPushButton("Detener Envío")
        self.btn_stop.clicked.connect(self.stop_clicked) # Conecta a la señal
        self.btn_stop.setEnabled(False)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.btn_start)
        buttons_layout.addWidget(self.btn_stop)
        self.main_layout.addLayout(buttons_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.main_layout.addWidget(self.progress_bar)

        # --- Sección 5: Log (en vivo) ---
        self.main_layout.addWidget(QLabel("Log (En vivo):"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(150)
        scroll = QScrollArea(); scroll.setWidget(self.log_area); scroll.setWidgetResizable(True)
        self.main_layout.addWidget(scroll)

        # =======================================================
        # --- Contenido de la Pestaña 2 (Visor de Logs) ---
        # =======================================================

        # --- Layout de controles del visor ---
        logs_controls_layout = QHBoxLayout()
        logs_controls_layout.addWidget(QLabel("Seleccionar Archivo de Log:"))
        
        self.logs_combo_box = QComboBox()
        self.logs_combo_box.setPlaceholderText("Carga la lista primero...")
        # Conectar la señal de selección
        self.logs_combo_box.activated.connect(self._on_log_selected) # Usamos activated
        
        self.btn_refresh_logs = QPushButton("Refrescar Lista")
        self.btn_refresh_logs.clicked.connect(self.refresh_logs_list_clicked) # Conectar señal
        
        logs_controls_layout.addWidget(self.logs_combo_box, 1) # Darle más espacio al combo
        logs_controls_layout.addWidget(self.btn_refresh_logs)
        
        self.logs_layout.addLayout(logs_controls_layout)

        # --- Tabla del visor ---
        self.log_table_view = QTableView()
        self.log_table_view.setSortingEnabled(True)
        self.log_table_view.setAlternatingRowColors(True)
        self.log_table_view.setEditTriggers(QTableView.EditTrigger.NoEditTriggers) # Solo lectura
        self.logs_layout.addWidget(self.log_table_view)


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
        """Actualiza el LOG DE VIVO en la pestaña 1."""
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

    # --- Nuevos Slots para el Visor de Logs ---

    @Slot()
    def _on_log_selected(self):
        """Slot interno para manejar la selección del combobox."""
        full_path = self.logs_combo_box.currentData() # Obtenemos la ruta completa
        if full_path:
            self.log_file_selected.emit(full_path) # Emitimos la ruta

    @Slot(list)
    def update_log_files_list(self, files_list: list):
        """Actualiza el QComboBox con la lista de archivos de log encontrados."""
        self.logs_combo_box.blockSignals(True) # Evitar emitir señales mientras limpiamos
        current_data = self.logs_combo_box.currentData()
        
        self.logs_combo_box.clear()
        self.logs_combo_box.setPlaceholderText("Seleccione un archivo...")
        
        if not files_list:
            self.logs_combo_box.setPlaceholderText("No se encontraron logs.")
            self.logs_combo_box.blockSignals(False)
            return

        new_index_to_select = 0
        for i, full_path in enumerate(files_list):
            # Añadimos el nombre base, pero guardamos la ruta completa
            basename = os.path.basename(full_path)
            self.logs_combo_box.addItem(basename, userData=full_path)
            if full_path == current_data:
                new_index_to_select = i
                
        self.logs_combo_box.setCurrentIndex(new_index_to_select)
        self.logs_combo_box.blockSignals(False)

    @Slot(QStandardItemModel)
    def set_log_table_model(self, model):
        """Recibe el modelo de datos y lo asigna a la tabla en la Pestaña 2."""
        self.log_table_view.setModel(model)
        self.log_table_view.resizeColumnsToContents()
        self.log_table_view.horizontalHeader().setStretchLastSection(True)

    @Slot()
    def switch_to_logs_tab(self):
        """Cambia programáticamente a la pestaña del visor de logs."""
        self.tab_widget.setCurrentWidget(self.logs_tab)