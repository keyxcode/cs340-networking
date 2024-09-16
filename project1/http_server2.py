from socket import socket, AF_INET, SOCK_STREAM
import sys
from socket_utils import receive_all
from utils import print_err, print_br
from http_server1 import get_file_requested, file_exists, is_html_file, make_response

# [x] Create a TCP socket on which to listen for new connections
# [x] Bind that socket to the port provided on the command line
# [] Listen on that socket, which we shall call the "accept socket"
# [] Initialize the list of open connections to empty
#
# Do the following repeatedly:
# [] a. Make a list of the sockets we are waiting to read from the list of open connections. We shall call this the "read list." In our case, it's simply the list of all open connections.
#
# Note: A more sophisticated solution (beyond the scope of this assignment) would also do the reading of files from disk in a non-blocking way using select.
# In that case, the read list would also include a list of files that we were in the process of reading data from. In this assignment, we assume that file data can be read immediately, without an impact on performance, but that is not really true in practice.
#
# [] b. Add the accept socket to the read list. Having a new connection arrive on this socket makes it available for reading; it’s just that we use a strange kind of read, the accept call, to do the read.
#
# [] c. Call select with the read list. Your program will now block until one of the sockets on the read list is ready to be read.
#
# [] d. For each socket on the read list that select has marked readable, do the following:
# []    i. If it is the accept socket, accept the new connection and add it to the list of open connections with the appropriate state
# []    ii. If it is some other socket, perform steps 4.b through 4.f from the description of http_server1 in Part 2. After closing the socket, delete it from the list of open connections.
#
# [] Test your server using telnet and curl (or a web browser) as described above, to see whether it really handles two simultaneous connections.
#
# [] Your server should also be robust. If a request is empty or does not start with "GET", your server should just ignore it.


def run_server(port: int) -> None:
    """Start the HTTP server and handle a single incoming connection at a time."""

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

        # continuously listen to new connection requests
        while True:
            print_err("Listening...")
            # accept() pauses the program's execution until a connection request is received
            # once a connection is received, it will return a new connection socket, and the IP addr of the request
            conn, addr = s.accept()
            print_err(
                f"Received connection from {addr}\nOpened connection socket {conn}"
            )
            print_br()

            with conn:
                request = receive_all(conn, True)

                # parse request
                file_requested = get_file_requested(request)

                # creat response based on file availability
                if file_exists(file_requested):
                    if is_html_file(file_requested):
                        response = make_response(200, file_requested)
                    else:
                        response = make_response(403)
                else:
                    response = make_response(404)

                conn.sendall(response)


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
