from utils import print_err, print_br
from socket import socket


def receive_all(s: socket) -> bytes:
    """
    Receives all data from the socket and returns it as a single byte string.
    """

    packets = list()
    count = 0

    print_err("Receiving data...")
    while True:
        packet = s.recv(4096)
        if not packet:
            break

        print_err((f"[Packet {count}]: {len(packet)} bytes"))
        packets.append(packet)
        count += 1

    response = b"".join(packets)
    print_err(f"Received {len(response)} bytes")
    print_br()

    return response
