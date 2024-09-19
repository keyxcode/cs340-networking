from socket import socket, AF_INET, SOCK_STREAM
import sys
from socket_utils import receive_all
from utils import print_err, print_br
from http_server1 import make_response

# Implement a dynamic server that handles product calculation via HTTP requests
#
# [] Parse query parameters from the URL as operands
# [] Use Python's built-in json library to generate the response in JSON format
# [] Ensure the response body includes:
#     - [] "operation": "product"
#     - [] "operands": a list of the numbers provided in the query parameters
#     - [] "result": the product of the operands
# [] Set "Content-Type: application/json" for the response
# [] Return a 404 Not Found status code for URLs other than "/product"
# [] Return a 400 Bad Request status code if:
#     - [] No parameters are provided for "/product"
#     - [] Any parameter is not a valid number (e.g., "GET /product?a=blah")
# [] Treat query parameters as floating point numbers
# [] Handle floating point overflow: return "inf" or "-inf" as strings in the JSON response


def run_server(port: int) -> None:
    """Start the HTTP server and handle a single incoming connection at a time."""

    HOST = "localhost"
    BACKLOG_SIZE = 10

    with socket(AF_INET, SOCK_STREAM) as server:
        server.bind((HOST, port))
        server.listen(BACKLOG_SIZE)
        print_err(f"Server socket {server} is listening")
        print_br()

        while True:
            print_err("Listening...")
            conn, addr = server.accept()
            print_err(
                f"Received connection from {addr}\nOpened connection socket {conn}"
            )
            print_br()

            with conn:
                request = receive_all(conn)

                # parse request
                try:
                    response = make_response(200)
                except ValueError as e:
                    response = make_response(400, str(e))
                    print_err(e)

                conn.sendall(response)
                print_err(f"Response:\n{response.decode()}")
                print_br()


def main():
    port = 1024

    if len(sys.argv) > 2:
        print("Usage: python script.py <PORT>", file=sys.stderr)
        sys.exit(1)
    elif len(sys.argv) == 2:
        port = int(sys.argv[1])

    run_server(port)


if __name__ == "__main__":
    main()
