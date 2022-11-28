from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import QApplication, QMainWindow, QMessageBox

import re
import socket
import threading

from main_interface import Ui_MainWindow


class MainWidget(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWidget, self).__init__()
        self.setupUi(self)

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(('192.168.115.39', 5060))
        self.reciever = threading.Thread(target=self.recieve)
        self.reciever.start()

        self.logs.ensureCursorVisible()

        self.input.textChanged.connect(self.on_input_changed)
        self.input_button.clicked.connect(self.send)

        self.search_button.clicked.connect(self.search)

        self.nickname = ''
        self.opponent_nick = ''

    def send(self):
        message = self.input.text()
        try:
            message.encode('ascii')
        except UnicodeEncodeError:
            self.last_response.setText('Write ASCII text')
            self.input.setText('')
            return

        if self.nickname and not bool(re.match(r'^(?!.*(.).*\1)\d{4}$', message)):
            self.last_response.setText('Write 4 unique digits')
            self.input.setText('')
            return

        self.client.send(message.encode('ascii'))
        self.input_button.setEnabled(False)

    def on_input_changed(self):
        self.input_button.setEnabled(bool(self.input.text()))

    def search(self):
        self.logs.clear()
        self.client.send('search'.encode('ascii'))
        self.search_button.setEnabled(False)
        self.main_label.setText('Searching..')
        self.last_response.setText('Started search')

    def closeEvent(self, event):
        self.client.close()
        event.accept()

    def recieve(self):
        conn_exceptions = (ConnectionRefusedError, ConnectionAbortedError, ConnectionResetError)
        while True:
            try:
                resp = self.client.recv(1024).decode('ascii')
            except conn_exceptions:
                return

            if resp == 'invalid_opponent':
                self.last_response.setText('Opponent left match')
                self.logs.append(f"Opponent left match, you technically won!")
                self.input.clear()
                self.input.setEnabled(False)
                self.input_button.setEnabled(False)
                self.search_button.setEnabled(True)
                self.main_label.setText("Search game when you're ready")
                continue

            if resp == 'invalid_characters':
                self.last_response.setText('Write latin symbs')
                self.input.clear()
                continue

            if resp == 'invalid_taken':
                self.last_response.setText('Nickname is taken')
                self.input.clear()
                continue

            if resp == 'invalid_empty':
                self.last_response.setText('Send non-empty message!')
                continue

            if resp == 'invalid_code':
                self.last_response.setText('Write 4 unique digits')
                continue

            if resp.split()[0] == 'valid_nickname':
                self.nickname = resp.split()[1]
                self.label.setText(f'You({self.nickname})')
                self.main_label.setText(f'Now you can search for game')
                self.input.clear()
                self.input.setEnabled(False)
                self.input_button.setEnabled(False)
                self.search_button.setEnabled(True)
                self.input.setMaxLength(4)
                self.input.setValidator(QIntValidator())
                continue
            if resp.split()[0] == 'valid_wish':
                code = resp.split()[1]
                self.last_response.setText(f"You've made a code {code}")
                self.logs.append(f"You've made a code {code}")
                self.input.clear()
                self.input.setEnabled(False)
                self.input_button.setEnabled(False)
                continue
            if resp == 'first':
                self.last_response.setText("You're first to guess")
                self.input.clear()
                self.input.setEnabled(True)
                self.input_button.setEnabled(False)
                self.search_button.setEnabled(False)
                continue
            if resp == 'second':
                self.last_response.setText(f"{self.opponent_nick} is first to guess")
                self.input.clear()
                self.input.setEnabled(False)
                self.input_button.setEnabled(False)
                self.search_button.setEnabled(False)
                continue
            if resp.split()[0] == 'game':
                self.last_response.setText("Make your code")
                self.input.setEnabled(True)
                self.input_button.setEnabled(False)
                self.opponent_nick = resp.split()[1]
                self.main_label.setText(f"{self.nickname}(you) vs {self.opponent_nick}")
                continue
            if resp.split()[0] == 'lose':
                code = resp.split()[1]
                self.last_response.setText(f'Actual code was: {code}')
                self.logs.append(f"{self.opponent_nick} won")
                self.input.clear()
                self.input.setEnabled(False)
                self.input_button.setEnabled(False)
                self.search_button.setEnabled(True)
                self.main_label.setText("You lost :( Search game when you're ready")
                continue
            if resp == 'guess':
                self.last_response.setText("Your turn to guess")
                self.input.setEnabled(True)
                self.main_label.setText("Waiting for your guess")
                continue
            if resp == 'win':
                self.last_response.setText('You won this session!')
                self.logs.append(f"You won!")
                self.input.clear()
                self.input.setEnabled(False)
                self.input_button.setEnabled(False)
                self.search_button.setEnabled(True)
                self.main_label.setText("You won :) Search game when you're ready")
                continue
            if resp == 'wait':
                self.last_response.setText(f"Waiting for {self.opponent_nick}'s guess")
                self.input.clear()
                self.input.setEnabled(False)
                self.input_button.setEnabled(False)
                self.main_label.setText(f"Wait for {self.opponent_nick}'s guess")
                continue
            if resp == '?':
                continue
            self.logs.append(resp)


if __name__ == '__main__':
    app = QApplication([])
    w = MainWidget()
    w.show()
    app.exec()
