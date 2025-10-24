# controller.py
import re
import os
from PySide6.QtCore import QObject, Slot
from PySide6.QtWidgets import QFileDialog, QMessageBox

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
        # --- Añadido ---
        self._view.open_logs_clicked.connect(self.handle_open_logs)
        
        
        # ... (cierre de ventana opcional) ...

        # Conectar señales del Modelo a slots del Controlador o directamente a la Vista
        self._model.status_update.connect(self._view.update_log) # Log directo a la vista
        self._model.status_update.connect(self._view.set_status_label) # Estado general
        self._model.progress_update.connect(self._view.set_progress)
        self._model.ask_login_confirmation.connect(self.handle_ask_login)
        self._model.process_finished.connect(self.handle_process_finished)
        self._model.file_loaded.connect(self._view.set_file_label)

        # Actualizar formato inicial
        self.handle_template_change(self._view.get_template_text())

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
        file_path = self._model.get_file_path() 
        template = self._view.get_template_text().strip()
        static_vars = self._view.get_static_vars()

        # 2. Validaciones (archivo, plantilla)
        if not file_path or not os.path.exists(file_path):
            self._view.show_warning("Falta Archivo", "Carga un archivo de destinatarios válido."); return
        if not template:
            self._view.show_warning("Falta Plantilla", "Escribe el mensaje plantilla."); return
        
        # --- ELIMINADO ---
        # Ya no validamos que las variables estáticas estén llenas
        # if not all(static_vars.values()): 
        #     self._view.show_warning("Faltan Variables", "Completa todas las variables estáticas."); return
        # --- FIN DE ELIMINADO ---

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
        self._view.show_confirm_button(False)
        self._view.set_status_label("Iniciando...")
        self._view.set_progress(0)
        self.clear_log() # <--- Modificado: Llamar a la nueva función
        self._model.start_process(static_vars, template, dynamic_columns)

    # --- Slot para limpiar log ---
    @Slot()
    def clear_log(self):
        """Limpia el área de log de la vista."""
        self._view.log_area.clear()

    @Slot()
    def handle_stop(self):
        self._view.set_status_label("Deteniendo...")
        self._view.enable_stop_button(False) 
        self._model.stop_process()

    @Slot()
    def handle_ask_login(self):
        
        self._view.set_status_label("ℹ️ Escanea QR. Cuando carguen chats, haz clic abajo:")
        self._view.show_confirm_button(True)

    @Slot()
    def handle_confirm_login(self):
        
        self._view.show_confirm_button(False)
        self._view.set_status_label("✅ Login confirmado. Iniciando envío...")
        self._model.confirm_login_and_continue()

    @Slot()
    def handle_process_finished(self):
        
        self._view.set_status_label("Proceso terminado. Listo para iniciar.")
        self._view.enable_start_button(True)
        self._view.enable_stop_button(False)
        self._view.show_confirm_button(False)

    # --- Slot para manejar clic en botón de logs ---
    @Slot()
    def handle_open_logs(self):
        """Llama a la vista para que abra la carpeta de logs."""
        logs_dir = self._model.get_logs_directory()
        self._view.open_logs_folder(logs_dir) # Llama al nuevo slot de la vista
    