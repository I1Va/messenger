import selectors
import socket
from datetime import datetime
import time
import hashlib
import random
import os
import signal
import pickle

###############################

server_ip = '192.168.0.76'
server_port = 7777
timeout_delay = 100 #Кол-во секунд, по прошествие которых клиент автоматически отключается
hashlib_usage = True #True = Использовать библиотеку hashlib для генерации хэшэй, False = использовать собственную функцию для генерации хэшэй. При изменении параметра данные в rooms.pkl, client_names.pkl сотрутся

###############################
def hash(a, R = 1791791791, P = 301):
    temp = 0
    print(a)
    for x in a:
       
        temp = (temp * P + ord(x)) % P
    return temp

def save_obj(obj, name ):
    with open('obj/'+ name + '.pkl', 'wb') as f:
        pickle.dump(obj, f, pickle.HIGHEST_PROTOCOL)

def load_obj(name):
    with open('obj/' + name + '.pkl', 'rb') as f:
        return pickle.load(f)

if len(open("obj/client_names.pkl").read()) == 0 or int(open("obj/hashstate").read()) != int(hashlib_usage):
    save_obj({}, "client_names")
if len(open("obj/rooms.pkl").read()) == 0 or int(open("obj/hashstate").read()) != int(hashlib_usage):
    save_obj({}, "rooms")

with open("obj/hashstate", "w") as F:
    F.write(str(int(hashlib_usage)))

sel = selectors.DefaultSelector()

delete = []

client_names = load_obj("client_names")
client_states = {}
addr_name = {}
all_clients = [] #(conn, ip) участников
trying = {}
times = {}
rooms = load_obj("rooms")



def handler(signum, frame):
    print("Exit, data has been saved")
    save_obj(client_names, "client_names")
    save_obj(rooms, "rooms")
    exit(0)

signal.signal(signal.SIGINT, handler)


def accept(sock, mask):
    conn, addr = sock.accept()  # Should be ready
    client_states[addr[0]] = "aut"
    print(f"{addr[0]} подключился")
    conn.setblocking(False)
    conn.send("Введите логин: ".encode())
    sel.register(conn, selectors.EVENT_READ, lambda x, y: read(addr, x, y))

def read(adress, conn, mask):
    global delete
   
    state = client_states[adress[0]]
    for x in delete:
        if x in times:
            times.pop(x)
    delete = []
    for key, value in times.items():
        if time.time() - value> timeout_delay:
            if key in trying:
                trying.pop(key)
            k = -10**9
            for i in range(len(all_clients)):
                if all_clients[i][1][0] == key:
                    k = i
                    break
            if k != - 10**9:
                all_clients.pop(k)

            if key in addr_name:
                addr_name.pop(key)
            if key in client_states:
                client_states.pop(key)
            conn.send("Timeout\n".encode())
            delete.append(key)
            sel.unregister(conn)
            conn.close()
            return 0
    if state == "aut":
        mes = conn.recv(1024).decode().rstrip()
        if mes != "":
            trying[adress[0]] = mes
            times[adress[0]] = time.time()
            if mes in client_names:
                conn.send("Введите пароль: ".encode())
                client_states[adress[0]] = "pas"
            else:
                conn.send("Данного логина не найдено, введите пароль дважды через пробел: ".encode())
                client_states[adress[0]] = "pasnew"
    elif state == "pas":
        mes = conn.recv(1024).decode().rstrip()
        if mes != "":
            times[adress[0]] = time.time()
            if hashlib_usage:
                password = hashlib.sha1(mes.encode()).hexdigest()
            else:
                password = hash(mes)
            if client_names[trying[adress[0]]] == password:
                conn.send("Аутентификация прошал успешно. Вы поключены к основному каналу  ".encode())
                client_states[adress[0]] = "main"
                addr_name[adress[0]] = trying.pop(adress[0])
            else:
                conn.send("вы не прошли аутентификацию".encode())
                client_states[adress[0]] = "aut"
                conn.close()
    elif state == "pasnew":
        mes = conn.recv(1024).decode().rstrip()
        if mes != "":
            mes = mes.split()
            times[adress[0]] = time.time()
            if len(mes) < 2:
                print("Введите пароль ДВАЖДЫ")
            elif mes[0] == mes[1]:
                
                if hashlib_usage:
                    password = hashlib.sha1(mes[0].encode()).hexdigest()
                else:
                    password = hash(mes[0])
                client_names[trying[adress[0]]] = password
                conn.send("Аутентификация прошал успешно. Вы поключены к основному каналу ".encode())
                client_states[adress[0]] = "main"
                addr_name[adress[0]] = trying.pop(adress[0])
                all_clients.append((conn, adress))
            else:
                conn.send("Пароли не совпадают. Повторите попытку: ".encode())
    else:
        mes = conn.recv(1024).decode()
        mes1 = f"{addr_name[adress[0]]} {datetime.now()} : {mes}"
        if mes != '':
            print(mes.rstrip())
            times[adress[0]] = time.time()
            if mes[0] == "/":
                mes = mes.split()
                if mes[0][1:] == "create":
                    print('create')
                    if len(mes) < 2:
                        conn.send("Некоректная команда\n".encode())
                    else:
                        room_name = mes[1]
                        if room_name in rooms:
                            conn.send("Имя комнаты занято\n".encode())
                        else:
                            password = str(random.randrange(1000, 10000))
                            if hashlib_usage:
                                rooms[room_name] = hashlib.sha1(password.encode()).hexdigest()
                            else:
                                rooms[room_name] = hash(password)
                            conn.send(f"Комната с именем <{room_name}> создана. Пароль от комнаты <{password}>\n".encode())
                            conn.send("Вы были автоматически перенаправлены в комнату\n".encode())
                            client_states[adress[0]] = "#" + room_name #К имени комнаты добавляется специальный символ, чтобы пользователь не смог сломать систему, выдав за свой статус название комнаты вида "pas, newpas, aut"
                elif mes[0][1:] == "join":
                    if len(mes) < 3:
                        conn.send("Некоректная команда\n".encode())
                    else:
                        room_name = mes[1]
                        if hashlib_usage:
                            password = hashlib.sha1(mes[2].encode()).hexdigest()
                        else:
                            password = hash(mes[2])
                        if room_name not in rooms:
                            conn.send(f"Комната {room_name} не существует\n".encode())
                        else:
                            if rooms[room_name] == password:
                                conn.send(f"Вы были успешно подключены к комнате {room_name}\n".encode())
                                client_states[adress[0]] = "#" + room_name
                                
                            else:
                                conn.send(f"Пароль от комнаты {room_name} некоректен\n".encode())
                elif mes[0][1:] == "exit":
                    conn.send(f"Вы были перенаправлены в общий канал\n".encode())
                    client_states[adress[0]] = "all_clients"
                else:
                    conn.send("Некоректная команда\n".encode())
            else:
                for client in all_clients:
                    if client_states[client[1][0]] == client_states[adress[0]] and client[0] != conn:
                        client[0].send(mes1.encode())

sock = socket.socket()
sock.bind((server_ip, server_port))
sock.listen(100)
sock.setblocking(False)
sel.register(sock, selectors.EVENT_READ, accept)
try:
    while True:
        events = sel.select()
        for key, mask in events:
            callback = key.data
            callback(key.fileobj, mask)

except Exception as ex:
    print(ex)
    print("data has been saved")
    save_obj(client_names, "client_names")
    save_obj(rooms, "rooms")
except KeyboardInterrupt:
    print("exit")
    print("data has been saved")
    save_obj(client_names, "client_names")
    save_obj(rooms, "rooms")
finally:
    sock.close()