# skeleton code provided by prof. Steve Tarzia: https://github.com/starzia/reliable-transport-sim

# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP

# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY

import struct

CHUNK_SIZE = 1024
HEADER_FORMAT = "<I"  # little eldian 4-byte unsigned int


class Streamer:
    def __init__(self, dst_ip, dst_port, src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
        and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port

        self.send_seq_num = 0

        self.recv_buffer = dict()
        self.expected_seq_num = 0

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""

        for i in range(0, len(data_bytes), CHUNK_SIZE):
            # use struct to ensure the header created with seq_num always stays in HEADER_FORMAT
            header = struct.pack(HEADER_FORMAT, self.send_seq_num)
            full_packet = header + data_bytes[i : i + CHUNK_SIZE]
            self.socket.sendto(full_packet, (self.dst_ip, self.dst_port))
            self.send_seq_num += 1

    def recv(self) -> bytes:
        """Blocks (waits) until the expected sequence number is received.
        Handles out-of-order packet reception using a receive buffer.
        Returns the data corresponding to the expected sequence number."""
        while self.expected_seq_num not in self.recv_buffer:
            packet, addr = self.socket.recvfrom()
            header_size = struct.calcsize(HEADER_FORMAT)
            header = packet[:header_size]
            data = packet[header_size:][:]
            seq_num = struct.unpack(HEADER_FORMAT, header)[0]
            self.recv_buffer[seq_num] = data

        res = self.recv_buffer[self.expected_seq_num]
        del self.recv_buffer[self.expected_seq_num]
        self.expected_seq_num += 1
        return res

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
        the necessary ACKs and retransmissions"""
        # your code goes here, especially after you add ACKs and retransmissions.
        pass
