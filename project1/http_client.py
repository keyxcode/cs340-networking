import socket
import sys
from typing import Tuple

# Requirements:
#
# [x] Only the body of the response (excluding the header) should be printed to stdout.
#   Any other messages should be printed to stderr.
#
# [x] All requests are assumed to use the HTTP "GET" method (no support for POST or others).
#
# [x] The client must include a "Host: ..." header. This is necessary because some web servers handle multiple domains.
#
# [x] The program should return a Unix exit code (using sys.exit) to indicate whether the request is successful or not.
#   Return 0 on success (a "200 OK" response with valid HTML) and non-zero on failure.
#
# [] The client should understand and follow 301 and 302 redirects. On receiving a redirect, the client should make another request
#   to fetch the corrected URL and print a message to stderr with the format: "Redirected to: http://other.com/blah" (show the specific URL).
#   Examples of URLs with redirects:
#     - http://airbedandbreakfast.com/ (redirects to https://www.airbnb.com/belong-anywhere)
#     - http://maps.google.com/ (redirects to http://maps.google.com/maps, which redirects to https://www.google.com:443/maps)
#     - http://insecure.stevetarzia.com/redirect (redirects to http://insecure.stevetarzia.com/basic.html)
#   Handle a chain of multiple redirects but stop after 10 redirects and return a non-zero exit code.
#   For example, http://insecure.stevetarzia.com/redirect-hell should not loop infinitely but return a non-zero exit code.
#
# [] If you try to visit or are redirected to an HTTPS page, print an error message to stderr and return a non-zero exit code.
#
# [x] If the HTTP response code is >= 400, return a non-zero exit code but print the response body to stdout if any.
#   Example of a 404 response: http://cs.northwestern.edu/340
#
# [] Check the response's content-type header. Print the body to stdout only if the content-type begins with "text/html".
#   Otherwise, exit with a non-zero exit code.
#
# [x] Return a non-zero exit code if the input URL does not start with "http://".
#
# [x] Allow request URLs to include a port number (e.g., http://portquiz.net:8080/).
#
# [x] Do not require a slash at the end of top-level URLs. Both http://insecure.stevetarzia.com and http://insecure.stevetarzia.com/ should work.
#
# [x] Handle large pages, such as http://insecure.stevetarzia.com/libc.html.
#
# [] The client should run quickly and not use timeouts to determine when the response is fully transferred.
#
# [] Work even if the Content-Length header is missing. Read body data until the server closes the connection.
#   This behavior is part of the HTTP/1.0 spec and should work with servers like http://google.com.


def parse_url(url: str) -> Tuple[str, int, str]:
    if not url.startswith("http://"):
        raise Exception("URL must start with 'http://'")

    # remove http://
    url = url.split("://")[-1]

    # split the url in (host:port) and path
    if "/" in url:
        host_port, path = url.split("/", 1)
        path = "/" + path
    else:
        host_port, path = url, "/"

    # split (host:port) into host and port
    # note that host can either be a domain name or an IP address
    if ":" in host_port:
        host, port = host_port.split(":", 1)
    else:
        host, port = host_port, 80

    return host, int(port), path


def communicate_with_server(host: str, port: int, request: str) -> Tuple[int, str]:
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

    headers, _, body = response.decode().partition("\r\n\r\n")
    status_line = headers.splitlines()[0]  # always first line of the headers
    status_code = int(status_line.split()[1])  # always second el of the status line

    return status_code, body


def main():
    if len(sys.argv) != 2:
        print("Usage: python script.py <URL>")
        sys.exit(1)

    url = sys.argv[1]

    try:
        host, port, path = parse_url(url)
    except:
        sys.exit(1)

    request = f"GET {path} HTTP/1.1\r\nHost: {host}\r\nConnection: close\r\n\r\n"
    status_code, body = communicate_with_server(host, port, request)

    print(body)
    if status_code < 400:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
