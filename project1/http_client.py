import socket


def main():
    server_address = ("insecure.stevetarzia.com", 80)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        sock.connect(server_address)
        request = "GET / HTTP/1.1\r\nHost: insecure.stevetarzia.com\r\nConnection: close\r\n\r\n"

        sock.sendall(request.encode())
        response = b""
        while True:
            data = sock.recv(4096)
            if not data:
                break
            response += data

        print(response.decode())

    finally:
        sock.close()


if __name__ == "__main__":
    main()
