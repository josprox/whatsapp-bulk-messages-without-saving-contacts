# model.py
import os
import pandas
import re
from time import sleep
from urllib.parse import quote
import random
import traceback

from PySide6.QtCore import QObject, Signal, Slot, QThread, QMetaObject, Qt

from selenium import webdriver
from selenium.common import NoSuchElementException, TimeoutException
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

class SenderWorker(QObject):
    """
    Clase que realiza el trabajo pesado de Selenium en un hilo separado.
    Emite señales para comunicar el progreso y estado.
    """
    finished = Signal()
    progress = Signal(int)
    log_message = Signal(str)
    ask_login = Signal() # Señal para pedir al usuario que confirme el login en la GUI

    def __init__(self, file_path, static_vars, template_message, dynamic_file_columns):
        super().__init__()
        self.file_path = file_path
        self.static_vars = static_vars
        self.template_message = template_message
        self.dynamic_file_columns = dynamic_file_columns
        self.expected_columns = ['numero'] + self.dynamic_file_columns
        self.is_running = True
        self.driver = None
        self.recipients = []
        self.total_messages = 0

    @Slot()
    def run_initialization(self):
        """Inicia el proceso: lee archivo, abre navegador y emite ask_login."""
        try:
            self.log_message.emit("Leyendo archivo de datos...")
            try:
                df = pandas.read_csv(
                    self.file_path, sep=';', header=None, names=self.expected_columns,
                    dtype=str, skip_blank_lines=True, encoding='utf-8'
                )
                df.dropna(subset=self.expected_columns, how='all', inplace=True)
                df.fillna("", inplace=True)
                if df.empty or df['numero'].eq('').all():
                     raise ValueError(f"Archivo vacío o 'numero' vacío. Formato: {';'.join(self.expected_columns)};")

                # Validación de columnas extras (opcional)
                # ... (código de validación de columnas si lo deseas) ...

                self.recipients = df.to_dict('records')
            except Exception as e:
                self.log_message.emit(f"Error crítico al leer archivo: {e}")
                self.log_message.emit(traceback.format_exc())
                self.finished.emit(); return

            self.total_messages = len(self.recipients)
            if self.total_messages == 0:
                self.log_message.emit("No se encontraron destinatarios válidos."); self.finished.emit(); return
            self.log_message.emit(f"Se enviarán {self.total_messages} mensajes.")

            # --- Inicio del navegador ---
            self.log_message.emit("Iniciando navegador Chrome...")
            try:
                try:
                    driver_path = ChromeDriverManager().install()
                    service = Service(driver_path)
                    self.log_message.emit(f"ChromeDriver listo: {driver_path}")
                except Exception as driver_e:
                     self.log_message.emit(f"Error ChromeDriver: {driver_e}. Intentando continuar...")
                     service = Service()

                options = webdriver.ChromeOptions()
                self.driver = webdriver.Chrome(service=service, options=options)
                self.driver.get('https://web.whatsapp.com')
            except Exception as e:
                self.log_message.emit(f"Error al iniciar Chrome: {e}")
                self.log_message.emit(traceback.format_exc())
                self.finished.emit(); return

            self.log_message.emit("Navegador abierto. Escanea QR.")
            self.ask_login.emit() # Indica a la GUI que pida confirmación

        except Exception as e:
            self.log_message.emit(f"Error fatal en inicialización: {e}")
            self.log_message.emit(traceback.format_exc())
            if self.driver:
                try: self.driver.quit()
                except: pass
            self.finished.emit()

    @Slot()
    def continue_sending_messages(self):
        """Continúa el envío después de que el usuario confirma en la GUI."""
        if not self.driver:
            self.log_message.emit("Error: Navegador no inicializado."); self.finished.emit(); return
        if not self.is_running:
             self.log_message.emit("Detenido antes de confirmar login."); self.finished.emit(); return

        self.log_message.emit("Login confirmado. Iniciando envío...")
        try:
            count_sent = 0
            count_failed = 0
            for i, recipient in enumerate(self.recipients):
                if not self.is_running:
                    self.log_message.emit("Proceso cancelado durante envío."); break

                # Preparar variables
                current_vars = self.static_vars.copy()
                numero_dest = str(recipient.get('numero', '')).strip()
                variable_display_name = numero_dest
                missing_vars_msg = ""
                for col_name in self.dynamic_file_columns:
                    value = recipient.get(col_name)
                    value_str = str(value).strip() if value is not None else ""
                    current_vars[col_name] = value_str
                    if not value_str and value is None: missing_vars_msg += f"{col_name}, "
                    if col_name.lower() == 'nombre' and value_str: variable_display_name = f"{numero_dest} ({value_str})"
                if missing_vars_msg: self.log_message.emit(f"Advertencia: Faltan datos para '{variable_display_name}' en {missing_vars_msg[:-2]}. Usando vacíos.")

                # Formatear mensaje
                message = self.template_message
                try:
                    message = message.format_map(current_vars); encoded_message = quote(message)
                except Exception as e:
                     self.log_message.emit(f"Error formateo msg para {variable_display_name}: {e}. Saltando..."); count_failed += 1; self.progress.emit(int(((i + 1) / self.total_messages) * 100)); continue

                # Validar número
                if not numero_dest or not numero_dest.isdigit():
                    self.log_message.emit(f"Error: Número '{numero_dest}' inválido línea {i+1}. Saltando..."); count_failed += 1; self.progress.emit(int(((i + 1) / self.total_messages) * 100)); continue

                self.log_message.emit(f"[{i+1}/{self.total_messages}] Enviando a {variable_display_name}...")

                # Envío Selenium
                message_sent_successfully = False
                try:
                    url = f'https://web.whatsapp.com/send?phone=+52 1 {numero_dest}&text={encoded_message}'
                    self.driver.get(url)
                    chat_input_xpath = "//div[@contenteditable='true'][@data-tab='10'] | //div[@contenteditable='true'][@data-tab='1']"
                    try:
                        WebDriverWait(self.driver, 20).until(EC.presence_of_element_located((By.XPATH, chat_input_xpath)))
                        # self.log_message.emit("... Chat cargado.") # Log opcional
                    except TimeoutException:
                         try:
                            invalid_number_xpath = "//div[contains(@data-testid, 'popup-controls-ok')]"
                            WebDriverWait(self.driver, 5).until(EC.presence_of_element_located((By.XPATH, invalid_number_xpath)))
                            self.log_message.emit(f"Error: Número {numero_dest} inválido/sin WA (popup).")
                            try: self.driver.find_element(By.XPATH, invalid_number_xpath).click(); sleep(1)
                            except: pass
                         except TimeoutException:
                            self.log_message.emit(f"Error: No cargó chat para {numero_dest} en 20s.")
                         count_failed += 1; self.progress.emit(int(((i + 1) / self.total_messages) * 100)); continue

                    try:
                        xpath_send_button = "//button[@aria-label='Enviar'] | //span[@data-icon='send']/ancestor::button | //div[@role='button'][.//span[@data-icon='wds-ic-send-filled']]"
                        click_btn = WebDriverWait(self.driver, 40).until(EC.element_to_be_clickable((By.XPATH, xpath_send_button)))
                        sleep(random.uniform(1.5, 3.0)); click_btn.click(); sleep(random.uniform(4.0, 7.0))
                        self.log_message.emit(f"✓ Mensaje enviado a: {variable_display_name}")
                        count_sent += 1; message_sent_successfully = True
                    except TimeoutException: self.log_message.emit(f"Error: Botón enviar no encontrado/clicable para {variable_display_name}.")
                    except Exception as send_e: self.log_message.emit(f"Error inesperado al enviar a {variable_display_name}: {send_e}")

                except Exception as e:
                    self.log_message.emit(f"Fallo grave procesando {variable_display_name}: {e}")
                    self.log_message.emit(traceback.format_exc())

                if not message_sent_successfully: count_failed += 1
                self.progress.emit(int(((i + 1) / self.total_messages) * 100))
                sleep_time = random.uniform(2.5, 5.5)
                # self.log_message.emit(f"...pausando {sleep_time:.1f}s...") # Log opcional
                sleep(sleep_time)

            self.log_message.emit(f"Proceso finalizado. Enviados: {count_sent}, Fallidos/Saltados: {count_failed} de {self.total_messages}.")

        except Exception as e:
            self.log_message.emit(f"Error crítico en envío masivo: {e}")
            self.log_message.emit(traceback.format_exc())
        finally:
            self.cleanup() # Llama a la limpieza

    @Slot()
    def stop_process(self):
        """Marca el worker para detenerse y cierra el navegador si existe."""
        self.is_running = False
        self.log_message.emit("Solicitando cancelación...")
        self.cleanup() # Intenta cerrar el navegador inmediatamente

    def cleanup(self):
        """Cierra el navegador y emite la señal 'finished'."""
        if self.driver:
            try:
                self.driver.quit()
                self.log_message.emit("Navegador cerrado.")
                self.driver = None # Evita intentos repetidos de cierre
            except Exception as e:
                self.log_message.emit(f"Nota: No se pudo cerrar navegador (quizás ya cerrado): {e}")
        self.finished.emit()


