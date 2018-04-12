class SMEException(Exception):
    """An SME Exception."""

    pass


class IllegalReadException(SMEException):
    """Raised when a bus is read without being written to."""

    pass


class IllegalWriteException(SMEException):
    """Raised when the reading end of a bus is used for writing."""

    pass


class UnimplementedMethodException(SMEException):
    """Raised if requiried class methods are not overwridden.

    PySME requires that every Function or External class implements the setup
       and run methods and Network classes must implement a wire method.
    """

    pass


class BusMapMismatch(SMEException):
    """Thrown on bus map mismatch.

    TODO
    """

    pass


class InvalidTypeException(SMEException):
    """Thrown on type errors.

    TODO
    """

    pass
