import pickle
import socket

data_type_miner = ["add block", "add transaction", "remove transaction", "block validation", "remove block", "remove transaction list"]
miner_server_port = 9000
         
def send_data_to_miner_servers(data):
    server_ip = '0.0.0.0' #put your ip here

    server_address = (server_ip, miner_server_port)

    try:
        client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client.connect(server_address)
        
        # Serialize the data
        serialized_data = pickle.dumps(data)
        client.sendall(serialized_data)
        
        client.close()
    except ConnectionRefusedError:
        exit()
