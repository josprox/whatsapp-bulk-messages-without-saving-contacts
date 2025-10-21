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
    ask_login = Signal() # Señal para pedir al usuario que inicie sesión

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
        """Inicia el proceso: lee archivo, abre navegador, pide login."""
        try:
            self.log_message.emit("Leyendo archivo de datos...")
            try:
                df = pandas.read_csv(
                    self.file_path,
                    sep=';',
                    header=None,
                    names=self.expected_columns,
                    dtype=str,
                    skip_blank_lines=True,
                    encoding='utf-8' # Especificar UTF-8
                )
                 # Eliminar filas donde *todas* las columnas esperadas son NaN/vacías
                df.dropna(subset=self.expected_columns, how='all', inplace=True)
                # Llenar cualquier NaN restante (celdas vacías individuales) con string vacío
                df.fillna("", inplace=True)


                if df.empty or df['numero'].eq('').all(): # Revisar si 'numero' está vacío en todas las filas restantes
                     raise ValueError(f"El archivo está vacío o la columna 'numero' está vacía después de limpiar. Formato esperado: {';'.join(self.expected_columns)};")

                # Validación de columnas extras (opcional pero útil)
                try:
                    with open(self.file_path, 'r', encoding='utf-8') as f:
                        first_line = f.readline()
                        if first_line:
                            stripped_line = first_line.strip()
                            if stripped_line: # Solo si la línea no está vacía
                                actual_cols = len(stripped_line.split(';'))
                                # Ajuste si la línea termina en ';'
                                if stripped_line.endswith(';'):
                                    actual_cols -= 1

                                if actual_cols > len(self.expected_columns):
                                    self.log_message.emit(f"Advertencia: Archivo parece tener {actual_cols} columnas, pero se esperaban {len(self.expected_columns)} ({';'.join(self.expected_columns)};). Se ignorarán columnas extras.")
                                elif actual_cols < len(self.expected_columns):
                                     self.log_message.emit(f"Advertencia: Archivo parece tener solo {actual_cols} columnas, se esperaban {len(self.expected_columns)} ({';'.join(self.expected_columns)};). Faltarán datos.")
                except Exception as file_read_warn_e:
                     self.log_message.emit(f"Advertencia: No se pudo verificar el número exacto de columnas en el archivo: {file_read_warn_e}")


                recipients = df.to_dict('records')

            except ValueError as ve:
                 self.log_message.emit(f"Error al procesar archivo: {ve}")
                 self.log_message.emit(f"Formato esperado: {';'.join(self.expected_columns)}; Separador: ';'")
                 self.finished.emit()
                 return
            except FileNotFoundError:
                 self.log_message.emit(f"Error: No se encontró el archivo {self.file_path}")
                 self.finished.emit()
                 return
            except Exception as e:
                self.log_message.emit(f"Error inesperado al leer archivo: {e}")
                self.log_message.emit(traceback.format_exc())
                self.log_message.emit(f"Verifica formato: {';'.join(self.expected_columns)}; Separador: ';'")
                self.finished.emit()
                return

            total_messages = len(recipients)
            if total_messages == 0:
                self.log_message.emit("No se encontraron destinatarios válidos en el archivo.")
                self.finished.emit()
                return
            self.log_message.emit(f"Se enviarán {total_messages} mensajes.")

            # --- Inicio del navegador ---
            self.log_message.emit("Iniciando navegador Chrome...")
            try:
                # Intenta instalar/actualizar chromedriver
                try:
                    driver_path = ChromeDriverManager().install()
                    service = Service(driver_path)
                    self.log_message.emit(f"ChromeDriver listo en: {driver_path}")
                except Exception as driver_e:
                     self.log_message.emit(f"Error al obtener/instalar ChromeDriver: {driver_e}")
                     self.log_message.emit("Asegúrate de tener conexión a internet. Intentando continuar...")
                     # Si falla, intenta iniciar Chrome directamente (puede que ya esté en PATH)
                     service = Service()


                options = webdriver.ChromeOptions()
                # user_data_dir = os.path.join(os.path.expanduser("~"), ".whatsapp_selenium_session")
                # options.add_argument(f"user-data-dir={user_data_dir}")
                self.driver = webdriver.Chrome(service=service, options=options)
                self.driver.get('https://web.whatsapp.com')
            except Exception as e:
                self.log_message.emit(f"Error al iniciar Chrome: {e}")
                self.log_message.emit(traceback.format_exc())
                self.log_message.emit("Asegúrate de tener Google Chrome instalado.")
                self.finished.emit()
                return

            self.log_message.emit("Navegador abierto. Escanea el código QR y presiona ENTER en la consola cuando tus chats sean visibles.")
            self.ask_login.emit()

        except Exception as e:
            self.log_message.emit(f"Error fatal en inicialización: {e}")
            self.log_message.emit(traceback.format_exc())
            self.finished.emit()
            return

    @Slot() # <--- FIX: Añadir decorador @Slot()
    def continue_sending(self):
        """Continúa el envío después de que el usuario confirma el login."""
        if not self.driver:
            self.log_message.emit("Error: El navegador no está inicializado.")
            self.finished.emit()
            return

        try:
            # Re-leer por si acaso, usando las columnas correctas
            try:
                df = pandas.read_csv(self.file_path, sep=';', header=None, names=self.expected_columns, dtype=str, skip_blank_lines=True, encoding='utf-8')
                df.dropna(subset=self.expected_columns, how='all', inplace=True)
                df.fillna("", inplace=True)
                recipients = df.to_dict('records')
                total_messages = len(recipients)
                if total_messages == 0:
                     self.log_message.emit("No se encontraron destinatarios válidos para enviar.")
                     self.finished.emit()
                     return
            except Exception as e:
                 self.log_message.emit(f"Error al releer el archivo antes de enviar: {e}")
                 self.finished.emit()
                 return


            count_sent = 0
            count_failed = 0
            for i, recipient in enumerate(recipients):
                if not self.is_running:
                    self.log_message.emit("Proceso cancelado por el usuario.")
                    break

                current_vars = self.static_vars.copy()
                numero_dest = str(recipient.get('numero', '')).strip()
                variable_display_name = numero_dest
                missing_dynamic_vars = []

                for col_name in self.dynamic_file_columns:
                    value = recipient.get(col_name) # Puede ser None si la columna no existe o está vacía
                    value_str = str(value).strip() if value is not None else ""
                    current_vars[col_name] = value_str
                    if not value_str and value is None: # Solo si era None
                        missing_dynamic_vars.append(col_name)
                    if col_name.lower() == 'nombre' and value_str:
                       variable_display_name = f"{numero_dest} ({value_str})"

                if missing_dynamic_vars:
                    self.log_message.emit(f"Advertencia: Faltan datos para '{variable_display_name}' en columnas: {', '.join(missing_dynamic_vars)}. Usando valores vacíos.")

                message = self.template_message
                try:
                    message = message.format_map(current_vars)
                    encoded_message = quote(message)
                except Exception as e:
                     self.log_message.emit(f"Error al formatear mensaje para {variable_display_name}: {e}. Saltando...")
                     count_failed += 1
                     self.progress.emit(int(((i + 1) / total_messages) * 100))
                     continue

                if not numero_dest or not numero_dest.isdigit():
                    self.log_message.emit(f"Error: Número '{numero_dest}' inválido en línea {i+1}. Saltando...")
                    count_failed += 1
                    self.progress.emit(int(((i + 1) / total_messages) * 100))
                    continue

                self.log_message.emit(f"[{i+1}/{total_messages}] Intentando enviar a {variable_display_name}...")

                # --- Envío con Selenium ---
                message_sent_successfully = False
                try:
                    url = f'https://web.whatsapp.com/send?phone={numero_dest}&text={encoded_message}'
                    self.driver.get(url)

                    # Esperar a que el campo de texto del chat esté presente (indica que la URL cargó)
                    chat_input_xpath = "//div[@contenteditable='true'][@data-tab='10'] | //div[@contenteditable='true'][@data-tab='1']" # XPaths comunes para el input
                    try:
                        WebDriverWait(self.driver, 20).until(
                             EC.presence_of_element_located((By.XPATH, chat_input_xpath))
                        )
                        self.log_message.emit("... Chat cargado, buscando botón de enviar...")
                    except TimeoutException:
                         # Intentar verificar si es número inválido ANTES de buscar el botón
                         try:
                            invalid_number_xpath = "//div[contains(@data-testid, 'popup-controls-ok')]" # Botón OK en popup de "número inválido"
                            # Espera corta para el popup
                            WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, invalid_number_xpath)))
                            self.log_message.emit(f"Error: Número {numero_dest} es inválido o no tiene WhatsApp (detectado por popup).")
                            # Intentar cerrar el popup para continuar
                            try:
                                self.driver.find_element(By.XPATH, invalid_number_xpath).click()
                                sleep(1)
                            except: pass # Si no se puede cerrar, no importa mucho
                         except TimeoutException:
                            self.log_message.emit(f"Error: No se cargó la ventana de chat para {numero_dest} en 20 segundos. ¿Número correcto? ¿Conexión lenta?")
                         count_failed += 1
                         self.progress.emit(int(((i + 1) / total_messages) * 100))
                         continue # Saltar al siguiente número


                    # Ahora busca el botón de enviar
                    try:
                        xpath_send_button = "//button[@aria-label='Enviar'] | //span[@data-icon='send']/ancestor::button | //div[@role='button'][.//span[@data-icon='wds-ic-send-filled']]"
                        click_btn = WebDriverWait(self.driver, 40).until( # Espera un poco más por el botón
                            EC.element_to_be_clickable((By.XPATH, xpath_send_button))
                        )
                        sleep(random.uniform(1.5, 3.0)) # Pausa antes de clic
                        click_btn.click()
                        sleep(random.uniform(4.0, 7.0)) # Espera después de clic
                        self.log_message.emit(f"Mensaje enviado a: {variable_display_name}")
                        count_sent += 1
                        message_sent_successfully = True
                    except TimeoutException:
                         self.log_message.emit(f"Error: No se encontró o no se pudo hacer clic en el botón de enviar para {variable_display_name} después de cargar el chat.")
                    except Exception as send_e:
                        self.log_message.emit(f"Error inesperado al intentar hacer clic en enviar para {variable_display_name}: {send_e}")


                except Exception as e:
                    self.log_message.emit(f"Fallo grave al procesar {variable_display_name}: {e}")
                    self.log_message.emit(traceback.format_exc())

                if not message_sent_successfully:
                    count_failed += 1

                self.progress.emit(int(((i + 1) / total_messages) * 100))
                # Pausa aleatoria entre mensajes para parecer más humano
                sleep_time = random.uniform(2.5, 5.5)
                self.log_message.emit(f"...pausando por {sleep_time:.1f} segs...")
                sleep(sleep_time)


            self.log_message.emit(f"Proceso completado. Enviados: {count_sent}, Fallidos/Saltados: {count_failed} de {total_messages} destinatarios.")

        except Exception as e:
            self.log_message.emit(f"Error crítico durante el proceso de envío masivo: {e}")
            self.log_message.emit(traceback.format_exc())
        finally:
            if self.driver:
                try:
                    self.driver.quit()
                    self.log_message.emit("Navegador cerrado.")
                except Exception as e:
                    self.log_message.emit(f"No se pudo cerrar el navegador automáticamente: {e}")
            self.finished.emit()

    @Slot() # Marcar como Slot
    def stop(self):
        """Marca el worker para detenerse."""
        self.is_running = False
        self.log_message.emit("Solicitando cancelación...")


