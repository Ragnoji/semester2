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
        if op.fileno() == -1:
            clients[cl]['state'] = 4
            del session_info[cl]
            del session_info[op]
            del clients[op]
            free_players.append(cl)
            return False
        return op

    while True:
        if client not in clients:  # Клиент не аутентифицирован
            try:
                nickname = client.recv(1024)
            except ConnectionAbortedError:
                print('Connection aborted')
                client.close()
                return

            try:
                nickname = nickname.decode('ascii')
            except UnicodeDecodeError:
                try:
                    client.send('invalid_characters'.encode('ascii'))
                except ConnectionRefusedError:
                    print('Connection refused')
                    client.close()
                    return
                continue

            if len(nickname) == 0:
                try:
                    client.send('invalid_empty'.encode('ascii'))
                except ConnectionRefusedError:
                    print('Connection refused')
                    return
                continue

            with client_init_lock:
                if nickname in [c['nickname'] for c in clients.values()]:
                    try:
                        client.send('invalid_taken')
                    except ConnectionRefusedError:
                        print('Connection refused')
                        return
                    continue
                clients[client] = {'nickname': nickname, 'state': 4}
            try:
                client.send('valid_nickname'.encode('ascii'))
            except ConnectionRefusedError:
                print('Connection refused')
                del clients[client]
                return

            print("Nickname is {}".format(nickname))

        if clients[client]['state'] == 0:  # Поиск игры
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

                            try:
                                client.send('game'.encode('ascii'))
                            except ConnectionRefusedError:
                                print('Connection refused cln')
                            try:
                                opponent.send('game'.encode('ascii'))
                            except ConnectionRefusedError:
                                print('Connection refused opp')

                            client.send(clients[opponent]['nickname'].encode('ascii'))
                            opponent.send(clients[client]['nickname'].encode('ascii'))
                            break

        if clients[client]['state'] == 1:  # Загадывание числа
            while True:
                with code_lock:
                    if client.fileno == -1 or clients[client]['state'] != 1:
                        break

                    number = client.recv(1024)

                    opponent = opponent_valid(client)
                    if not isinstance(opponent, socket.socket):
                        client.send('invalid_opponent'.encode('ascii'))
                        clients[client]['state'] = 4
                        break

                    if number is False or number is None:
                        break
                    try:
                        number = number.decode('ascii')
                    except UnicodeDecodeError:
                        client.send('invalid_characters'.encode('ascii'))
                        continue

                    if not number:
                        client.send('invalid_length'.encode('ascii'))
                        continue

                    if not re.match(r'^(?!.*(.).*\1)\d{4}$', number):
                        client.send('invalid_code'.encode('ascii'))
                        continue

                    client.send('valid_wish'.encode('ascii'))

                    session_info[client]['code'] = number
                    clients[client]['state'] = 2

        if clients[client]['state'] == 2:  # Ожидание загадывания числа от опонента и определение первого угадывающего
            while True:
                with wait_lock:
                    if client.fileno == -1 or clients[client]['state'] != 2:
                        break

                    opponent = opponent_valid(client)
                    if not isinstance(opponent, socket.socket):
                        client.send('invalid_opponent'.encode('ascii'))
                        clients[client]['state'] = 4
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

                            order[0].send('first'.encode('ascii'))
                            order[1].send('second'.encode('ascii'))
                        break
        elif clients[client]['state'] == 3:  # Игра началась
            while True:
                with game_lock:
                    if client.fileno == -1 or clients[client]['state'] != 3:
                        break

                    client_info = session_info[client]

                    if not client_info['guessing']:
                        continue

                    number = client.recv(1024)

                    if number is False or number is None:
                        opponent.send('invalid_opponent'.encode('ascii'))
                        break

                    opponent = opponent_valid(client)
                    if not isinstance(opponent, socket.socket):
                        client.send('invalid_opponent'.encode('ascii'))
                        clients[client]['state'] = 4
                        break

                    opponent_info = session_info[opponent]

                    try:
                        number = number.decode('ascii')
                    except UnicodeDecodeError:
                        client.send('invalid_characters'.encode('ascii'))
                        continue

                    if not number or not re.match(r'^(?!.*(.).*\1)\d{4}$', number):
                        client.send('invalid_code'.encode('ascii'))
                        continue
                    client.send('valid_guess'.encode('ascii'))

                    bull, cow = 0, 0
                    opponent_number = opponent_info['code']

                    for i, digit in enumerate(number):
                        if digit in opponent_number and i == opponent_number.find(digit):
                            bull += 1
                        elif digit in opponent_number:
                            cow += 1

                    client.send(f"You: {number} | {bull} Bull | {cow} Cow".encode('ascii'))
                    opponent.send(f"{clients[client]['nickname']}: {number} | {bull} Bull | {cow} Cow".encode('ascii'))

                    if bull == 4:
                        clients[client]['state'] = 4
                        client.send('win'.encode('ascii'))
                        clients[opponent]['state'] = 4
                        opponent.send('lose'.encode('ascii'))
                        opponent.send(client_info['code'].encode('ascii'))
                        del session_info[opponent]
                        del session_info[client]
                        break
                    else:
                        client.send('wait'.encode('ascii'))
                        opponent.send('guess'.encode('ascii'))

                    session_info[client]['guessing'] = False
                    session_info[opponent]['guessing'] = True
        elif clients[client]['state'] == 4:  # После итога матча
            try:
                msg = client.recv(1024).decode('ascii')
            except ConnectionAbortedError:
                return
            if not msg:
                break
            if msg == 'search':
                clients[client]['state'] = 0
                free_players.append(client)


def serve():
    while True:
        client, address = server.accept()
        print("Connected with {}".format(str(address)))

        thread = threading.Thread(target=handle, args=(client,))
        thread.start()


if __name__ == '__main__':
    serve()
