import socket
import json
import time

# Wait for manager to start up
time.sleep(3)

from utils import (
    send_message,
    ok_request,
)

with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
    send_message(
        s,
        ("127.0.0.1", 5000),
        ok_request(
            "configure-dss",
            {
                "name": "my_dss",
                "num_disks": 3,
                "striping_unit": 1024,
            },
        ),
    )
