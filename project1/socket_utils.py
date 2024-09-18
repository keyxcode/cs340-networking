from utils import print_err, print_br
from socket import socket


def receive_all(s: socket) -> bytes:
    """
    Receives all data from the socket and returns it as a single byte string.
    """

    # bytearray (muteable) allows us to append new packets more efficiently
    # than adding new packets directly to immuteable bytes object using +=
    data = bytearray()
    count = 0

    print_err("Receiving data...")
    while True:
        packet = s.recv(4096)
        data.extend(packet)
        print_err((f"[Packet {count}]: {len(packet)} bytes - {packet}"))
        count += 1

        if not packet or b"\r\n\r\n" in data:
            break

    print_err(f"Received {len(data)} bytes")
    print_br()

    return bytes(data)
