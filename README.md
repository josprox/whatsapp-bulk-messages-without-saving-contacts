
# WhatsApp Bulk Sender GUI (AuraSend): Automatización de Mensajería Personalizada

## Introducción

**WhatsApp Bulk Sender GUI** es una aplicación de escritorio desarrollada en Python que facilita el envío masivo de mensajes personalizados a través de WhatsApp Web. Utilizando una interfaz gráfica intuitiva construida con PySide6 y la automatización del navegador mediante Selenium, esta herramienta permite a los usuarios gestionar campañas de comunicación eficientes basadas en plantillas y datos externos.

## Características Principales

* **Interfaz Gráfica de Usuario (GUI):** Proporciona un entorno visual claro y fácil de operar para usuarios sin experiencia técnica, construido con el framework PySide6.
* **Sistema de Plantillas Dinámicas:** Permite definir mensajes base con marcadores de posición (`{variable}`) que se sustituyen con datos específicos para cada destinatario.
* **Detección Automática de Variables:** Analiza la plantilla de mensaje para identificar automáticamente las columnas de datos requeridas en el archivo de entrada, además de las variables estáticas definidas.
* **Variables Estáticas Configurables:** Permite definir valores fijos (ej. nombre del remitente, nombre de la empresa) directamente en la interfaz, aplicables a todos los mensajes.
* **Importación de Datos:** Soporta la carga de información de destinatarios desde archivos de texto plano (`.txt`) o valores separados por comas (`.csv`), utilizando el punto y coma (`;`) como delimitador.
* **Automatización con Selenium:** Emplea Selenium WebDriver y `webdriver-manager` para controlar una instancia de Google Chrome e interactuar de forma programática con la interfaz de WhatsApp Web.
* **Monitorización en Tiempo Real:** Incluye una barra de progreso y un área de registro (log) detallada para seguir el estado del proceso de envío y diagnosticar posibles incidencias.
* **Manejo Básico de Errores:** Incorpora mecanismos para detectar y reportar números de teléfono inválidos o errores durante el intento de envío.

## Requisitos Previos

Para utilizar esta aplicación, asegúrese de cumplir con los siguientes requisitos:

1.  **Python:** Se recomienda la versión 3.7 o superior del intérprete de Python.
2.  **Google Chrome:** Es necesario tener instalado el navegador Google Chrome, ya que es el navegador automatizado por el script.
3.  **Dependencias de Python:** Instale las librerías requeridas ejecutando el siguiente comando en su terminal o consola:
    ```bash
    pip install PySide6 pandas selenium webdriver-manager
    ```

## Instrucciones de Uso

Siga estos pasos para operar la aplicación:

1.  **Guardar el Script:** Descargue o copie el código fuente y guárdelo en un archivo con extensión `.py` (ej. `whatsapp_sender.py`).
2.  **Preparar el Archivo de Datos:**
    * Cree un archivo de texto (`.txt`) o CSV (`.csv`) en el mismo directorio que el script (ej. `destinatarios.txt`).
    * Este archivo **debe** utilizar el **punto y coma (`;`)** como delimitador de campos.
    * La **primera columna** corresponde siempre al **número de teléfono** del destinatario (incluyendo código de país, sin el símbolo `+` ni espacios; ej. `5215512345678`).
    * Las **columnas subsecuentes** deben contener los datos para las variables dinámicas identificadas en la plantilla de mensaje. La interfaz gráfica indicará el formato exacto esperado (`numero;variable1;variable2;...;`).
    * Es crucial guardar el archivo con codificación **UTF-8** para asegurar la correcta interpretación de caracteres especiales y acentos.
3.  **Ejecutar la Aplicación:** Abra una terminal o símbolo del sistema, navegue hasta el directorio del script y ejecútelo mediante:
    ```bash
    python whatsapp_sender.py
    ```