class SenderModel(QObject):
    """
    Modelo: Mantiene el estado, maneja la lógica de negocio (worker) y emite señales.
    """
    # Señales para notificar al Controlador/Vista
    status_update = Signal(str)
    progress_update = Signal(int)
    ask_login_confirmation = Signal()
    process_finished = Signal()
    file_loaded = Signal(str) # Emite el nombre base del archivo cargado

    def __init__(self):
        super().__init__()
        self._file_path = ""
        self._worker = None
        self._thread = None

    def set_file_path(self, path):
        if path and os.path.exists(path):
            self._file_path = path
            self.file_loaded.emit(os.path.basename(path))
            self.status_update.emit(f"Archivo cargado: {path}")
        else:
            self._file_path = ""
            self.file_loaded.emit("Archivo no cargado.")
            self.status_update.emit("Error: Ruta de archivo inválida.")

    def get_file_path(self):
        return self._file_path

    def start_process(self, static_vars, template_message, dynamic_columns):
        if self._thread and self._thread.isRunning():
            self.status_update.emit("Error: Proceso ya en ejecución.")
            return
        if not self._file_path:
             self.status_update.emit("Error: No se ha cargado un archivo.")
             return

        self.status_update.emit("Iniciando worker...")
        self._thread = QThread()
        self._worker = SenderWorker(self._file_path, static_vars, template_message, dynamic_columns)
        self._worker.moveToThread(self._thread)

        # Conectar señales internas del worker a las señales del modelo
        self._worker.log_message.connect(self.status_update)
        self._worker.progress.connect(self.progress_update)
        self._worker.ask_login.connect(self.ask_login_confirmation)
        # Cuando el worker termine (finished), el modelo también emitirá process_finished
        # y limpiará el hilo
        self._worker.finished.connect(self._on_worker_finished)

        # Conectar inicio del hilo a la inicialización del worker
        self._thread.started.connect(self._worker.run_initialization)

        self._thread.start()

    def confirm_login_and_continue(self):
        if self._worker and self._thread and self._thread.isRunning():
            self.status_update.emit("Confirmación recibida, continuando envío...")
            # Llamar a continue_sending_messages en el hilo del worker
            QMetaObject.invokeMethod(self._worker, "continue_sending_messages", Qt.QueuedConnection)
        else:
            self.status_update.emit("Error: No se puede continuar, el proceso no está activo.")

    def stop_process(self):
        if self._worker and self._thread and self._thread.isRunning():
            self.status_update.emit("Intentando detener el proceso...")
            # Llamar a stop_process en el hilo del worker
            QMetaObject.invokeMethod(self._worker, "stop_process", Qt.QueuedConnection)
            # La señal finished se encargará de la limpieza final
        else:
             self.status_update.emit("El proceso no está en ejecución.")

    @Slot()
    def _on_worker_finished(self):
        """Slot interno para limpiar cuando el worker termina."""
        self.status_update.emit("Worker ha terminado.")
        if self._thread:
            if self._thread.isRunning():
                self._thread.quit()
                if not self._thread.wait(3000): # Espera 3 segs
                    self.status_update.emit("Advertencia: Hilo no terminó limpiamente.")
                    self._thread.terminate() # Forzar si es necesario
                    self._thread.wait()
            self._thread = None
        self._worker = None
        self.process_finished.emit() # Notificar al controlador que todo terminó