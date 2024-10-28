# skeleton code provided by prof. Steve Tarzia: https://github.com/starzia/reliable-transport-sim

# do not import anything else from loss_socket besides LossyUDP
from lossy_socket import LossyUDP

# do not import anything else from socket except INADDR_ANY
from socket import INADDR_ANY

import struct
from concurrent.futures import ThreadPoolExecutor
from threading import Lock
from time import sleep, time
from hashlib import md5
from typing import Optional, Callable
from collections import deque
from bisect import bisect_left

CHUNK_SIZE = 1024
ACK_TIMEOUT = 0.25  # secs

# HEADER_NO_HASH_FORMAT: big eldian
# 4-byte unsigned int data
# 2 bool bytes: ACK flag and FIN flag
HEADER_NO_HASH_FORMAT = ">I2?"
HEADER_NO_HASH_SIZE = struct.calcsize(HEADER_NO_HASH_FORMAT)
# technically, the header includes the hash as well
# but in practice, we calculate the hash based on the rest of the header + the data
# and finally add it to the beginning of the packet
HASH_SIZE = 16  # md5 hash is 16 bytes
HEADER_SIZE = HASH_SIZE + HEADER_NO_HASH_SIZE


class Streamer:
    def __init__(self, dst_ip, dst_port, src_ip=INADDR_ANY, src_port=0):
        """Default values listen on all network interfaces, chooses a random source port,
        and does not introduce any simulated packet loss."""
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.dest = (self.dst_ip, self.dst_port)

        self.closed = False
        # start the receiver listener function in a background thread
        self.executor = ThreadPoolExecutor(max_workers=1)
        self.executor.submit(self._listener)

        self.fin_acked = False

        # we've received ack up to this number - 1
        # when resending packets, we start from this number
        self.acked_up_to = 0

        self.send_buffer = deque()  # data will go here first, then to send_queue
        self.send_buffer_lock = Lock()
        self.send_queue = list()  # data will be sent from here
        self.send_queue_lock = Lock()
        self.send_seq_num = 0  # seq num of the next packet to be sent
        self.send_thread = ThreadPoolExecutor(max_workers=1)
        self.send_thread.submit(self._send_from_send_queue)

        self.recv_buffer = dict()
        self.recv_buffer_lock = Lock()
        self.expected_recv_seq_num = 0

    def send(self, data_bytes: bytes) -> None:
        """Note that data_bytes can be larger than one packet."""
        for i in range(0, len(data_bytes), CHUNK_SIZE):
            data = data_bytes[i : i + CHUNK_SIZE]
            packet = self._build_packet(self.send_seq_num, False, False, data)
            with self.send_buffer_lock:
                self.send_buffer.append((self.send_seq_num, packet))
                self.send_seq_num += 1

    def _send_from_send_queue(self) -> None:
        while not self.closed:
            # find the idx of the first element in the send queue that has seq num <= ack num
            acked_idx = bisect_left(
                self.send_queue, self.acked_up_to, key=lambda x: x[0]
            )
            with self.send_queue_lock and self.send_buffer_lock:
                # remove packets in send queue that have seq num less than ack up to seq num
                self.send_queue = self.send_queue[acked_idx:]

                # if we dont have enough packets in send queue now, add more from send buffer
                while len(self.send_queue) < 20 and self.send_buffer:
                    self.send_queue.append(self.send_buffer.popleft())
                # print([e[0] for e in self.send_queue])

            # send all packets
            for _, packet in self.send_queue:
                self.socket.sendto(packet, self.dest)

            # timeout
            sleep(0.01)

    def recv(self) -> bytes:
        """Blocks (waits) until the expected sequence number is received.
        Handles out-of-order packet reception using a receive buffer.
        Returns the data corresponding to the expected sequence number."""
        while True:
            if self.expected_recv_seq_num in self.recv_buffer:
                with self.recv_buffer_lock:
                    res = self.recv_buffer.pop(self.expected_recv_seq_num)
                    return res

            sleep(0.01)

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
        the necessary ACKs and retransmissions"""
        # when doing stop and wait, when we call close() we're guaranteed to have received all the ACKs
        # but in the future when doing other implementations, we may have to check for this
        # print("CLOSINGGGG", self.acked_up_to, self.send_seq_num)
        while self.acked_up_to < self.send_seq_num - 1:
            sleep(0.1)

        fin_packet = self._build_packet(self.expected_recv_seq_num, False, True)
        self.socket.sendto(fin_packet, self.dest)
        print("Sending FIN")

        # resend ack until having received fin ack
        self._retransmit_until(fin_packet, lambda: self.fin_acked)

        sleep(2)  # wait for 2 secs according to the assignment requirements

        self.closed = True  # as a side effect will stop the packet listener
        self.socket.stoprecv()

    def _retransmit_until(self, packet: bytes, should_stop: Callable[[], bool]) -> None:
        start_time = time()
        while not should_stop():
            if time() - start_time > ACK_TIMEOUT:
                self.socket.sendto(packet, self.dest)
                start_time = time()
            sleep(0.01)  # reduce busy waiting

    def _listener(self) -> None:
        while not self.closed:
            try:
                packet, _ = self.socket.recvfrom()
                expected_hash = packet[:HASH_SIZE]
                packet_no_hash = packet[HASH_SIZE:]
                if not self._is_valid_hash(packet_no_hash, expected_hash):
                    continue

                seq_num, is_ack, is_fin, data = self._unpack_packet(packet_no_hash)
                if is_ack and is_fin:  # fin-ack
                    self.fin_acked = True
                    print("Received FIN-ACK")
                elif is_ack:  # is data ack
                    if seq_num > self.acked_up_to:
                        self.acked_up_to = seq_num
                    print(f"sucessfully sent up to {self.acked_up_to - 1}")
                elif is_fin:  # fin
                    fin_ack = self._build_packet(self.send_seq_num, True, True)
                    self.socket.sendto(fin_ack, self.dest)
                    print("Received FIN, sending FIN-ACK")
                else:  # data packet
                    if seq_num not in self.recv_buffer:
                        with self.recv_buffer_lock:
                            self.recv_buffer[seq_num] = data
                        # self.expected_recv_seq_num += 1
                    print(f"expect {self.expected_recv_seq_num} next")
                    if seq_num == self.expected_recv_seq_num:
                        # have received up to expected_recv_seq_num
                        self.expected_recv_seq_num += 1
                    ack = self._build_packet(self.expected_recv_seq_num, True, False)
                    self.socket.sendto(ack, self.dest)
            except Exception as e:
                print("listener died!", e)

        self.executor.shutdown()

    def _unpack_packet(self, packet_no_hash: bytes) -> tuple[int, bool, bool, bytes]:
        header = packet_no_hash[:HEADER_NO_HASH_SIZE]
        data = packet_no_hash[HEADER_NO_HASH_SIZE:][:]
        seq_num, is_ack, is_fin = struct.unpack(HEADER_NO_HASH_FORMAT, header)

        return seq_num, is_ack, is_fin, data

    def _build_packet(
        self, seq_num: int, is_ack: bool, is_fin: bool, data: Optional[bytes] = b""
    ) -> bytes:
        header_without_hash = struct.pack(
            HEADER_NO_HASH_FORMAT, seq_num, is_ack, is_fin
        )
        packet_without_hash = header_without_hash + data
        digest = self._calculate_hash(packet_without_hash)
        packet = digest + packet_without_hash

        return packet

    def _calculate_hash(self, data: bytes) -> bytes:
        return md5(data).digest()

    def _is_valid_hash(self, data: bytes, expected_hash: bytes) -> bool:
        return self._calculate_hash(data) == expected_hash
