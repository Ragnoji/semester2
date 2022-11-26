from PyQt6.QtCore import pyqtSlot
from PyQt6.QtGui import QIntValidator
from PyQt6.QtWidgets import QApplication, QMainWindow

import sys
import re
import socket

from main_interface import Ui_MainWindow


class MainWidget(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super(MainWidget, self).__init__()
        self.setupUi(self)

        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.client.connect(('127.0.0.1', 5060))

        self.input.textChanged.connect(self.on_input_changed)
        self.input_button.clicked.connect(self.send)

        self.search_button.clicked.connect(self.search)

        self.nickname = ''

    def send(self):
        message = self.input.text()

        try:
            message.encode('ascii')
        except UnicodeEncodeError:
            self.last_response.setText('Please write only ASCII-characters')
            self.input.setText('')
            return

        if self.nickname and not bool(re.match(r'^(?!.*(.).*\1)\d{4}$', message)):
            self.last_response.setText('Allowed input is 4-digit(unique) number')
            self.input.setText('')
            return

        self.client.send(message.encode('ascii'))
        response = self.client.recv(1024).decode('ascii')

        if response == 'invalid_opponent':
            self.game_position = ''
            self.last_response.setText('Opponent left match')
            self.logs.append(f"Opponent left match, you technically won!")
            self.input.clear()
            self.input.setEnabled(False)
            self.search_button.setEnabled(True)
            self.main_label.setText("Search game when you're ready")
            return

        if response == 'invalid_characters':
            self.last_response.setText('Please write only ASCII-characters!')
            self.input.setText('')
            return

        if response == 'invalid_empty':
            self.last_response.setText('Send non-empty message!')
            return

        if response == 'invalid_code':
            self.last_response.setText('Allowed input is 4-digit(unique) number')
            return

        if response == 'valid_nickname':
            self.nickname = message
            self.label.setText(f'You({message})')
            self.main_label.setText(f'Now you can search for game')
            self.input.clear()
            self.input.setEnabled(False)
            self.search_button.setEnabled(True)
            self.input.setMaxLength(4)
            self.input.setValidator(QIntValidator())
            return

        if response == 'valid_wish':
            self.last_response.setText(f"You've made a code {message}")
            self.logs.append(f"You: have made a code {message}")
            self.input.clear()
            self.input.setEnabled(False)
            self.main_label.setText('Waiting for opponent to make code')
            await_response = self.client.recv(1024).decode('ascii')
            if await_response == 'invalid_opponent':
                self.last_response.setText('Opponent left match')
                self.logs.append(f"Opponent left match, you technically won!")
                self.input.clear()
                self.input.setEnabled(False)
                self.search_button.setEnabled(True)
                self.main_label.setText("Search game when you're ready")
            if await_response == 'first':
                self.last_response.setText("You're first to guess")
                self.logs.append(f"You're first to guess")
                self.input.clear()
                self.input.setEnabled(True)
                self.search_button.setEnabled(False)
                self.main_label.setText("Your time to make a guess")
            if await_response == 'second':
                self.last_response.setText("Your opponent is first to guess")
                self.logs.append(f"Your opponent is first to guess")
                self.input.clear()
                self.input.setEnabled(False)
                self.search_button.setEnabled(False)
                self.main_label.setText("Wait for your opponents' guess")
                self.wait_for_opponent()
            return

        if response == 'valid_guess':
            message = self.client.recv(1024).decode('ascii')
            self.logs.append(message)

            result = self.client.recv(1024).decode('ascii')
            if result == 'win':
                self.last_response.setText('You won this session!')
                self.logs.append(f"You guessed opponents' code first!")
                self.input.clear()
                self.input.setEnabled(False)
                self.search_button.setEnabled(True)
                self.main_label.setText("You won :) Search game when you're ready")

    def on_input_changed(self):
        self.input_button.setEnabled(bool(self.input.text()))

    def wait_for_opponent(self):
        resp = self.client.recv(1024).decode('ascii')
        if resp == 'invalid_opponent':
            self.last_response.setText('Opponent left match')
            self.logs.append(f"Opponent left match, you technically won!")
            self.input.clear()
            self.input.setEnabled(False)
            self.search_button.setEnabled(True)
            self.main_label.setText("Search game when you're ready")
            return
        self.logs.append(resp)
        resp = self.client.recv(1024).decode('ascii')

        if resp == 'lose':
            code = self.client.recv(1024).decode('ascii')
            self.last_response.setText(f'Actual code was: {code}')
            self.logs.append(f"Your opponent won")
            self.input.clear()
            self.input.setEnabled(False)
            self.search_button.setEnabled(True)
            self.main_label.setText("You lost :( Search game when you're ready")
            return
        if resp == 'guess':
            self.last_response.setText("Your turn to guess")
            self.input.setEnabled(True)
            self.main_label.setText("Waiting for your guess")
            return

    def search(self):
        self.client.send('search'.encode('ascii'))
        response = self.client.recv(1024).decode('ascii')
        if response == 'game':
            self.search_button.setEnabled(False)
            self.last_response.setText("Game was found")
            self.input.setEnabled(True)
            opponent_nick = self.client.recv(1024).decode('ascii')
            self.main_label.setText(f"Make your code")
            self.logs.append(f'Initialized game between you({self.nickname}) and {opponent_nick}')


if __name__ == '__main__':
    app = QApplication([])
    w = MainWidget()
    w.show()
    app.exec()
