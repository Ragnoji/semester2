import os
import socket
import threading
from time import sleep
import re
from random import shuffle


searching_lock = threading.Lock()
client_init_lock = threading.Lock()
code_lock = threading.Lock()
wait_lock = threading.Lock()
game_lock = threading.Lock()

host = '127.0.0.1'
port = 5060

server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((host, port))
server.listen()

clients = {}
free_players = []
session_info = {}


def handle(client):

    def opponent_valid(cl):
        op = session_info[cl]['opponent']
        if op.fileno == -1:
            clients[cl]['state'] = 4
            del session_info[cl]
            del session_info[op]
            del clients[op]
            free_players.append(cl)
            return False
        return op

    while True:
        if client.fileno == -1:  # Соединение разорвано
            print(f'Connection closed with client {client}')
            return

        if client not in clients:  # Клиент не аутентифицирован
            client.send('nickname'.encode('ascii'))

            nickname = client.recv(1024).decode('ascii')
            if not nickname:
                print(f'Connection closed with client {client}')
                return

            if len(nickname) == 0:
                client.send('invalid'.encode('ascii'))
                continue
            client.send('valid'.encode('ascii'))

            with client_init_lock:
                clients[client] = {'nickname': nickname, 'state': 0}
                free_players.append(client)

            print("Nickname is {}".format(nickname))

        if clients[client]['state'] == 0:  # Клиент еще не в сессии
            client.send('search'.encode('ascii'))
            while True:
                sleep(1)
                with searching_lock:
                    if client.fileno == -1 or clients[client]['state'] != 0:
                        break

                    for opponent in free_players:  # Подбор свободного соперника
                        if opponent != client:
                            if opponent.fileno == -1:
                                free_players.remove(opponent)
                                del clients[opponent]
                                continue
                            free_players.remove(client)
                            free_players.remove(opponent)

                            session_info[client] = {'opponent': opponent}
                            session_info[opponent] = {'opponent': client}

                            clients[client]['state'] = 1
                            clients[opponent]['state'] = 1
                            break

        if clients[client]['state'] == 1:  # Загадывание числа
            client.send('guess'.encode('ascii'))
            while True:
                with code_lock:
                    if client.fileno == -1 or clients[client]['state'] != 1:
                        break

                    opponent = opponent_valid(client)
                    if not isinstance(opponent, socket.socket):
                        break

                    if 'code' not in session_info[client]:
                        number = client.recv(1024).decode('ascii')
                        if not number:
                            break
                        if not re.match(r'^(?!.*(.).*\1)\d{4}$', number):
                            client.send('invalid'.encode('ascii'))
                            continue
                        client.send('valid'.encode('ascii'))

                        session_info[client]['code'] = number

        if clients[client]['state'] == 2:  # Ожидание загадывания числа от опонента и определение первого угадывающего
            client.send('wait'.encode('ascii'))
            while True:
                with wait_lock:
                    if client.fileno == -1 or clients[client]['state'] != 2:
                        break

                    opponent = opponent_valid(client)
                    if not isinstance(opponent, socket.socket):
                        break

                    opponent_info = session_info[opponent]

                    if 'code' in opponent_info:
                        if 'guessing' not in session_info.get(client):
                            order = [opponent, client]
                            shuffle(order)

                            session_info[order[0]]['guessing'] = True
                            session_info[order[1]]['guessing'] = False

                            clients[client]['state'] = 3
                            clients[opponent]['state'] = 3
                        break
        elif clients[client]['state'] == 3:  # Игра началась
            client.send('start'.encode('ascii'))
            while True:
                with game_lock:
                    if client.fileno == -1 or clients[client]['state'] != 3:
                        break

                    opponent = opponent_valid(client)
                    if not isinstance(opponent, socket.socket):
                        break

                    opponent_info = session_info[opponent]
                    client_info = session_info[client]

                    if not client_info['guessing']:
                        continue

                    client.send('guess'.encode('ascii'))
                    number = client.recv(1024).decode('ascii')

                    if not number or not re.match(r'^(?!.*(.).*\1)\d{4}$', number):
                        client.send('invalid'.encode('ascii'))
                        continue
                    client.send('valid'.encode('ascii'))

                    bull, cow = 0, 0
                    opponent_number = opponent_info['code']

                    for i, digit in enumerate(number):
                        if digit in opponent_number and i == opponent_number.find(digit):
                            bull += 1
                        elif digit in opponent_number:
                            cow += 1

                    client.send(f"{number} | {bull} Bull | {cow} Cow".encode('ascii'))
                    opponent.send(f"{number} | {bull} Bull | {cow} Cow".encode('ascii'))

                    if bull == 4:
                        clients[client]['state'] = 4
                        client.send('win'.encode('ascii'))
                        clients[opponent]['state'] = 4
                        opponent.send('lose'.encode('ascii'))
                        opponent.send(client_info['code'].encode('ascii'))
                        del session_info[opponent]
                        del session_info[client]
                        break

                    session_info[client]['guessing'] = False
                    session_info[opponent]['guessing'] = True
        elif clients[client]['state'] == 4:  # После итога матча
            msg = client.recv(1024).decode('ascii')
            if not msg:
                break
            if msg == 'search':
                clients[client]['state'] = 0
                free_players.append(client)


def receive():
    while True:
        client, address = server.accept()
        print("Connected with {}".format(str(address)))

        thread = threading.Thread(target=handle, args=(client,))
        thread.start()


os.system('clear')
receive()