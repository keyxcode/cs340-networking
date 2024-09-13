from utils import print_err, print_br
from socket import socket


def receive_all(s: socket, header_mode: bool = False) -> bytes:
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

        # header_mode means we're only detecting the end of the headers
        # => useful for when servers detect the end of GET requests, because they don't include any body
        # if header_mode is False, break only at the end of the data stream
        if header_mode and b"\r\n\r\n" in packet:
            break
        elif not packet:
            break

    response = b"".join(packets)
    print_err(f"Received {len(response)} bytes")
    print_br()

    return response
