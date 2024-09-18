from socket import socket, AF_INET, SOCK_STREAM
import sys
from select import select
from socket_utils import receive_all
from utils import print_err, print_br
from http_server1 import get_file_requested, file_exists, is_html_file, make_response

# [x] Create a TCP socket on which to listen for new connections
# [x] Bind that socket to the port provided on the command line
# [x] Listen on that socket, which we shall call the "accept socket"
# [x] Initialize the list of open connections to empty
#
# Do the following repeatedly:
# [x] a. Make a list of the sockets we are waiting to read from the list of open connections. We shall call this the "read list." In our case, it's simply the list of all open connections.
#
# [x] b. Add the accept socket to the read list. Having a new connection arrive on this socket makes it available for reading; it’s just that we use a strange kind of read, the accept call, to do the read.
#
# [x] c. Call select with the read list. Your program will now block until one of the sockets on the read list is ready to be read.
#
# [x] d. For each socket on the read list that select has marked readable, do the following:
# [x]    i. If it is the accept socket, accept the new connection and add it to the list of open connections with the appropriate state
# [x]    ii. If it is some other socket, perform steps 4.b through 4.f from the description of http_server1 in Part 2. After closing the socket, delete it from the list of open connections.
#
# [x] Test your server using telnet and curl (or a web browser) as described above, to see whether it really handles two simultaneous connections.
#
# [] Your server should also be robust. If a request is empty or does not start with "GET", your server should just ignore it.


def run_server(port: int) -> None:
    """Start the HTTP server that handles multiple incoming connections at a time."""

    HOST = "localhost"
    BACKLOG_SIZE = 10

    with socket(AF_INET, SOCK_STREAM) as server:
        server.bind((HOST, port))
        server.listen(BACKLOG_SIZE)
        # non-blocking mode => operations on the socket e.g. accept(), recv(), and send() return immediately
        # if they can't complete right away they raise an exception like BlockingIOError instead of waiting
        # in this mode, select() can monitor multiple sockets efficiently
        server.setblocking(False)
        print_err(f"Server socket {server} is listening")
        print_br()

        # sockets from which we expect to read
        inputs = [server]

        while inputs:
            # blocking until an input is marked by select as readable
            print_err("Listening...")
            readable, _, _ = select(inputs, [], [])

            # handle inputs
            for s in readable:
                if s is server:
                    # a "readable" socket is ready to accept a connection
                    conn, addr = server.accept()
                    conn.setblocking(0)
                    inputs.append(conn)
                    print_err(
                        f"Received connection from {addr}\nOpened connection socket {conn}"
                    )
                    print_br()
                else:
                    request = receive_all(s)
                    file_requested = get_file_requested(request)
                    print_err(f"Received request from socket {s}")
                    print_br()

                    # create response based on file availability
                    if file_exists(file_requested):
                        if is_html_file(file_requested):
                            response = make_response(200, file_requested)
                        else:
                            response = make_response(403)
                    else:
                        response = make_response(404)

                    s.sendall(response)
                    print_err(f"Response:\n{response.decode()}")
                    print_br()

                    inputs.remove(s)
                    s.close()
                    print_err(f"Closing socket {s}")
                    print_br()


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
