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
        packets.append(packet)
        print_err((f"[Packet {count}]: {len(packet)} bytes"))
        count += 1

        if b"\r\n\r\n" in packet:
            break

    response = b"".join(packets)
    print_err(f"Received {len(response)} bytes")
    print_br()

    return response
