import sys
import os
import pandas # Para leer el archivo de texto fácilmente
import re # Para encontrar variables en la plantilla
from time import sleep
from urllib.parse import quote # Para codificar el texto del mensaje en la URL
import random # Para pausas aleatorias
import traceback # Para mejor log de errores

# --- Importaciones de PySide6 ---
from PySide6.QtWidgets import (
    QMainWindow, QPushButton, QWidget, QVBoxLayout,
    QLabel, QLineEdit, QTextEdit, QMessageBox, QProgressBar,
    QHBoxLayout, QFileDialog, QApplication, QScrollArea
)
from PySide6.QtCore import Qt, Signal, QObject, QThread, Slot, QMetaObject

# --- Importaciones de Selenium ---
from selenium import webdriver
from selenium.common import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager


# --- Worker para Selenium (se ejecuta en otro hilo) ---
class Worker(QObject):
    finished = Signal()
    progress = Signal(int)
    log_message = Signal(str)
    # ask_login: Señal para indicarle a la GUI que muestre el botón de confirmar
    ask_login = Signal()

    def __init__(self, file_path, static_vars, template_message, dynamic_file_columns):
        super().__init__()
        self.file_path = file_path
        self.static_vars = static_vars
        self.template_message = template_message
        self.dynamic_file_columns = dynamic_file_columns
        self.expected_columns = ['numero'] + self.dynamic_file_columns
        self.is_running = True
        self.driver = None

    @Slot()
    def run(self):
        """Inicia el proceso: lee archivo, abre navegador y emite ask_login."""
        try:
            # --- Lectura y validación del archivo (sin cambios) ---
            self.log_message.emit("Leyendo archivo de datos...")
            try:
                df = pandas.read_csv(
                    self.file_path, sep=';', header=None, names=self.expected_columns,
                    dtype=str, skip_blank_lines=True, encoding='utf-8'
                )
                df.dropna(subset=self.expected_columns, how='all', inplace=True)
                df.fillna("", inplace=True)
                if df.empty or df['numero'].eq('').all():
                     raise ValueError(f"Archivo vacío o columna 'numero' vacía. Formato: {';'.join(self.expected_columns)};")

                # Validación de columnas extras (opcional)
                try:
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        first_line = f.readline()
                        if first_line:
                            stripped_line = first_line.strip()
                            if stripped_line:
                                actual_cols = len(stripped_line.split(';'))
                                if stripped_line.endswith(';'): actual_cols -= 1
                                if actual_cols > len(self.expected_columns): self.log_message.emit(f"Advertencia: Archivo con {actual_cols} columnas, esperadas {len(self.expected_columns)}. Se ignorarán extras.")
                                elif actual_cols < len(self.expected_columns): self.log_message.emit(f"Advertencia: Archivo con {actual_cols} columnas, esperadas {len(self.expected_columns)}. Faltarán datos.")
                except Exception as file_read_warn_e:
                     self.log_message.emit(f"Advertencia al verificar columnas: {file_read_warn_e}")

                recipients = df.to_dict('records')
            except Exception as e:
                self.log_message.emit(f"Error crítico al leer/procesar archivo: {e}")
                self.log_message.emit(traceback.format_exc())
                self.finished.emit()
                return

            total_messages = len(recipients)
            if total_messages == 0:
                self.log_message.emit("No se encontraron destinatarios válidos.")
                self.finished.emit()
                return
            self.log_message.emit(f"Se enviarán {total_messages} mensajes.")

            # --- Inicio del navegador ---
            self.log_message.emit("Iniciando navegador Chrome...")
            try:
                try:
                    driver_path = ChromeDriverManager().install()
                    service = Service(driver_path)
                    self.log_message.emit(f"ChromeDriver listo en: {driver_path}")
                except Exception as driver_e:
                     self.log_message.emit(f"Error al obtener ChromeDriver: {driver_e}. Intentando continuar...")
                     service = Service() # Intenta usar uno en PATH

                options = webdriver.ChromeOptions()
                self.driver = webdriver.Chrome(service=service, options=options)
                self.driver.get('https://web.whatsapp.com')
            except Exception as e:
                self.log_message.emit(f"Error al iniciar Chrome: {e}")
                self.log_message.emit(traceback.format_exc())
                self.finished.emit()
                return

            # --- Emitir señal para que la GUI pida confirmación ---
            self.log_message.emit("Navegador abierto. Escanea el código QR en Chrome.")
            self.ask_login.emit() # <-- La GUI reaccionará a esto

            # El worker esperará aquí hasta que la GUI llame a continue_sending

        except Exception as e:
            self.log_message.emit(f"Error fatal en inicialización: {e}")
            self.log_message.emit(traceback.format_exc())
            if self.driver: # Intenta cerrar si falló después de abrir
                try: self.driver.quit()
                except: pass
            self.finished.emit()
            return

    @Slot()
    def continue_sending(self):
        """Continúa el envío después de que el usuario confirma en la GUI."""
        if not self.driver:
            self.log_message.emit("Error: El navegador no está inicializado para continuar.")
            self.finished.emit()
            return
        if not self.is_running: # Chequeo extra por si se detuvo antes de confirmar
             self.log_message.emit("El proceso fue detenido antes de confirmar el login.")
             self.finished.emit()
             return

        self.log_message.emit("Login confirmado. Iniciando bucle de envío...")
        try:
            # --- Relectura del archivo (sin cambios) ---
            try:
                df = pandas.read_csv(self.file_path, sep=';', header=None, names=self.expected_columns, dtype=str, skip_blank_lines=True, encoding='utf-8')
                df.dropna(subset=self.expected_columns, how='all', inplace=True)
                df.fillna("", inplace=True)
                recipients = df.to_dict('records')
                total_messages = len(recipients)
                if total_messages == 0:
                     self.log_message.emit("No se encontraron destinatarios válidos al re-leer.")
                     self.finished.emit()
                     return
            except Exception as e:
                 self.log_message.emit(f"Error al releer el archivo: {e}")
                 self.finished.emit()
                 return

            count_sent = 0
            count_failed = 0
            # --- Bucle de envío (sin cambios internos, solo el log inicial) ---
            for i, recipient in enumerate(recipients):
                if not self.is_running:
                    self.log_message.emit("Proceso cancelado por el usuario durante el envío.")
                    break

                # Preparar variables (igual que antes)
                current_vars = self.static_vars.copy()
                numero_dest = str(recipient.get('numero', '')).strip()
                variable_display_name = numero_dest
                missing_dynamic_vars = []
                for col_name in self.dynamic_file_columns:
                    value = recipient.get(col_name)
                    value_str = str(value).strip() if value is not None else ""
                    current_vars[col_name] = value_str
                    if not value_str and value is None: missing_dynamic_vars.append(col_name)
                    if col_name.lower() == 'nombre' and value_str: variable_display_name = f"{numero_dest} ({value_str})"
                if missing_dynamic_vars: self.log_message.emit(f"Advertencia: Faltan datos para '{variable_display_name}' en {', '.join(missing_dynamic_vars)}. Usando vacíos.")

                # Formatear mensaje (igual que antes)
                message = self.template_message
                try:
                    message = message.format_map(current_vars)
                    encoded_message = quote(message)
                except Exception as e:
                     self.log_message.emit(f"Error al formatear mensaje para {variable_display_name}: {e}. Saltando...")
                     count_failed += 1; self.progress.emit(int(((i + 1) / total_messages) * 100)); continue

                # Validar número (igual que antes)
                if not numero_dest or not numero_dest.isdigit():
                    self.log_message.emit(f"Error: Número '{numero_dest}' inválido en línea {i+1}. Saltando...")
                    count_failed += 1; self.progress.emit(int(((i + 1) / total_messages) * 100)); continue

                self.log_message.emit(f"[{i+1}/{total_messages}] Intentando enviar a {variable_display_name}...")

                # --- Envío Selenium (igual que antes) ---
                message_sent_successfully = False
                try:
                    url = f'https://web.whatsapp.com/send?phone={numero_dest}&text={encoded_message}'
                    self.driver.get(url)
                    chat_input_xpath = "//div[@contenteditable='true'][@data-tab='10'] | //div[@contenteditable='true'][@data-tab='1']"
                    try:
                        WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, chat_input_xpath)))
                        self.log_message.emit("... Chat cargado, buscando botón enviar...")
                    except TimeoutException:
                         try:
                            invalid_number_xpath = "//div[contains(@data-testid, 'popup-controls-ok')]"
                            WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, invalid_number_xpath)))
                            self.log_message.emit(f"Error: Número {numero_dest} inválido/sin WA (popup).")
                            try: self.driver.find_element(By.XPATH, invalid_number_xpath).click(); sleep(1)
                            except: pass
                         except TimeoutException:
                            self.log_message.emit(f"Error: No cargó chat para {numero_dest} en 20s.")
                         count_failed += 1; self.progress.emit(int(((i + 1) / total_messages) * 100)); continue

                    try:
                        xpath_send_button = "//button[@aria-label='Enviar'] | //span[@data-icon='send']/ancestor::button | //div[@role='button'][.//span[@data-icon='wds-ic-send-filled']]"
                        click_btn = WebDriverWait(self.driver, 40).until(EC.element_to_be_clickable((By.XPATH, xpath_send_button)))
                        sleep(random.uniform(1.5, 3.0))
                        click_btn.click()
                        sleep(random.uniform(4.0, 7.0))
                        self.log_message.emit(f"Mensaje enviado a: {variable_display_name}")
                        count_sent += 1; message_sent_successfully = True
                    except TimeoutException: self.log_message.emit(f"Error: Botón enviar no encontrado/clicable para {variable_display_name}.")
                    except Exception as send_e: self.log_message.emit(f"Error inesperado al enviar a {variable_display_name}: {send_e}")

                except Exception as e:
                    self.log_message.emit(f"Fallo grave procesando {variable_display_name}: {e}")
                    self.log_message.emit(traceback.format_exc())

                if not message_sent_successfully: count_failed += 1
                self.progress.emit(int(((i + 1) / total_messages) * 100))
                sleep_time = random.uniform(2.5, 5.5)
                self.log_message.emit(f"...pausando {sleep_time:.1f}s...")
                sleep(sleep_time)
            # --- Fin del bucle ---

            self.log_message.emit(f"Proceso finalizado. Enviados: {count_sent}, Fallidos/Saltados: {count_failed} de {total_messages}.")

        except Exception as e:
            self.log_message.emit(f"Error crítico durante el envío masivo: {e}")
            self.log_message.emit(traceback.format_exc())
        finally:
            if self.driver:
                try: self.driver.quit(); self.log_message.emit("Navegador cerrado.")
                except Exception as e: self.log_message.emit(f"No se pudo cerrar navegador: {e}")
            self.finished.emit()

    @Slot()
    def stop(self):
        """Marca el worker para detenerse."""
        self.is_running = False
        self.log_message.emit("Solicitando cancelación...")


