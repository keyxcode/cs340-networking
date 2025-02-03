from sys import stderr


def print_err(*args) -> None:
    print(*args, file=stderr)


def print_br() -> None:
    print_err("-----------------------")
