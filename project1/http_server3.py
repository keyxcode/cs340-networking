from socket import socket, AF_INET, SOCK_STREAM
import sys
from math import prod, isinf
import json
from socket_utils import receive_all
from utils import print_err, print_br
from http_server1 import make_http_response
from typing import List

# Implement a dynamic server that handles product calculation via HTTP requests
#
# [x] Parse query parameters from the URL as operands
# [x] Return a 404 Not Found status code for URLs other than "/product"
# [x] Return a 400 Bad Request status code if:
#     - [x] No parameters are provided for "/product"
#     - [x] Any parameter is not a valid number (e.g., "GET /product?a=blah")
# [x] Treat query parameters as floating point numbers
# [x] Handle floating point overflow: return "inf" or "-inf" as strings in the JSON response
# [x] Use Python's built-in json library to generate the response in JSON format
# [x] Ensure the response body includes:
#     - [x] "operation": "product"
#     - [x] "operands": a list of the numbers provided in the query parameters
#     - [x] "result": the product of the operands
# [x] Set "Content-Type: application/json" for the response


class NotFoundError(Exception):
    pass


def get_path(request: bytes) -> str:
    """Extract the operands from HTTP GET query params."""

    headers = request.decode()
    print_err(f"Request Headers:\n{headers}")
    print_br()

    headers_lines = headers.splitlines()
    if not headers_lines:
        raise ValueError("Invalid request: No headers found")

    request_line = headers_lines[0]
    request_components = request_line.split()
    if len(request_components) < 3 or request_components[0] != "GET":
        raise ValueError("Invalid request method or format")

    path = request_line.split()[1]  # e.g. GET /index.html HTTP/1.1

    return path


def get_operands(path: str) -> List[float]:
    if not path.startswith("/product"):
        raise NotFoundError(f"Requested URL {path} does not start with '/product'")

    # split between product and the query params e.g. /product?a=1&b=2
    path_components = path.split("?")
    if len(path_components) < 2:
        raise ValueError(f"Missing query parameters in the request {path}")

    # get a list of the query params themselves e.g. ["a=1", "b=2"]
    query_params = path_components[1].split("&")
    if len(query_params) < 1:
        raise ValueError(f"No operands provided in the query {path}")

    res = list()
    for param in query_params:
        try:
            res.append(float(param.split("=")[1]))
        except ValueError:
            raise ValueError(f"Invalid operand value: '{param}' is not a number")

    return res


def make_json_response(operands: List[int]) -> int:
    product = prod(operands)
    if isinf(product):
        product = str(product)

    response_body = {
        "operation": "product",
        "operands": operands,
        "result": product,
    }
    response_json = json.dumps(response_body)

    return response_json


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

                try:
                    path = get_path(request)
                    operands = get_operands(path)
                    json_body = make_json_response(operands)
                    response = make_http_response(200, json_body, "application/json")
                except NotFoundError as e:
                    response = make_http_response(404, str(e))
                    print_err(e)
                except (ValueError, Exception) as e:
                    response = make_http_response(400, f"{str(e)}")
                    print_err(e)
                finally:
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