# --- Aplicación Principal (GUI) ---
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WhatsApp Bulk Sender")
        # Ajustar tamaño si es necesario para el nuevo botón
        self.setGeometry(100, 100, 700, 700)

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # --- Secciones 1, 2, 3 (Carga, Estáticas, Plantilla) sin cambios visuales ---
        # ... (código igual que antes para file_path, btn_load_file, lbl_file_path) ...
        self.file_path = ""
        self.btn_load_file = QPushButton("Cargar Archivo de Destinatarios (.txt o .csv)")
        self.btn_load_file.clicked.connect(self.load_file)
        self.lbl_file_path = QLabel("Archivo no cargado.")
        self.layout.addWidget(self.btn_load_file)
        self.layout.addWidget(self.lbl_file_path)

        # ... (código igual que antes para variables estáticas) ...
        self.static_vars_inputs = {}
        static_vars_layout = QVBoxLayout()
        static_vars_layout.addWidget(QLabel("Variables Estáticas:"))
        static_vars_to_add = ["minombre", "miempresa"]
        for var_name in static_vars_to_add:
            hbox = QHBoxLayout(); label = QLabel(f"{var_name}:"); line_edit = QLineEdit()
            self.static_vars_inputs[var_name] = line_edit
            hbox.addWidget(label); hbox.addWidget(line_edit); static_vars_layout.addLayout(hbox)
        self.layout.addLayout(static_vars_layout)

        # ... (código igual que antes para plantilla y etiqueta de formato) ...
        self.layout.addWidget(QLabel("Plantilla del Mensaje (usa {nombre_variable}):"))
        self.txt_template = QTextEdit()
        self.txt_template.setPlaceholderText("Ej: Hola {nombre}, de {miempresa}...")
        self.txt_template.setMinimumHeight(100)
        self.txt_template.textChanged.connect(self.update_expected_format_label)
        self.layout.addWidget(self.txt_template)
        self.lbl_expected_format = QLabel("Formato esperado del archivo: numero;<variables_dinámicas>;")
        self.lbl_expected_format.setStyleSheet("font-style: italic; color: grey;")
        self.layout.addWidget(self.lbl_expected_format)


        # --- Sección 4: Controles (MODIFICADA) ---
        # Etiqueta de estado para login
        self.lbl_login_status = QLabel("Listo para iniciar.")
        self.lbl_login_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.layout.addWidget(self.lbl_login_status)

        # Botón para confirmar login (inicialmente oculto)
        self.btn_confirm_login = QPushButton("Ya Escaneé QR y Cargaron Chats, Continuar Envío")
        self.btn_confirm_login.clicked.connect(self.on_login_confirmed)
        self.btn_confirm_login.setVisible(False) # <--- Oculto al inicio
        self.layout.addWidget(self.btn_confirm_login)

        # Botones Iniciar/Detener
        self.btn_start = QPushButton("Iniciar Proceso y Abrir WhatsApp Web")
        self.btn_start.clicked.connect(self.start_sending)
        self.btn_stop = QPushButton("Detener Envío")
        self.btn_stop.clicked.connect(self.stop_sending)
        self.btn_stop.setEnabled(False)

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.btn_start)
        buttons_layout.addWidget(self.btn_stop)
        self.layout.addLayout(buttons_layout)

        # Barra de progreso (sin cambios)
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)

        # --- Sección 5: Log (sin cambios visuales) ---
        self.layout.addWidget(QLabel("Log:"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(150)
        scroll = QScrollArea(); scroll.setWidget(self.log_area); scroll.setWidgetResizable(True)
        self.layout.addWidget(scroll)

        # --- Manejo de Hilos (sin cambios) ---
        self.thread = None
        self.worker = None

        self.update_expected_format_label() # Llamada inicial

    # --- Métodos load_file y update_expected_format_label (sin cambios) ---
    def load_file(self):
        # ... (igual que antes) ...
        file_dialog = QFileDialog(self)
        file_dialog.setNameFilter("Archivos de datos (*.txt *.csv)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if file_dialog.exec():
            filenames = file_dialog.selectedFiles()
            if filenames:
                self.file_path = filenames[0]
                self.lbl_file_path.setText(f"Archivo: {os.path.basename(self.file_path)}")
                self.log(f"Archivo cargado: {self.file_path}")
                try:
                     df_test = pandas.read_csv(self.file_path, sep=';', header=None, dtype=str, nrows=5, encoding='utf-8')
                     if df_test.empty: self.log("Advertencia: El archivo parece estar vacío.")
                     else: self.log("Verificación inicial de lectura OK.")
                except Exception as e:
                     QMessageBox.warning(self, "Error al leer", f"No se pudo leer.\nVerifica separador ';' y UTF-8.\n\nError: {e}")
                     self.file_path = ""; self.lbl_file_path.setText("Archivo no cargado.")
            else:
                self.file_path = ""; self.lbl_file_path.setText("Archivo no cargado.")

    def update_expected_format_label(self):
        # ... (igual que antes) ...
        template = self.txt_template.toPlainText(); static_var_names = list(self.static_vars_inputs.keys())
        placeholders = re.findall(r'\{(\w+)\}', template)
        dynamic_file_columns = sorted(list(set(var for var in placeholders if var != 'numero' and var not in static_var_names)))
        format_str = "numero;" + ";".join(dynamic_file_columns) + ";"; self.lbl_expected_format.setText(f"Formato esperado: {format_str}")

    def start_sending(self):
        """Valida y empieza el worker (que abrirá el navegador y esperará)."""
        # --- Validaciones (igual que antes) ---
        if not self.file_path or not os.path.exists(self.file_path):
            QMessageBox.warning(self, "Falta Archivo", "Carga un archivo de destinatarios."); return
        template = self.txt_template.toPlainText().strip()
        if not template:
            QMessageBox.warning(self, "Falta Plantilla", "Escribe el mensaje plantilla."); return
        static_vars = {}; static_var_names = list(self.static_vars_inputs.keys()); all_inputs_filled = True
        for name, input_widget in self.static_vars_inputs.items():
            value = input_widget.text().strip()
            if not value: all_inputs_filled = False
            static_vars[name] = value
        if not all_inputs_filled:
            QMessageBox.warning(self, "Faltan Variables", "Completa todas las variables estáticas."); return
        placeholders = re.findall(r'\{(\w+)\}', template)
        dynamic_file_columns = sorted(list(set(var for var in placeholders if var != 'numero' and var not in static_var_names)))
        expected_columns = ['numero'] + dynamic_file_columns
        all_available_vars = set(static_var_names + dynamic_file_columns + ['numero'])
        missing_vars = [p for p in placeholders if p not in all_available_vars]
        if missing_vars:
             QMessageBox.warning(self, "Error Plantilla", f"Variable(s) no definida(s): {', '.join(missing_vars)}"); return
        try:
             test_vars = {k: f"[{k}]" for k in all_available_vars}
             template.format_map(test_vars)
        except Exception as e:
             QMessageBox.warning(self, "Error Formato Plantilla", f"Revisa llaves en plantilla: {e}"); return

        # --- Iniciar Worker ---
        self.log("--- Iniciando Proceso ---")
        self.log(f"Estáticas: {static_vars}")
        self.log(f"Dinámicas: {dynamic_file_columns}")
        self.log(f"Formato: {';'.join(expected_columns)};")

        self.progress_bar.setValue(0)
        self.btn_start.setEnabled(False) # Deshabilitar mientras corre
        self.btn_stop.setEnabled(True) # Habilitar detener
        self.btn_confirm_login.setVisible(False) # Asegurar que esté oculto
        self.lbl_login_status.setText("Iniciando navegador...")
        self.log_area.clear()

        self.thread = QThread()
        self.worker = Worker(self.file_path, static_vars, template, dynamic_file_columns)
        self.worker.moveToThread(self.thread)

        # Conectar señales
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log_message.connect(self.log)
        # Conectar ask_login a la nueva función que muestra el botón
        self.worker.ask_login.connect(self.show_login_confirmation_ui) # <--- CAMBIO

        self.thread.start()

    # --- NUEVO Slot para manejar la señal ask_login ---
    @Slot()
    def show_login_confirmation_ui(self):
        """Actualiza la GUI para pedir la confirmación del login."""
        self.lbl_login_status.setText("ℹ️ Escanea el QR en Chrome. Cuando carguen tus chats, haz clic abajo:")
        self.btn_confirm_login.setVisible(True) # Mostrar el botón
        self.btn_confirm_login.setEnabled(True) # Habilitarlo
        # Mantenemos Stop habilitado, Start deshabilitado

    # --- NUEVO Slot para el clic del botón de confirmar login ---
    @Slot()
    def on_login_confirmed(self):
        """Llamado cuando el usuario hace clic en el botón de confirmar login."""
        self.log("Botón 'Continuar Envío' presionado.")
        self.btn_confirm_login.setEnabled(False) # Deshabilitar para evitar doble clic
        self.btn_confirm_login.setVisible(False) # Ocultar de nuevo
        self.lbl_login_status.setText("✅ Login confirmado. Iniciando envío...")

        # Llamar a continue_sending en el hilo del worker
        if self.worker:
            QMetaObject.invokeMethod(self.worker, "continue_sending", Qt.QueuedConnection)
        else:
            self.log("Error: No se encontró el worker para continuar.")
            self.on_worker_finished() # Resetear UI

    # --- ELIMINADO el método prompt_login_confirmation ---

    # --- Métodos stop_sending, on_worker_finished, log, closeEvent (sin cambios) ---
    @Slot()
    def stop_sending(self):
        # ... (igual que antes) ...
        self.log("Botón Detener presionado.")
        if self.worker:
             QMetaObject.invokeMethod(self.worker, "stop", Qt.QueuedConnection)
        self.btn_stop.setEnabled(False)

    @Slot()
    def on_worker_finished(self):
        # ... (igual que antes) ...
        self.log("--- Señal 'finished' recibida ---")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)
        self.btn_confirm_login.setVisible(False) # Asegurar que esté oculto al final
        self.lbl_login_status.setText("Proceso terminado. Listo para iniciar de nuevo.")

        if self.thread:
            if self.thread.isRunning():
                self.log("Esperando que el hilo termine...")
                self.thread.quit()
                if not self.thread.wait(5000):
                    self.log("Advertencia: Hilo no terminó limpiamente. Forzando.")
                    self.thread.terminate(); self.thread.wait()
                else: self.log("Hilo terminado.")
            else: self.log("Hilo ya no corría.")
        self.thread = None; self.worker = None
        self.log("Recursos limpiados.")


    @Slot(str)
    def log(self, message):
        # ... (igual que antes) ...
        self.log_area.append(message)
        scrollbar = self.log_area.verticalScrollBar(); scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        # ... (igual que antes) ...
        if self.thread and self.thread.isRunning():
            reply = QMessageBox.question(self, 'Proceso en Ejecución',
                                       "Envío en curso. ¿Salir y detener?",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.log("Cerrando ventana, deteniendo proceso..."); self.stop_sending(); sleep(1)
                event.accept()
            else: event.ignore()
        else: event.accept()

# --- Punto de Entrada Principal (sin cambios) ---
if __name__ == "__main__":
    if hasattr(Qt, 'AA_EnableHighDpiScaling'): QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'): QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    app = QApplication(sys.argv); window = App(); window.show(); sys.exit(app.exec())