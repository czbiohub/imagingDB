from PyQt5.QtWidgets import QApplication
from components import Window, DatasetBrowser

credentials = "/Users/kevin.yamauchi/Documents/db_credentials.json"

app = QApplication([])

browser = DatasetBrowser(credentials)
window = Window(browser, show=False)
window.show()

app.exec()