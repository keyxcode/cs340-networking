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
from datetime import datetime

CHUNK_SIZE = 1024
WINDOW_SIZE = 10
ACK_TIMEOUT = 0.2  # secs
BUSY_WAIT_SLEEP = 0.1

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

        # the following states are relevant when the socket is sending data
        self.send_queue = list()
        self.send_queue_lock = Lock()
        self.send_base = 0
        self.max_acked_seq = -1  # sent data has been acked up to this seq num
        self.next_send_seq = 0  # used to create packet seq num when add to send queue

        # the following states are relevant when the socket is receiving data
        self.received_packets = dict()
        self.received_packets_lock = Lock()
        self.last_inorder_received_seq = -1
        self.next_return_seq = 0  # seq num of data to return to socket client

        # the following states are relevant to closing the socket
        self.fin_acked = False  # socket has received an an ack for the fin it's sent
        self.closed = False  # socket has been closed

        # start the sender and receiver listener function in background threads
        self.send_thread = ThreadPoolExecutor(max_workers=1)
        self.send_thread.submit(self._transmit)
        self.listen_thread = ThreadPoolExecutor(max_workers=1)
        self.listen_thread.submit(self._listener)

    def send(self, data_bytes: bytes) -> None:
        """
        Chunks data into segments of CHUNK_SIZE and adds to the end of send_queue.

        Args:
            data_bytes: The data to be sent that may exceed one CHUNK_SIZE.
        """
        for i in range(0, len(data_bytes), CHUNK_SIZE):
            chunk = data_bytes[i : i + CHUNK_SIZE]
            packet = self._build_packet(self.next_send_seq, False, False, chunk)

            with self.send_queue_lock:
                self.send_queue.append(packet)
                self.next_send_seq += 1

    def recv(self) -> bytes:
        """
        Blocks until the packet with the next_return_seq is available.
        Increments next_return_seq upon successful retrieval.

        Returns:
            bytes: The data corresponding to the expected sequence number.
            The returned data may include multiple packets concatenated together.
        """
        while True:
            data = bytearray()

            while self.next_return_seq in self.received_packets:
                with self.received_packets_lock:
                    data.extend(self.received_packets.pop(self.next_return_seq))
                    self.next_return_seq += 1

            if data:
                return bytes(data)

            sleep(BUSY_WAIT_SLEEP)

    def close(self) -> None:
        """
        Blocks until all necessary ACKs are received, then initiates connection teardown:
        - Waits until all sent packets are acknowledged.
        - Sends a FIN packet and retransmits until a FIN-ACK is received.
        - Pauses briefly for potential final retransmissions before marking the socket as closed.

        Sets self.closed to terminate background processes.
        """
        while self.send_base != len(self.send_queue):
            self._log(
                f"SOCK: Can't close. Only received ACK up to {self.send_base - 1} / {len(self.send_queue) - 1}"
            )
            sleep(BUSY_WAIT_SLEEP)

        self._log("SOCK: Initiating connectinon teardown")

        fin_packet = self._build_packet(0, False, True)
        self.socket.sendto(fin_packet, self.dest)
        self._log("SOCK: Sending FIN")

        # resend fin until having received fin ack using stop and wait
        self._retransmit_until(fin_packet, lambda: self.fin_acked)
        self._log("SOCK: Received FIN-ACK")

        sleep(2)  # wait in case the other side socket needs this side to resend fin ack
        self._log("SOCK: Closing...")
        self.closed = True  # this will stop the transmit and listener background tasks as a side effect
        self.socket.stoprecv()

    def _transmit(self) -> None:
        """
        Transmits packets from the send_queue continuously in a background thread until the socket is closed.

        Follows the Go-Back-N protocol to manage packet transmission.
        Resend all packets that have not yet been acknowledged in the current window.
        """
        self._log("SOCK: Started transmit thread")

        while not self.closed:
            self.send_base = self.max_acked_seq + 1

            # transmit all packets in the window
            send_queue_len = len(self.send_queue)
            for i in range(WINDOW_SIZE):
                packet_i = self.send_base + i
                if packet_i < send_queue_len:
                    self.socket.sendto(self.send_queue[packet_i], self.dest)
                    self._log(f"SOCK: Sending packet {packet_i}")

            # timeout, after which we'll check for newly acked packets and retransmit if needed
            sleep(ACK_TIMEOUT)

        self.send_thread.shutdown()

    def _listener(self) -> None:
        """
        Listens for incoming packets in a background thread and processes them until the socket is closed.

        Continuously receives packets from the socket and performs the following actions:
        - Validates the hash.
        - Processes FIN-ACK, ACK, FIN, and data packets differently.
        - Updates internal state as necessary.
        - Sends acknowledgments for data and FIN packets.
        """
        self._log("SOCK: Started listener thread")

        while not self.closed:
            try:
                packet, _ = self.socket.recvfrom()

                # extract hash from the received packet for validation
                expected_hash = packet[:HASH_SIZE]
                packet_no_hash = packet[HASH_SIZE:]
                if not self._verify_hash(packet_no_hash, expected_hash):
                    continue

                seq_num, is_ack, is_fin, data = self._unpack_packet(packet_no_hash)

                # process different types of packet differently
                if is_ack and is_fin:  # fin-ack
                    self.fin_acked = True
                    self._log("SOCK: Received FIN-ACK")

                elif is_ack:  # data ack
                    self.max_acked_seq = max(self.max_acked_seq, seq_num)
                    self._log(
                        f"SOCK: Received ACK for up to packet {self.max_acked_seq} / {len(self.send_queue) - 1}"
                    )

                elif is_fin:  # fin
                    fin_ack = self._build_packet(0, True, True)
                    self.socket.sendto(fin_ack, self.dest)
                    self._log("SOCK: Received FIN. Sending FIN-ACK")

                else:  # data packet
                    # only accept in order packet
                    if seq_num == self.last_inorder_received_seq + 1:
                        with self.received_packets_lock:
                            self.received_packets[seq_num] = data
                        self.last_inorder_received_seq = seq_num
                        self._log(f"SOCK: Received packet {seq_num}")
                    else:
                        self._log(f"SOCK: Discarded out of order packet {seq_num}")

                    self._log(
                        f"SOCK: Sending ACK for packet {self.last_inorder_received_seq}"
                    )
                    ack = self._build_packet(
                        self.last_inorder_received_seq, True, False
                    )
                    self.socket.sendto(ack, self.dest)
            except Exception as e:
                self._log("SOCK: Listener died!", e)

        self.listen_thread.shutdown()

    def _retransmit_until(
        self,
        packet: bytes,
        should_stop: Callable[[], bool],
        timeout: int = ACK_TIMEOUT,
    ) -> None:
        """
        Retransmits a packet until the stop condition is met.

        Args:
            packet: Packet to retransmit.
            should_stop: Callable that returns True to stop retransmission.
            timeout: Interval (in seconds) between retransmissions.
        """
        start_time = time()
        while not should_stop():
            self._log("SOCK: Resending...")
            if time() - start_time > ACK_TIMEOUT:
                self.socket.sendto(packet, self.dest)
                start_time = time()
            sleep(timeout)

    def _unpack_packet(self, packet: bytes) -> tuple[int, bool, bool, bytes]:
        """
        Unpacks the header and data from a packet without its hash.

        Args:
            packet: Packet with header and data, excluding the hash.

        Returns:
            Tuple of sequence number, ACK flag, FIN flag, and data payload.
        """
        header = packet[:HEADER_NO_HASH_SIZE]
        data = packet[HEADER_NO_HASH_SIZE:]
        seq_num, is_ack, is_fin = struct.unpack(HEADER_NO_HASH_FORMAT, header)

        return seq_num, is_ack, is_fin, data

    def _build_packet(
        self, seq_num: int, is_ack: bool, is_fin: bool, data: Optional[bytes] = b""
    ) -> bytes:
        """
        Constructs a packet with header, data, and hash for integrity verification.

        Args:
            seq_num: Non negative sequence number for the packet.
            is_ack: If this packet sends acknowledgement of receiving data.
            is_fin: If this packet signals the end of transmission.
            data: Optional data payload.

        Returns:
            The complete packet with a hash prepended to the header and data.
        """
        try:
            header_no_hash = struct.pack(HEADER_NO_HASH_FORMAT, seq_num, is_ack, is_fin)
            packet_no_hash = header_no_hash + data
            digest = self._calculate_hash(packet_no_hash)

            return digest + packet_no_hash
        except Exception as e:
            raise RuntimeError(f"Failed to build packet: {e}")

    def _calculate_hash(self, data: bytes) -> bytes:
        """Calculates MD5 hash of some bytes data."""
        return md5(data).digest()

    def _verify_hash(self, data: bytes, expected_hash: bytes) -> bool:
        """Verifies data integrity by comparing the calculated hash to the expected hash."""
        return self._calculate_hash(data) == expected_hash

    def _log(self, *args) -> None:
        print(datetime.now().strftime("[%M:%S:%f]"), *args)
