import pickle
import socket
import threading
import sqlite3
import logging
from database import Database
from keys import key_file_path
from notifications import notification

# Configure logging
logging.basicConfig(level=logging.INFO)

db = Database()

data_type_wallet = ["new user", "update password", "update username", "add notification", "add notification to all users"]
wallet_server_port = 8000
server = None
stop_server_thread = False
server_lock = threading.Lock()
server_ip = '0.0.0.0'

def setup_server():
    global server
    try:
        server_address = (server_ip, wallet_server_port)  

        if server is not None:
            server.close()

        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(server_address)
        server.listen()
        return server
        
    except OSError:
        logging.error("Error setting up the server")
        exit()

def start_wallet_server():
    global server, stop_server_thread
    server = setup_server()
    if server is None:
        logging.error("Failed to set up a server.")
        return

    while True:
        if stop_server_thread:
            break
        
        with server_lock:
            try:
                client_socket, address = server.accept()
            except OSError as e:
                continue
        thread = threading.Thread(target=handle_client, args=(client_socket, address))
        thread.start()

def handle_client(conn, addr):
    try:
        received_data = conn.recv(8888)
        if received_data:
            unpickled_data = pickle.loads(received_data)
            if unpickled_data[0][0] == data_type_wallet[0]:
                new_user(unpickled_data[0][1], unpickled_data[0][2], unpickled_data[0][3], unpickled_data[0][4], unpickled_data[0][5], unpickled_data[0][6])
            elif unpickled_data[0][0] == data_type_wallet[1]:
                update_password(unpickled_data[0][1], unpickled_data[0][2])
            elif unpickled_data[0][0] == data_type_wallet[2]:
                update_username(unpickled_data[0][1], unpickled_data[0][2])
            elif unpickled_data[0][0] == data_type_wallet[3]:
                add_notification(unpickled_data[0][1], unpickled_data[0][2])
            elif unpickled_data[0][0] == data_type_wallet[4]:
                add_notification_to_all_users(unpickled_data[0][1], unpickled_data[0][2] if len(unpickled_data[0]) > 2 else None)
    except pickle.UnpicklingError as e:
        logging.error(f"Error in data from {addr}: {e}")
    except Exception as e:
        logging.error(f"Error handling client {addr}: {e}")
    finally:
        conn.close()

def new_user(username, password, private_key, public_key, phrase, key_encryption):
    # add new user to local database
    try: 
        with open(key_file_path, "w") as key_file:
            key_file.write(key_encryption)
    except Exception as e:
        print("Exception: " + str(e))
        return ""
    try:
        db.execute('INSERT INTO users (username, password, privatekey, publickey, phrase) VALUES (?, ?, ?, ?, ?)', (username, password, private_key, public_key, phrase))
    except sqlite3.Error as e:
        print(f"Database error: {e}")
        return

def update_password(user, new_password):
    # update password in local database
    try:
        db.execute('UPDATE users SET password=? WHERE username=?', (new_password, user))
    except sqlite3.Error as e:
        print(f"Database error: {e}")

def update_username(user, new_username):
    # update username in local database
    try:
        db.execute('UPDATE users SET username=? WHERE username=?', (new_username, user))
    except sqlite3.IntegrityError:
        print('Username is already taken')

def add_notification(user, message):
    notification.add_notification(user, message)

def add_notification_to_all_users(message, exclude_user=None):
    notification.add_notification_to_all_users(message, exclude_user)

def get_all_users():
        results = db.fetch("SELECT username FROM users")
        return [result[0] for result in results] if results else []

def handle_wallet_termination_server():
    global stop_server_thread
    stop_server_thread = True

    if server:
        try:
            server.close()  # Close the server socket
        except Exception as e:
            print(f"Error closing server: {e}")