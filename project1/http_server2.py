from socket import socket, AF_INET, SOCK_STREAM
import sys
from select import select
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
        # sockets to which we expect to write
        outputs = []
        # outgoing message queues
        responses = dict()

        while inputs:
            print_err("Listening...")
            readable, writable, exceptional = select.select(inputs, outputs, inputs)

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
                    # with s:
                    request = receive_all(s, True)

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

                    responses[s] = response
                    outputs.append(s)
                    inputs.remove(s)
                    print_err(f"Received request from socket {s}")
                    print_br()

                    # addr = s.getpeername()
                    # data = s.recv(1024)
                    # if data:
                    #     # a readable client socket has data
                    #     print(
                    #         "  received {!r} from {}".format(data, s.getpeername()),
                    #         file=sys.stderr,
                    #     )
                    #     # add output channel for response
                    #     if s not in outputs:
                    #         outputs.append(s)
                    # else:
                    #     # interpret empty result as closed connection
                    #     print("  closing", addr, file=sys.stderr)
                    #     # stop listening for input on the connection
                    #     if s in outputs:
                    #         outputs.remove(s)
                    #     inputs.remove(s)
                    #     s.close()

                    #     # remove message queue
                    #     del message_queues[s]

            # handle outputs
            for s in writable:
                response = responses[s]
                s.sendall(response)

                outputs.remove(s)
                del responses[s]
                s.close()

                print_err(f"Closing socket {s}")
                print_br()

                # try:
                #     next_msg = message_queues[s].get_nowait()
                # except queue.Empty:
                #     # no messages waiting so stop checking for writability
                #     print("  ", s.getpeername(), "queue empty", file=sys.stderr)
                #     outputs.remove(s)
                # else:
                #     print(
                #         "  sending {!r} to {}".format(next_msg, s.getpeername()),
                #         file=sys.stderr,
                #     )
                #     s.send(next_msg)

            # handle "exceptional conditions"
            for s in exceptional:
                inputs.remove(s)
                if s in outputs:
                    outputs.remove(s)
                del responses[s]
                s.close()

                print_err(f"Exception condition on socket {s}")
                print_br()

                # print("exception condition on", s.getpeername(), file=sys.stderr)
                # # stop listening for input on the connection
                # inputs.remove(s)
                # if s in outputs:
                #     outputs.remove(s)
                # s.close()

                # remove message queue
                # del message_queues[s]

        # while True:
        #     print_err("Listening...")
        #     # accept() pauses the program's execution until a connection request is received
        #     # once a connection is received, it will return a new connection socket, and the IP addr of the request
        #     conn, addr = server.accept()
        #     print_err(
        #         f"Received connection from {addr}\nOpened connection socket {conn}"
        #     )
        #     print_br()

        #     with conn:
        #         request = receive_all(conn, True)

        #         # parse request
        #         file_requested = get_file_requested(request)

        #         # creat response based on file availability
        #         if file_exists(file_requested):
        #             if is_html_file(file_requested):
        #                 response = make_response(200, file_requested)
        #             else:
        #                 response = make_response(403)
        #         else:
        #             response = make_response(404)

        #         conn.sendall(response)


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
