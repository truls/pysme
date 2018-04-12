from abc import ABC, abstractmethod
from ._exceptions import IllegalReadException, IllegalWriteException


class _BaseChannel(ABC):

    @property
    def name(self):
        return self._name

    @property
    @abstractmethod
    def value(self):
        pass

    @value.setter
    @abstractmethod
    def value(self, v):
        pass

    @abstractmethod
    def propagate(self):
        pass


class _Channel(_BaseChannel):

    def __init__(self, name):
        self._name = name
        self.read = None
        self.write = None

    @property
    def value(self):
        """Get the value of the channel."""
        if self.read is None:
            raise IllegalReadException("Bus had value " +
                                       self.read)
        return self.read

    @value.setter
    def value(self, v):
        """Get the value of the channel."""
        if self.write is None:
            self.write = v
        else:
            raise IllegalWriteException("Bus had value " +
                                        self.write)

    def propagate(self):
        self.read = self.write
        self.write = None


class _BaseBus(ABC):

    def __getitem__(self, n):
        return self.read(n)

    def __setitem__(self, n, v):
        self.write(n, v)

    def read(self, n):
        return self.chs[n].value

    def write(self, n, v):
        self.chs[n].value = v

    def channames(self):
        return self.chs.keys()

    @property
    @abstractmethod
    def _trace(self):
        pass

    @abstractmethod
    def _clock(self):
        pass
