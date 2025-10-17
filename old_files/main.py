import socket
import json
import time

# Wait for manager to start up
time.sleep(3)

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    message = {
        "type": "configure-dss",
        "data": {
            "dss-name": "dss1",
            "n": 3,
            "striping-unit": 16384
        }
    }
    s.sendto(json.dumps(message).encode(), ("127.0.0.1", 31500))
    print("Sent configure-dss message to manager")
