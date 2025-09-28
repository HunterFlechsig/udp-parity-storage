import socket;
import json;

HOST = '127.0.0.1';
PORT = 65432;

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    data = {
        "type": "register-user",
        "data": {
            "user-name": "testuser",
            "Ipv4": "127.0.0.1",
            "m-port": 65432,
            "c-port": 65433
        }
    }
    s.sendto(json.dumps(data).encode(), (HOST, PORT));
    data, addr = s.recvfrom(1024);

print(f"Received {data!r}");