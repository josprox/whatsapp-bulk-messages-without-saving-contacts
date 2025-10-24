# controller.py
import re
import os
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox
from PySide6.QtGui import QStandardItemModel 

# Importar Modelo y Vista
from model import SenderModel
from view import MainView

class AppController(QObject):
    """
    Controlador: Conecta la Vista y el Modelo, maneja la lógica de la aplicación.
    """
    def __init__(self, model: SenderModel, view: MainView):
        super().__init__()
        self._model = model
        self._view = view

        # Conectar señales de la Vista a slots del Controlador
        self._view.load_file_clicked.connect(self.handle_load_file)
        self._view.start_clicked.connect(self.handle_start)
        self._view.stop_clicked.connect(self.handle_stop)
        self._view.confirm_login_clicked.connect(self.handle_confirm_login)
        self._view.template_text_changed.connect(self.handle_template_change)

        # --- Nuevas conexiones para el Visor de Logs ---
        self._view.refresh_logs_list_clicked.connect(self.handle_refresh_logs_list)
        self._view.log_file_selected.connect(self.handle_log_file_selected)
        # --- Fin de Nuevas conexiones ---


        # Conectar señales del Modelo a slots del Controlador o Vista
        self._model.status_update.connect(self._view.update_log) # Log directo a la vista
        self._model.status_update.connect(self._view.set_status_label) # Estado general
        self._model.progress_update.connect(self._view.set_progress)
        self._model.ask_login_confirmation.connect(self.handle_ask_login)
        self._model.process_finished.connect(self.handle_process_finished)
        self._model.file_loaded.connect(self._view.set_file_label)

        # --- Conexiones del Modelo para el Visor de Logs ---
        self._model.log_available.connect(self.handle_log_available)
        self._model.available_logs_list.connect(self._view.update_log_files_list)
        self._model.log_data_ready.connect(self._view.set_log_table_model)
        self._model.log_data_ready.connect(self.handle_log_data_loaded) # Para cambiar de pestaña
        # --- Fin de Conexiones ---

        # Actualizar formato inicial basado en plantilla vacía o por defecto
        self.handle_template_change(self._view.get_template_text())
        # Cargar lista de logs existentes al iniciar
        self.handle_refresh_logs_list()

    @Slot()
    def handle_load_file(self):
        file_dialog = QFileDialog(self._view)
        file_dialog.setNameFilter("Archivos de datos (*.txt *.csv)")
        file_dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if file_dialog.exec():
            filenames = file_dialog.selectedFiles()
            if filenames:
                self._model.set_file_path(filenames[0])
            else:
                 self._model.set_file_path("") # Limpiar si cancela

    @Slot(str)
    def handle_template_change(self, template):
        # Calcular columnas dinámicas y actualizar etiqueta en la vista
        static_var_names = list(self._view.get_static_vars().keys())
        placeholders = re.findall(r'\{(\w+)\}', template)
        dynamic_columns = sorted(list(set(
            var for var in placeholders if var != 'numero' and var not in static_var_names
        )))
        format_str = "numero;" + ";".join(dynamic_columns) + ";"
        self._view.set_expected_format_label(format_str)

    @Slot()
    def handle_start(self):
        # 1. Obtener datos de la Vista
        file_path = self._model.get_file_path() # Obtener del modelo donde se validó
        template = self._view.get_template_text().strip()
        static_vars = self._view.get_static_vars()

        # 2. Validaciones básicas (archivo, plantilla)
        if not file_path or not os.path.exists(file_path):
            self._view.show_warning("Falta Archivo", "Carga un archivo de destinatarios válido."); return
        if not template:
            self._view.show_warning("Falta Plantilla", "Escribe el mensaje plantilla."); return
        
        # 3. Validar consistencia de plantilla y variables
        static_var_names = list(static_vars.keys())
        placeholders = re.findall(r'\{(\w+)\}', template)
        dynamic_columns = sorted(list(set(var for var in placeholders if var != 'numero' and var not in static_var_names)))
        all_available_vars = set(static_var_names + dynamic_columns + ['numero'])
        missing_vars = [p for p in placeholders if p not in all_available_vars]
        if missing_vars:
             self._view.show_warning("Error Plantilla", f"Variable(s) no definida(s): {', '.join(missing_vars)}"); return
        try:
             test_vars = {k: f"[{k}]" for k in all_available_vars}
             template.format_map(test_vars)
        except Exception as e:
             self._view.show_warning("Error Formato Plantilla", f"Revisa llaves: {e}"); return

        # 4. Actualizar estado de la GUI y llamar al Modelo para iniciar
        self._view.enable_start_button(False)
        self._view.enable_stop_button(True)
        self._view.show_confirm_button(False) # Ocultar por si estaba visible
        self._view.set_status_label("Iniciando...")
        self._view.set_progress(0)
        self.clear_log() # Limpiar log en vivo
        self._model.start_process(static_vars, template, dynamic_columns)

    @Slot()
    def clear_log(self):
        """Limpia el área de log de la vista."""
        self._view.log_area.clear()

    @Slot()
    def handle_stop(self):
        self._view.set_status_label("Deteniendo...")
        self._view.enable_stop_button(False) # Deshabilitar mientras se detiene
        self._model.stop_process()

    @Slot()
    def handle_ask_login(self):
        # El modelo pide confirmación, actualizamos la vista
        self._view.set_status_label("ℹ️ Escanea QR. Cuando carguen chats, haz clic abajo:")
        self._view.show_confirm_button(True)

    @Slot()
    def handle_confirm_login(self):
        # Usuario confirmó en la vista, le decimos al modelo que continúe
        self._view.show_confirm_button(False) # Ocultar botón
        self._view.set_status_label("✅ Login confirmado. Iniciando envío...")
        self._model.confirm_login_and_continue()

    @Slot()
    def handle_process_finished(self):
        # El modelo indica que todo terminó (o fue detenido)
        self._view.set_status_label("Proceso terminado. Listo para iniciar.")
        self._view.enable_start_button(True)
        self._view.enable_stop_button(False)
        self._view.show_confirm_button(False)
        
        # Refrescar lista de logs al terminar
        self.handle_refresh_logs_list()

    # --- Slots del Visor de Logs ---

    @Slot()
    def handle_refresh_logs_list(self):
        """Pide al modelo que busque los archivos de log."""
        self._view.update_log("Buscando archivos de log...")
        self._model.fetch_available_logs()

    @Slot(str)
    def handle_log_file_selected(self, file_path: str):
        """
        El usuario seleccionó un archivo del ComboBox.
        Pide al modelo que lo cargue.
        """
        if file_path:
            self._view.update_log(f"Cargando archivo de log: {os.path.basename(file_path)}")
            self._model.load_log_file(file_path)
        else:
            self._view.update_log("Selección de log inválida.")

    @Slot(str, int)
    def handle_log_available(self, file_path, error_count):
        """
        Se activa cuando el worker termina y reporta un NUEVO log.
        Refresca la lista y carga automáticamente el log recién creado.
        """
        self._view.update_log(f"Proceso terminado con {error_count} errores. Cargando log...")
        
        # 1. Refrescar la lista (esto actualizará el ComboBox)
        self.handle_refresh_logs_list()
        
        # 2. Pedir al modelo que cargue el *nuevo* archivo específico
        self._model.load_log_file(file_path)
        # (La señal 'log_data_ready' se encargará de mostrarlo y cambiar de pestaña)

    @Slot(QStandardItemModel)
    def handle_log_data_loaded(self, model_data):
        """
        Se activa DESPUÉS de que 'set_log_table_model' haya sido llamado.
        Cambia automáticamente a la pestaña de logs.
        """
        if model_data and model_data.rowCount() > 0:
            self._view.update_log("Log cargado en el visor.")
            self._view.switch_to_logs_tab() # Llama a la nueva función de la vista
        else:
            self._view.update_log("El archivo de log seleccionado está vacío.")