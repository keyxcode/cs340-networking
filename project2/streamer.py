# skeleton code provided by prof. Steve Tarzia: https://github.com/starzia/reliable-transport-sim

# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP

# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY

import struct
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep, time
from typing import Optional

CHUNK_SIZE = 1024
ACK_TIMEOUT = 0.25  # seconds

# HEADER_FORMAT: big eldian
# 4-byte unsigned int data
# 1 byte bool ACK flag
HEADER_FORMAT = ">I??"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)


class Streamer:
    def __init__(self, dst_ip, dst_port, src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
        and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port

        # seq num of the next packet to be sent
        self.send_seq_num = 0

        self.recv_buffer = dict()
        self.recv_buffer_lock = Lock()
        self.expected_seq_num = 0

        self.closed = False
        # start the listener function in a background thread
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.executor.submit(self._listener)

        # a var storing the seq num of the latest ack package
        # should match the send_seq_num for a send action to be considered complete
        self.ack_num = -1

        self.fin_received = False

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""

        for i in range(0, len(data_bytes), CHUNK_SIZE):
            data = data_bytes[i : i + CHUNK_SIZE]
            packet = self._build_packet(self.send_seq_num, False, False, data)
            self.socket.sendto(packet, (self.dst_ip, self.dst_port))

            # wait for ack for ACK_TIME secs
            start_time = time()
            while self.ack_num != self.send_seq_num:
                if time() - start_time > ACK_TIMEOUT:  # resend packet
                    self.socket.sendto(packet, (self.dst_ip, self.dst_port))
                    start_time = time()
                sleep(0.01)  # reduce busy waiting

            self.send_seq_num += 1

    def recv(self) -> bytes:
        """Blocks (waits) until the expected sequence number is received.
        Handles out-of-order packet reception using a receive buffer.
        Returns the data corresponding to the expected sequence number."""
        while True:
            if self.expected_seq_num in self.recv_buffer:
                with self.recv_buffer_lock:
                    res = self.recv_buffer.pop(self.expected_seq_num)
                    self.expected_seq_num += 1
                    return res

            sleep(0.01)

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
        the necessary ACKs and retransmissions"""
        # when doing stop and wait, when we call close() we're guaranteed to have received all the ACKs
        # but in the future when doing other implementations, we may have to check for this
        # fin_packet = self._build_packet(self.expected_seq_num, True, True)

        self.closed = True  # as a side effect will stop the packet listener
        self.socket.stoprecv()

    def _listener(self) -> None:
        while not self.closed:
            try:
                ack_packet, addr = self.socket.recvfrom()
                seq_num, is_ack, is_fin, data = self._unpack_packet(ack_packet)
                if is_ack:  # received ack packet
                    self.ack_num = seq_num
                else:  # received data packet
                    with self.recv_buffer_lock:
                        self.recv_buffer[seq_num] = data
                    # send ack for the packet just received
                    ack_packet = self._build_packet(seq_num, True, False)
                    self.socket.sendto(ack_packet, (self.dst_ip, self.dst_port))
            except Exception as e:
                print("listener died!", e)

        self.executor.shutdown()

    def _unpack_packet(self, packet: bytes) -> tuple[int, bool, bool, bytes]:
        header = packet[:HEADER_SIZE]
        data = packet[HEADER_SIZE:][:]
        seq_num, is_ack, is_fin = struct.unpack(HEADER_FORMAT, header)

        return seq_num, is_ack, is_fin, data

    def _build_packet(
        self, seq_num: int, is_ack: bool, is_fin: bool, data: Optional[bytes] = b""
    ) -> bytes:
        header = struct.pack(HEADER_FORMAT, seq_num, is_ack, is_fin)
        packet = header + data

        return packet
