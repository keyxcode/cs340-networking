import socket
import sys
from typing import Tuple


def parse_url(url: str) -> Tuple[str, str]:
    url = url.split("://")[-1]  # remove the scheme

    # split only on the first '/'
    parts = url.split("/", 1)
    host = parts[0]
    path = "/" + parts[1] if len(parts) > 1 else "/"

    return host, path


def communicate_with_server(host: str, port: str, request: str) -> str:
    # socket.AF_INET specifies we're using IPv4
    # socket.SOCK_STREAM means we're using TCP => can reassemble data in order and retransmit if needed
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.connect((host, port))
        s.sendall(request.encode())

        response = b""
        while True:
            data = s.recv(4096)
            if not data:
                break
            response += data

        return response.decode()


def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <URL>")
        sys.exit(1)

    url = sys.argv[1]
    host, path = parse_url(url)
    PORT = 80  # port used by the server
    request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"

    res = communicate_with_server(host, PORT, request)
    print(res)


if __name__ == "__main__":
    main()