# --- Aplicación Principal (GUI) ---
class App(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("WhatsApp Bulk Sender")
        self.setGeometry(100, 100, 700, 650) # Ancho x Alto

        self.central_widget = QWidget()
        self.setCentralWidget(self.central_widget)
        self.layout = QVBoxLayout(self.central_widget)

        # --- Sección 1: Carga de Archivo ---
        self.file_path = ""
        self.btn_load_file = QPushButton("Cargar Archivo de Destinatarios (.txt o .csv)")
        self.btn_load_file.clicked.connect(self.load_file)
        self.lbl_file_path = QLabel("Archivo no cargado.")
        self.layout.addWidget(self.btn_load_file)
        self.layout.addWidget(self.lbl_file_path)

        # --- Sección 2: Variables Estáticas ---
        self.static_vars_inputs = {}
        static_vars_layout = QVBoxLayout()
        static_vars_layout.addWidget(QLabel("Variables Estáticas:"))
        # Define aquí las variables estáticas que SIEMPRE usarás
        static_vars_to_add = ["minombre", "miempresa"]
        for var_name in static_vars_to_add:
            hbox = QHBoxLayout()
            label = QLabel(f"{var_name}:")
            line_edit = QLineEdit()
            self.static_vars_inputs[var_name] = line_edit
            hbox.addWidget(label)
            hbox.addWidget(line_edit)
            static_vars_layout.addLayout(hbox)
        self.layout.addLayout(static_vars_layout)

        # --- Sección 3: Plantilla del Mensaje ---
        self.layout.addWidget(QLabel("Plantilla del Mensaje (usa {nombre_variable}):"))
        self.txt_template = QTextEdit()
        self.txt_template.setPlaceholderText("Ej: Hola {nombre}, de {miempresa}. Recordatorio: {concepto}. Saludos, {minombre}.")
        self.txt_template.setMinimumHeight(100)
        # Conectar cambio de texto para actualizar etiqueta de formato
        self.txt_template.textChanged.connect(self.update_expected_format_label)
        self.layout.addWidget(self.txt_template)

        # Etiqueta que muestra el formato esperado del archivo (se actualiza dinámicamente)
        self.lbl_expected_format = QLabel("Formato esperado del archivo: numero;<variables_dinámicas>;")
        self.lbl_expected_format.setStyleSheet("font-style: italic; color: grey;")
        self.layout.addWidget(self.lbl_expected_format)

        # --- Sección 4: Controles y Progreso ---
        self.btn_start = QPushButton("Iniciar Envío")
        self.btn_start.clicked.connect(self.start_sending)
        self.btn_stop = QPushButton("Detener Envío")
        self.btn_stop.clicked.connect(self.stop_sending)
        self.btn_stop.setEnabled(False) # Deshabilitado al inicio

        buttons_layout = QHBoxLayout()
        buttons_layout.addWidget(self.btn_start)
        buttons_layout.addWidget(self.btn_stop)
        self.layout.addLayout(buttons_layout)

        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.layout.addWidget(self.progress_bar)

        # --- Sección 5: Log de Mensajes ---
        self.layout.addWidget(QLabel("Log:"))
        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setMinimumHeight(150)
        # Añadir scroll al área de log
        scroll = QScrollArea()
        scroll.setWidget(self.log_area)
        scroll.setWidgetResizable(True)
        self.layout.addWidget(scroll)

        # --- Manejo de Hilos y Worker ---
        self.thread = None
        self.worker = None

        # Inicializar la etiqueta de formato
        self.update_expected_format_label()

    def load_file(self):
        """Abre un diálogo para seleccionar el archivo de destinatarios."""
        file_dialog = QFileDialog(self)
        # Permitir txt y csv
        file_dialog.setNameFilter("Archivos de datos (*.txt *.csv)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if file_dialog.exec():
            filenames = file_dialog.selectedFiles()
            if filenames:
                self.file_path = filenames[0]
                self.lbl_file_path.setText(f"Archivo: {os.path.basename(self.file_path)}")
                self.log(f"Archivo cargado: {self.file_path}")
                # Validar lectura básica al cargar
                try:
                     # Intenta leer solo las primeras filas para verificar formato rápido
                     df_test = pandas.read_csv(self.file_path, sep=';', header=None, dtype=str, nrows=5, encoding='utf-8')
                     if df_test.empty:
                          self.log("Advertencia: El archivo parece estar vacío.")
                     else:
                          self.log("Archivo leído exitosamente (verificación inicial).")
                except Exception as e:
                     QMessageBox.warning(self, "Error al leer archivo", f"No se pudo leer el archivo correctamente. Verifica que esté separado por ';' y codificado en UTF-8.\n\nError: {e}")
                     self.file_path = ""
                     self.lbl_file_path.setText("Archivo no cargado.")

            else: # Si el usuario cancela
                self.file_path = ""
                self.lbl_file_path.setText("Archivo no cargado.")

    def update_expected_format_label(self):
        """Analiza la plantilla y actualiza la etiqueta del formato esperado."""
        template = self.txt_template.toPlainText()
        static_var_names = list(self.static_vars_inputs.keys())

        # Encontrar todas las variables {variable} usando expresión regular
        placeholders = re.findall(r'\{(\w+)\}', template)

        # Filtrar para obtener solo las dinámicas (no estáticas, no 'numero')
        # Ordenarlas alfabéticamente para consistencia en la etiqueta
        dynamic_file_columns = sorted(list(set(
            var for var in placeholders if var != 'numero' and var not in static_var_names
        )))

        # Construir el string del formato esperado: numero;var1;var2;...;
        format_str = "numero;" + ";".join(dynamic_file_columns) + ";"
        self.lbl_expected_format.setText(f"Formato esperado del archivo: {format_str}")

    def start_sending(self):
        """Valida entradas e inicia el worker en un hilo separado."""
        # --- Validaciones Previas ---
        if not self.file_path or not os.path.exists(self.file_path):
            QMessageBox.warning(self, "Archivo Requerido", "Por favor, carga un archivo de destinatarios válido.")
            return

        template = self.txt_template.toPlainText().strip()
        if not template:
            QMessageBox.warning(self, "Plantilla Requerida", "Por favor, escribe la plantilla del mensaje.")
            return

        static_vars = {}
        static_var_names = list(self.static_vars_inputs.keys())
        all_inputs_filled = True
        for name, input_widget in self.static_vars_inputs.items():
            value = input_widget.text().strip()
            # Ahora SÍ requerimos que las estáticas tengan valor
            if not value:
                # Marcar como no lleno, pero continuar recolectando para mostrar todos los errores
                all_inputs_filled = False
                # Podrías resaltar el campo vacío aquí si quieres: input_widget.setStyleSheet("border: 1px solid red;")
            static_vars[name] = value

        if not all_inputs_filled:
            QMessageBox.warning(self, "Variables Estáticas Requeridas", "Por favor, completa todas las variables estáticas.")
            return
        # else: # Resetear estilos si estaban marcados
             # for input_widget in self.static_vars_inputs.values():
                 # input_widget.setStyleSheet("")


        # --- Detección de columnas dinámicas ---
        placeholders = re.findall(r'\{(\w+)\}', template)
        dynamic_file_columns = sorted(list(set(
            var for var in placeholders if var != 'numero' and var not in static_var_names
        )))
        expected_columns = ['numero'] + dynamic_file_columns
        # -------------------------------------

        # Validar que todas las variables usadas en la plantilla existan
        all_available_vars = set(static_var_names + dynamic_file_columns + ['numero'])
        missing_vars = [p for p in placeholders if p not in all_available_vars]
        if missing_vars:
             QMessageBox.warning(self, "Error en Plantilla", f"Variable(s) no definida(s): {', '.join(missing_vars)}. Asegúrate que estén en Variables Estáticas o que no sean typo.")
             return

        # Intenta formatear con valores de prueba para detectar errores de formato {variable} vs {{literal}}
        try:
             test_vars = {k: f"[{k}]" for k in all_available_vars}
             # Usar format_map para ser más tolerante a variables no usadas
             template.format_map(test_vars)
        except Exception as e:
             QMessageBox.warning(self, "Error en Formato de Plantilla", f"Revisa la plantilla, podría haber llaves incompletas o mal usadas: {e}")
             return

        # --- Iniciar Worker ---
        self.log("--- Iniciando Proceso ---")
        self.log(f"Variables estáticas: {static_vars}")
        self.log(f"Variables dinámicas esperadas del archivo: {dynamic_file_columns}")
        self.log(f"Formato de archivo esperado: {';'.join(expected_columns)};")

        self.progress_bar.setValue(0)
        self.btn_start.setEnabled(False)
        self.btn_stop.setEnabled(True)
        self.log_area.clear() # Limpiar log anterior

        # Crear y mover worker a un hilo
        self.thread = QThread()
        self.worker = Worker(self.file_path, static_vars, template, dynamic_file_columns)
        self.worker.moveToThread(self.thread)

        # Conectar señales del worker a slots de la GUI
        self.thread.started.connect(self.worker.run)
        self.worker.finished.connect(self.on_worker_finished)
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.log_message.connect(self.log)
        self.worker.ask_login.connect(self.prompt_login_confirmation)

        self.thread.start()

    @Slot()
    def prompt_login_confirmation(self):
         """ Pide al usuario confirmación en la consola después de abrir el navegador. """
         try:
            print("\n" + "="*40)
            print("  INTERACCIÓN REQUERIDA EN LA CONSOLA")
            print("="*40)
            # Usar try-except para manejar posible cierre de consola inesperado
            try:
                input(" > Navegador abierto. Escanea el código QR,\n > espera a que carguen tus chats y luego\n > PRESIONA ENTER AQUÍ para continuar el envío...")
            except EOFError:
                 self.log("Error: La entrada de la consola se cerró inesperadamente. Deteniendo.")
                 # Si la consola se cierra, no podemos continuar
                 if self.worker:
                     # Intentar detener el worker desde este hilo (puede ser riesgoso)
                     QMetaObject.invokeMethod(self.worker, "stop", Qt.QueuedConnection)
                 return # No continuar

            print("="*40 + "\n")
            self.log("Inicio de sesión confirmado por el usuario. Continuando envío...")

            if self.worker:
                 # Invocar continue_sending en el hilo del worker
                 QMetaObject.invokeMethod(self.worker, "continue_sending", Qt.QueuedConnection)
            else:
                 self.log("Error: El worker ya no existe al intentar continuar.")
                 self.on_worker_finished() # Limpiar GUI

         except Exception as e:
             self.log(f"Error durante la confirmación de login: {e}")
             self.log(traceback.format_exc())
             # Si hay error aquí, intentamos detener limpiamente
             if self.worker:
                 QMetaObject.invokeMethod(self.worker, "stop", Qt.QueuedConnection)


    @Slot() # Marcar como Slot por si se llama desde otro hilo
    def stop_sending(self):
        """Solicita al worker que se detenga."""
        self.log("Botón Detener presionado.")
        if self.worker:
            # Usar invokeMethod para llamar a stop() en el hilo del worker
             QMetaObject.invokeMethod(self.worker, "stop", Qt.QueuedConnection)
        self.btn_stop.setEnabled(False) # Deshabilitar para evitar clics repetidos

    @Slot()
    def on_worker_finished(self):
        """Limpia el hilo y worker cuando el proceso termina."""
        self.log("--- Señal 'finished' recibida ---")
        self.btn_start.setEnabled(True)
        self.btn_stop.setEnabled(False)

        # Asegurarse que el hilo termine antes de borrar referencias
        if self.thread:
            if self.thread.isRunning():
                self.log("Esperando que el hilo termine...")
                self.thread.quit()
                if not self.thread.wait(5000): # Espera 5 segs
                    self.log("Advertencia: El hilo no terminó limpiamente tras 5s. Forzando.")
                    self.thread.terminate()
                    self.thread.wait() # Espera a la terminación forzada
                else:
                    self.log("Hilo terminado correctamente.")
            else:
                 self.log("El hilo ya no estaba corriendo.")

        self.thread = None
        self.worker = None
        self.log("Recursos del hilo limpiados.")


    # Hacer log un Slot para poder llamarlo desde otros hilos si fuera necesario
    @Slot(str)
    def log(self, message):
        """Añade un mensaje al área de log de la GUI."""
        self.log_area.append(message)
        # Mueve el scroll al final para ver los últimos mensajes
        scrollbar = self.log_area.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())

    def closeEvent(self, event):
        """Asegura que el hilo se detenga si se cierra la ventana."""
        if self.thread and self.thread.isRunning():
            reply = QMessageBox.question(self, 'Proceso en Ejecución',
                                       "El envío de mensajes está en curso. ¿Estás seguro de que quieres salir? El proceso se detendrá.",
                                       QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                       QMessageBox.StandardButton.No)

            if reply == QMessageBox.StandardButton.Yes:
                self.log("Cerrando ventana, intentando detener proceso...")
                # Llamar a stop_sending que ahora usa invokeMethod
                self.stop_sending()
                # Esperar un poco para que el worker procese la señal de stop
                sleep(1)
                # La limpieza final se hará en on_worker_finished cuando el worker emita finished
                event.accept()
            else:
                event.ignore() # Ignora el evento de cierre
        else:
            event.accept() # Acepta el cierre si no hay hilo corriendo


# --- Punto de Entrada Principal ---
if __name__ == "__main__":
    # Configuración adicional recomendada para algunas versiones/entornos
    if hasattr(Qt, 'AA_EnableHighDpiScaling'):
        QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    if hasattr(Qt, 'AA_UseHighDpiPixmaps'):
        QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    window = App()
    window.show()
    sys.exit(app.exec())