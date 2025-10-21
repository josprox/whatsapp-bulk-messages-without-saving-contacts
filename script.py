# Program to send bulk messages through WhatsApp web from an excel sheet without saving contact numbers
# Author @inforkgodara

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager
from time import sleep
import pandas

# --- CORRECCIÓN 1: Importar Service ---
from selenium.webdriver.chrome.service import Service

excel_data = pandas.read_excel('Recipients data.xlsx', sheet_name='Recipients')

count = 0

# --- CORRECCIÓN 1: Inicializar el driver con Service ---
# Esta es la forma correcta en Selenium 4+
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)
# ----------------------------------------------------

driver.get('https://web.whatsapp.com')
input("Press ENTER after login into Whatsapp Web and your chats are visiable.")
for column in excel_data['Contact'].tolist():
    try:
        url = 'https://web.whatsapp.com/send?phone=+52 1 {}&text={}'.format(excel_data['Contact'][count], excel_data['Message'][0])
        sent = False
        # It tries 3 times to send a message in case if there any error occurred
        driver.get(url)
        try:
            # --- CORRECCIÓN 2: Usar XPath estable para el botón de enviar ---
            # La clase '_3XKXx' cambia todo el tiempo. XPath es mejor.
            # Este XPath busca el botón que contiene el ícono de 'enviar'.
            xpath_send_button = "//div[@role='button'][.//span[@data-icon='wds-ic-send-filled']]"
            click_btn = WebDriverWait(driver, 35).until(
                EC.element_to_be_clickable((By.XPATH, xpath_send_button)))
            # -----------------------------------------------------------
            
        except Exception as e:
            print("Sorry message could not sent to " + str(excel_data['Contact'][count]))
        else:
            sleep(2)
            click_btn.click()
            sent = True
            sleep(5)
            print('Message sent to: ' + str(excel_data['Contact'][count]))
        count = count + 1
    except Exception as e:
        print('Failed to send message to ' + str(excel_data['Contact'][count]) + str(e))
driver.quit()
print("The script executed successfully.")