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
from bisect import bisect_right

CHUNK_SIZE = 1024
ACK_TIMEOUT = 0.1  # secs
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

        # the following states are relevant when the socket is transmitting data
        # data submitted to recv() will first go to send_buffer
        self.chunk_buffer = deque()
        self.chunk_buffer_lock = Lock()
        # then moved to send_queue when it's ready to be sent over the network
        self.send_queue = list()
        self.send_queue_lock = Lock()
        self.next_send_seq = 0
        self.max_acked_seq = -1  # sent data has been acked up to this seq num

        # the following states are relevant when the socket is receiving data
        # incoming data will be stored in the received_packets, even if it didn't come in order
        self.received_packets = dict()
        self.received_packets_lock = Lock()
        self.last_inorder_received_seq = -1

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
        Chunks data into segments of CHUNK_SIZE and stores each with a unique sequence number in the chunk_buffer.

        Args:
            data_bytes: The data to be sent that may exceed one CHUNK_SIZE.
        """
        for i in range(0, len(data_bytes), CHUNK_SIZE):
            chunk = data_bytes[i : i + CHUNK_SIZE]
            packet = self._build_packet(self.next_send_seq, False, False, chunk)

            with self.chunk_buffer_lock:
                # storing the packet with the send_seq explicitly will help later in the transmit process
                # when we need to do binary search
                self.chunk_buffer.append((self.next_send_seq, packet))
                self.next_send_seq += 1

    def recv(self) -> bytes:
        """
        Blocks until the packet with the next in order sequence number (last_inorder_received_seq + 1) is available.
        Increments last_inorder_received_seq upon successful retrieval.

        Returns:
            bytes: The data corresponding to the expected sequence number.
        """
        while True:
            if self.last_inorder_received_seq + 1 in self.received_packets:
                if self.received_packets_lock:
                    self.last_inorder_received_seq += 1
                    packet_data = self.received_packets.pop(
                        self.last_inorder_received_seq
                    )
                    return packet_data

            sleep(0.01)  # reduce busy waiting

    def close(self) -> None:
        """
        Blocks until all necessary ACKs are received, then initiates connection teardown:
        - Waits until all sent packets are acknowledged.
        - Sends a FIN packet and retransmits until a FIN-ACK is received.
        - Pauses briefly for potential final retransmissions before marking the socket as closed.

        Sets self.closed to terminate background processes.
        """
        while self.max_acked_seq != self.next_send_seq - 1:
            sleep(0.01)

        fin_packet = self._build_packet(self.last_inorder_received_seq, False, True)
        self.socket.sendto(fin_packet, self.dest)
        print("Sending FIN")

        # resend fin until having received fin ack using stop and wait
        self._retransmit_until(fin_packet, lambda: self.fin_acked)

        sleep(2)  # wait in case the other side socket needs this side to resend fin ack

        self.closed = True  # this will stop the transmit and listener background tasks as a side effect
        self.socket.stoprecv()

    def _transmit(self) -> None:
        """
        Transmits packets from the transmit queue continuously in a background thread until the socket is closed.

        Follows the Go-Back-N protocol to manage packet transmission.
        Processes the transmit queue to resend all packets that have not yet been acknowledged.
        If the queue has fewer packets than the defined window size, additional packets are added from the chunk buffer.
        """

        while not self.closed:
            # find the idx of the first element in the transmit queue that hasn't been acked
            # aka the element right after the one that has seq num == max_acked_seq
            first_unacked_idx = bisect_right(
                self.send_queue, self.max_acked_seq, key=lambda x: x[0]
            )

            with self.send_queue_lock and self.chunk_buffer_lock:
                # remove packets that have been acked from the transmit queue
                self.send_queue = self.send_queue[first_unacked_idx:]

                # if there're less packets in the queue than the window size, add more from send buffer
                while len(self.send_queue) < WINDOW_SIZE and self.chunk_buffer:
                    self.send_queue.append(self.chunk_buffer.popleft())

            # transmit all packets in the transmit queue
            for _, packet in self.send_queue:
                self.socket.sendto(packet, self.dest)

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
                    print("Received FIN-ACK")

                elif is_ack:  # data ack
                    self.max_acked_seq = max(self.max_acked_seq, seq_num)
                    print(f"Received ACK for up to packet {self.max_acked_seq}")

                elif is_fin:  # fin
                    fin_ack = self._build_packet(self.next_send_seq, True, True)
                    self.socket.sendto(fin_ack, self.dest)
                    print("Received FIN, sending FIN-ACK")

                else:  # data packet
                    # a true Go-Back-N implementation would discard any out of order packets
                    # meaning we'll have to use this condition: if seq_num == self.expected_seq
                    # here we're storing the packets anyway if we haven't received it
                    # => improve runtime at the cost of space
                    if seq_num not in self.received_packets:
                        with self.received_packets_lock:
                            self.received_packets[seq_num] = data
                    # note that we don't necessarily ack the seq num we just received
                    # instead we need to ack the last seq num of the consecutive seq of packets starting from packet 0
                    # this is updated as a side effect by recv() as it only returns consecutive packets
                    # one drawback of doing it this way is that we have to wait until the next cycle of recv() for this value to be updated
                    # even if the seq num we just received in fact resulted in a valid consecutive sequence
                    ack = self._build_packet(
                        self.last_inorder_received_seq, True, False
                    )
                    self.socket.sendto(ack, self.dest)
                    print(
                        f"Received packet with seq num {seq_num}, sending ACK for seq num {self.last_inorder_received_seq}"
                    )
            except Exception as e:
                print("listener died!", e)

        self.listen_thread.shutdown()

    def _retransmit_until(self, packet: bytes, should_stop: Callable[[], bool]) -> None:
        """
        Retransmits a packet at intervals defined by ACK_TIMEOUT until the stop condition is met.

        Args:
            packet: The packet to retransmit.
            should_stop: A callable that returns True to stop retransmission.
        """
        start_time = time()
        while not should_stop():
            if time() - start_time > ACK_TIMEOUT:
                self.socket.sendto(packet, self.dest)
                start_time = time()
            sleep(0.01)

    def _unpack_packet(self, packet: bytes) -> tuple[int, bool, bool, bytes]:
        """
        Unpacks the header and data from a packet without its hash.

        Args:
            packet: The packet with header and data, excluding the hash.

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
            seq_num: Sequence number for the packet.
            is_ack: if this packet sends acknowledgement of receiving data.
            is_fin: if this packet signals the end of transmission.
            data: Optional data payload.

        Returns:
            The complete packet with a hash prepended to the header and data.
        """
        header_no_hash = struct.pack(HEADER_NO_HASH_FORMAT, seq_num, is_ack, is_fin)
        packet_no_hash = header_no_hash + data
        digest = self._calculate_hash(packet_no_hash)

        return digest + packet_no_hash

    def _calculate_hash(self, data: bytes) -> bytes:
        """Calculates MD5 hash of some bytes data."""
        return md5(data).digest()

    def _verify_hash(self, data: bytes, expected_hash: bytes) -> bool:
        """Verifies data integrity by comparing the calculated hash to the expected hash."""
        return self._calculate_hash(data) == expected_hash
