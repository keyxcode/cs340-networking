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
ACK_TIMEOUT = 0.01  # secs
WINDOW_SIZE = 20

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
    def __init__(
        self, dst_ip: str, dst_port: int, src_ip: str = INADDR_ANY, src_port: int = 0
    ):
        """
        Initializes the Streamer for sending and receiving data.

        Args:
            dst_ip: IP address to send data to.
            dst_port: Destination port for data transmission.
            src_ip: Source IP address. Defaults to INADDR_ANY (listen on all network interfaces).
            src_port: Source port. Defaults to 0.
        """
        self.socket = LossyUDP()
        self.socket.bind((src_ip, src_port))
        self.dst_ip = dst_ip
        self.dst_port = dst_port
        self.dest = (self.dst_ip, self.dst_port)

        # data submitted to recv() will go to send_buffer first
        # then moved to send_queue when it's ready to be sent over the network
        self.chunk_buffer = deque()
        self.chunk_buffer_lock = Lock()
        self.transmit_queue = list()
        self.transmit_queue_lock = Lock()
        self.send_seq = 0  # seq num of the next packet to send

        # we've received ack for data packet up to this seq num - 1
        # when resending packets, start from this seq num
        self.next_unacked_seq = 0

        # incoming data will be stored in the received_packets, even if not it didn't come in order
        self.received_packets = dict()
        self.received_packets_lock = Lock()
        self.expected_seq = 0  # seq num of the next packet we expect to receive

        self.fin_acked = False  # socket has received an an ack for the fin it's sent
        self.closed = False  # socket has been closed

        # start the sender and receiver listener function in background threads
        self.send_thread = ThreadPoolExecutor(max_workers=1)
        self.send_thread.submit(self._send_from_send_queue)
        self.listen_thread = ThreadPoolExecutor(max_workers=1)
        self.listen_thread.submit(self._listener)

    def send(self, data_bytes: bytes) -> None:
        """
        Chunks data into segments of CHUNK_SIZE and stores each with a unique sequence number in the chunk_buffer.

        Args:
            data_bytes: The data to be sent that may exceed one CHUNK_SIZE.
        """

        for i in range(0, len(data_bytes), CHUNK_SIZE):
            chunk = data_bytes[i : i + CHUNK_SIZE]
            packet = self._build_packet(self.send_seq, False, False, chunk)

            with self.chunk_buffer_lock:
                self.chunk_buffer.append((self.send_seq, packet))
                self.send_seq += 1

    def recv(self) -> bytes:
        """
        Blocks until the packet with the expected sequence number (expected_seq) is received.
        Handles out-of-order packets by placing them in the received_packets buffer.
        Data is returned in order, incrementally, as expected_seq is always incremented upon successful retrieval.

        Returns:
            bytes: The data corresponding to the expected sequence number.
        """
        while True:
            if self.expected_seq in self.received_packets:
                with self.received_packets_lock:
                    packet_data = self.received_packets.pop(self.expected_seq)
                    self.expected_seq += 1
                    return packet_data

            sleep(0.01)  # reduce busy waiting

    def close(self) -> None:
        """Cleans up. It should block (wait) until the Streamer is done with all
        the necessary ACKs and retransmissions"""
        # when doing stop and wait, when we call close() we're guaranteed to have received all the ACKs
        # but in the future when doing other implementations, we may have to check for this
        # print("CLOSINGGGG", self.acked_up_to, self.send_seq_num)
        while self.next_unacked_seq < self.send_seq - 1:
            sleep(0.01)

        fin_packet = self._build_packet(self.expected_seq, False, True)
        self.socket.sendto(fin_packet, self.dest)
        print("Sending FIN")

        # resend ack until having received fin ack
        self._retransmit_until(fin_packet, lambda: self.fin_acked)

        sleep(2)  # wait for 2 secs according to the assignment requirements

        self.closed = True  # as a side effect will stop the packet listener
        self.socket.stoprecv()

    def _send_from_send_queue(self) -> None:
        while not self.closed:
            # find the idx of the first element in the send queue that has seq num <= ack num
            acked_idx = bisect_left(
                self.transmit_queue, self.next_unacked_seq, key=lambda x: x[0]
            )
            with self.transmit_queue_lock and self.chunk_buffer_lock:
                # remove packets in send queue that have seq num less than ack up to seq num
                self.transmit_queue = self.transmit_queue[acked_idx:]

                # if we dont have enough packets in send queue now, add more from send buffer
                while len(self.transmit_queue) < WINDOW_SIZE and self.chunk_buffer:
                    self.transmit_queue.append(self.chunk_buffer.popleft())
                # print([e[0] for e in self.send_queue])

            # (re)send all packets
            for _, packet in self.transmit_queue:
                self.socket.sendto(packet, self.dest)

            # timeout
            sleep(ACK_TIMEOUT)

        self.send_thread.shutdown()

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
                    if seq_num >= self.next_unacked_seq:
                        self.next_unacked_seq = seq_num
                    print(f"sucessfully sent up to {self.next_unacked_seq - 1}")
                elif is_fin:  # fin
                    fin_ack = self._build_packet(self.send_seq, True, True)
                    self.socket.sendto(fin_ack, self.dest)
                    print("Received FIN, sending FIN-ACK")
                else:  # data packet
                    if seq_num not in self.received_packets:
                        with self.received_packets_lock:
                            self.received_packets[seq_num] = data
                        # self.expected_recv_seq_num += 1
                    # print(f"expect {self.expected_recv_seq_num} next")
                    ack = self._build_packet(self.expected_seq, True, False)
                    self.socket.sendto(ack, self.dest)
            except Exception as e:
                print("listener died!", e)

        self.listen_thread.shutdown()

    def _retransmit_until(self, packet: bytes, should_stop: Callable[[], bool]) -> None:
        start_time = time()
        while not should_stop():
            if time() - start_time > ACK_TIMEOUT:
                self.socket.sendto(packet, self.dest)
                start_time = time()
            sleep(0.01)

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
