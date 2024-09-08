import socket


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
    HOST = "insecure.stevetarzia.com"  # server's hostname or IP
    PORT = 80  # port used by the server
    request = (
        "GET / HTTP/1.1\r\nHost: insecure.stevetarzia.com\r\nConnection: close\r\n\r\n"
    )

    res = communicate_with_server(HOST, PORT, request)
    print(res)


if __name__ == "__main__":
    main()