4.  **Cargar Archivo de Datos:** Dentro de la aplicación, haga clic en "Cargar Archivo de Destinatarios" y seleccione el archivo preparado en el paso 2.
5.  **Configurar Variables Estáticas:** Ingrese los valores correspondientes para las variables fijas (`minombre`, `miempresa`, etc.) en los campos designados.
6.  **Definir la Plantilla:** Escriba o pegue el texto del mensaje en el área "Plantilla del Mensaje". Utilice llaves `{}` para indicar las variables (ej. `{nombre}`). Observe la etiqueta "Formato esperado del archivo", que se actualizará dinámicamente para reflejar las columnas necesarias según su plantilla. Verifique que su archivo de datos cumpla con este formato.
7.  **Iniciar Proceso:** Haga clic en el botón "Iniciar Envío".
8.  **Autenticación en WhatsApp Web:**
    * Se abrirá automáticamente una ventana de Google Chrome cargando WhatsApp Web.
    * Utilice la aplicación móvil de WhatsApp en su teléfono para escanear el código QR mostrado.
    * **Espere** a que la interfaz de WhatsApp Web cargue completamente sus conversaciones.
    * Regrese a la **terminal o consola** donde ejecutó el script inicial y **presione la tecla ENTER** para confirmar que ha iniciado sesión.
9.  **Monitorizar Envío:** La aplicación comenzará a enviar los mensajes secuencialmente. El progreso se mostrará en la barra y los detalles aparecerán en el área de Log. Puede interrumpir el proceso en cualquier momento haciendo clic en "Detener Envío".

## Ejemplo de Configuración

A continuación, se muestra un caso de uso práctico:

**Plantilla de Mensaje:**
````

Hola buenas tardes {nombre}, te está atendiendo {minombre} de la {miempresa}, el motivo de este mensaje es para recordarle de la materia {nombre\_materia}, pues con esta inscripción, ya la estaría cursando {numveces} veces, en caso de alguna aclaración, comuniquese directamente con su director de carrera.

````

**Variables Estáticas (configuradas en la GUI):**

* `minombre`: Juan Perez
* `miempresa`: Universidad Ejemplo

**Formato Esperado del Archivo de Datos (indicado por la GUI):**
`numero;nombre;nombre_materia;numveces;`

**Contenido del archivo `destinatarios.txt` (ejemplo):**
```

5215511112222;Ana García;Cálculo I;3;
5213344445555;Luis Martínez;Álgebra Lineal;2;
5218177778888;Sofía Hernández;Programación Básica;4;

```
*(Archivo guardado con codificación UTF-8)*

## Consideraciones Importantes y Descargo de Responsabilidad

* **Mantenimiento:** La estructura del sitio web de WhatsApp Web puede cambiar sin previo aviso. Dichos cambios podrían requerir actualizaciones en el código del script (particularmente en los selectores XPath utilizados por Selenium) para mantener su funcionalidad.
* **Políticas de Uso de WhatsApp:** La automatización de interacciones en WhatsApp puede infringir sus términos de servicio. El envío excesivo de mensajes, especialmente a contactos no guardados o a alta velocidad, puede resultar en la suspensión temporal o permanente de la cuenta de WhatsApp asociada. Se recomienda encarecidamente utilizar esta herramienta de forma responsable, moderada y ética, considerando la implementación de pausas más largas y variables entre envíos.
* **Gestión de Errores:** Aunque el script incluye manejo básico de errores, factores externos (conectividad de red, cambios inesperados en WhatsApp Web, interrupciones del sistema) pueden generar fallos. Revise el log para obtener información detallada sobre cualquier problema.
* **Finalidad de Uso:** Esta herramienta está diseñada para facilitar comunicaciones legítimas y consentidas. No debe utilizarse para la distribución de spam, mensajes no solicitados o cualquier actividad que viole la privacidad o las normativas aplicables.
* **Independencia:** Este proyecto es una herramienta independiente y no está afiliado, respaldado ni patrocinado por WhatsApp, Meta Platforms, Inc., o sus subsidiarias.

### Compilar
Puede compilar la aplicación instalando pyinstaller y usando el siguiente comando
```bash
pyinstaller --windowed --name="WhatsApp Bulk Sender" --ico="img/AuraSend.ico" --add-data "msedgedriver.exe;." --add-data "img;img" main.py
```