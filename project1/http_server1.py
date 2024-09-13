from socket import socket, AF_INET, SOCK_STREAM
import sys
from socket_utils import receive_all
from utils import print_err, print_br

# [x] Create a TCP socket to listen for new connections.
# [x] Bind the socket to the port provided on the command line.
# [x] Listen on the accept socket. (Consider the effects of backlog size on performance)
#
# Do the following repeatedly:
#
# [x] a. Accept a new connection on the accept socket.
# [x    ] b. Read and parse the HTTP request from the connection socket. Determine how many bytes to read.
# [] c. Check if the requested file exists and ends with ".htm" or ".html".
# [] d. If the file exists, use status code 200 OK to write the HTTP header to the connection socket. Then open and write the file content (HTTP body) to the socket.
# [] e. If the file doesn't exist, send a 404 Not Found response. If the file exists but does not end with ".htm" or ".html", send a 403 Forbidden response.
# [] f. Close the connection socket.


def run_server(port: int) -> None:
    # use an empty string "" as the IP so that the socket listens on all network interfaces available on the machine
    # or use "localhost" for only testing locally
    HOST = "localhost"
    # instructs the OS to start queuing up to 10 incoming connections while server is busy
    BACKLOG_SIZE = 10

    # packet family AF_INET for IPv4 | type SOCK_STREAM for TCP
    with socket(AF_INET, SOCK_STREAM) as s:
        s.bind((HOST, port))  # bind socket to host:port
        s.listen(BACKLOG_SIZE)  # enable a server to accept connections
        print_err(f"Server socket {s} is listening")
        print_br()

        # accept() pauses the program's execution until a connection request is received
        # once a connection is received, it will return a new connection socket, and the IP addr of the request
        conn, addr = s.accept()
        print_err(f"Received connection from {addr}\nOpened connection socket {conn}")
        print_br()

        with conn:
            request = receive_all(conn)
            print_err(f"Request Headers:\n{request.decode()}")
            print_br()

            # dummy hardcoded
            response = b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n"
            conn.sendall(response)
            print_err(f"Response Headers:\n{response.decode()}")
            print_br()

    # check for file availability

    # create and send response


def main():
    port = 1024  # default

    # get optional user input port number
    if len(sys.argv) > 2:
        print("Usage: python script.py <PORT>", file=sys.stderr)
        sys.exit(1)
    elif len(sys.argv) == 2:
        port = int(sys.argv[1])

    run_server(port)


if __name__ == "__main__":
    main()
