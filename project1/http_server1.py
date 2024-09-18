from socket import socket, AF_INET, SOCK_STREAM
import sys
from os.path import basename, isfile
from socket_utils import receive_all
from utils import print_err, print_br

# [x] Create a TCP socket to listen for new connections.
# [x] Bind the socket to the port provided on the command line.
# [x] Listen on the accept socket. (Consider the effects of backlog size on performance)
#
# Do the following repeatedly:
#
# [x] a. Accept a new connection on the accept socket.
# [x] b. Read and parse the HTTP request from the connection socket. Determine how many bytes to read.
# [x] c. Check if the requested file exists and ends with ".htm" or ".html".
# [x] d. If the file exists, use status code 200 OK to write the HTTP header to the connection socket. Then open and write the file content (HTTP body) to the socket.
# [x] e. If the file doesn't exist, send a 404 Not Found response. If the file exists but does not end with ".htm" or ".html", send a 403 Forbidden response.
# [x] f. Close the connection socket.


def get_file_requested(request: bytes) -> str:
    """Extract the requested file name from an HTTP GET request."""

    # technically, there should be a step separating the request headers and body
    # but since we're only supporting GET requests here, this is not important as they only contain headers
    headers = request.decode()
    print_err(f"Request Headers:\n{headers}")
    print_br()

    headers_lines = headers.splitlines()
    if not headers_lines:
        raise ValueError("Invalid request: No headers found")

    request_line = headers_lines[0]  # always first line of the headers
    request_components = request_line.split()
    if len(request_components) < 3 or request_components[0] != "GET":
        raise ValueError("Invalid request method or format")

    path = request_line.split()[1]  # e.g. GET /index.html HTTP/1.1
    filename = basename(path)

    return filename


def file_exists(filename: str) -> bool:
    """Check if a file exists on the server."""

    return isfile(filename)


def is_html_file(filename: str) -> bool:
    """Determine if the file is an HTML or HTM file."""

    return filename.rsplit(".", 1)[-1].lower() in ("html", "htm")


def make_response(status_code: int, filename: str = None) -> bytes:
    """Generate an HTTP response with the given status code and optional file content."""

    status_code_reasons = {
        200: "OK",
        400: "Bad Request",
        403: "Forbidden",
        404: "Not Found",
    }

    # headers
    response = f"HTTP/1.0 {status_code} {status_code_reasons[status_code]}\r\nContent-Type: text/html\r\n\r\n"

    if filename:
        with open(filename, "r") as file:
            response += file.read()

    return response.encode()


def run_server(port: int) -> None:
    """Start the HTTP server and handle a single incoming connection at a time."""

    # use an empty string "" as the IP so that the socket listens on all network interfaces available on the machine
    # or use "localhost" for only testing locally
    HOST = "localhost"
    # instructs the OS to start queuing up to 10 incoming connections while server is busy
    BACKLOG_SIZE = 10

    # packet family AF_INET for IPv4 | type SOCK_STREAM for TCP
    with socket(AF_INET, SOCK_STREAM) as server:
        server.bind((HOST, port))  # bind socket to host:port
        server.listen(BACKLOG_SIZE)  # enable a server to accept connections
        print_err(f"Server socket {server} is listening")
        print_br()

        # continuously listen to new connection requests
        while True:
            print_err("Listening...")
            # accept() pauses the program's execution until a connection request is received
            # once a connection is received, it will return a new connection socket, and the IP addr of the request
            conn, addr = server.accept()
            print_err(
                f"Received connection from {addr}\nOpened connection socket {conn}"
            )
            print_br()

            with conn:
                request = receive_all(conn)

                # parse request
                try:
                    file_requested = get_file_requested(request)
                    # create response based on file availability
                    if file_exists(file_requested):
                        if is_html_file(file_requested):
                            response = make_response(200, file_requested)
                        else:
                            response = make_response(403)
                    else:
                        response = make_response(404)
                except ValueError as e:
                    response = make_response(400)
                    print_err(e)

                conn.sendall(response)
                print_err(f"Response:\n{response.decode()}")
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
