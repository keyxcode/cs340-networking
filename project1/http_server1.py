import socket
import sys

# [x] Create a TCP socket to listen for new connections.
# [x] Bind the socket to the port provided on the command line.
# [x] Listen on the accept socket. (Consider the effects of backlog size on performance)
#
# Do the following repeatedly:
#
# [x] a. Accept a new connection on the accept socket.
# [] b. Read and parse the HTTP request from the connection socket. Determine how many bytes to read based on Content-Length header?
# [] c. Check if the requested file exists and ends with ".htm" or ".html".
# [] d. If the file exists, use status code 200 OK to write the HTTP header to the connection socket. Then open and write the file content (HTTP body) to the socket.
# [] e. If the file doesn't exist, send a 404 Not Found response. If the file exists but does not end with ".htm" or ".html", send a 403 Forbidden response.
# [] f. Close the connection socket.


def run_server(port: int) -> None:
    HOST = "localhost"

    # packet family AF_INET for IPv4 & type SOCK_STREAM for TCP
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        # use an empty string "" as the IP so that the socket listens on all network interfaces available on the machine
        # or use "localhost" for testing locally
        # and use the port passed in arg
        s.bind((HOST, port))

        # listen() enables a server to accept connections
        # instructs the OS to start queuing up to 10 incoming connections while server is busy
        s.listen(10)

        # accept() pauses the program's execution until a connection request is received
        # once a connection is received, it will return a new connection socket, and the IP addr of the request
        conn, addr = s.accept()

        with conn:
            print(f"Connected by {addr}")

            # while True: # echo
            #     data = conn.recv(1024)
            #     if not data:
            #         break
            #     conn.sendall(data)

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
