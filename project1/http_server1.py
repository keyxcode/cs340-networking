import socket
import sys
from typing import Tuple

# [] Create a TCP socket to listen for new connections.
# [] Bind the socket to the port provided on the command line.
# [] Listen on the accept socket. (Consider the effects of backlog size on performance)
#
# Do the following repeatedly:
#
# [] a. Accept a new connection on the accept socket.
# [] b. Read and parse the HTTP request from the connection socket. Determine how many bytes to read based on Content-Length header?
# [] c. Check if the requested file exists and ends with ".htm" or ".html".
# [] d. If the file exists, use status code 200 OK to write the HTTP header to the connection socket. Then open and write the file content (HTTP body) to the socket.
# [] e. If the file doesn't exist, send a 404 Not Found response. If the file exists but does not end with ".htm" or ".html", send a 403 Forbidden response.
# [] f. Close the connection socket.


def run_server(port: int) -> None:
    print(port)

    # packet/address family AF_INET for IPv4
    # type SOCK_STREAM for TCP

    # bind to an empty string "" as the IP so that the socket listens on all network interfaces available on the machine
    # and use the port passed in arg

    # check for file availability

    # create and send response

    # close socket


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
