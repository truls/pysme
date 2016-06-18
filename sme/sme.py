import argparse
import time
import re
from collections import OrderedDict

from typing import TypeVar, Any, Generic, List, KeysView

T = TypeVar('T')
BT = TypeVar('BT', int, str)
CT = TypeVar("CT")

typere = re.compile(r'^(b|(?:i|u)(?=\d+))((?<=(?:i|u))\d+)?$')


class GeneralSMEException(Exception):
    pass


class IllegalReadException(GeneralSMEException):
    pass


class IllegalWriteException(GeneralSMEException):
    pass


class UnimplementedMethodException(GeneralSMEException):
    pass


class BusMapMismatch(GeneralSMEException):
    pass


class InvalidTypeException(GeneralSMEException):
    pass


def anytostr(v: Any) -> str:
    return str(v)


class BaseType:
    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

    @name.setter
    def name(self, n):
        self._name = n

    def __str__(self):
        return self.__repr__()

    def __repr__(self):
        return self._name


class Boolean(BaseType):
    def __init__(self, name):
        BaseType.__init__(self, name)


class Integer(BaseType):
    def __init__(self, name, width):
        BaseType.__init__(self, name)
        self._width = width

    @property
    def width(self):
        return self._width


class Signed(Integer):
    def __init__(self, name, width):
        Integer.__init__(self, name, width)


class Unsigned(Integer):
    def __init__(self, name, width):
        Integer.__init__(self, name, width)


class Types:
    def __init__(self):
        self._name = ""
        self._type = None

    def _classify_type(self, n, t):
        match = typere.match(t)

        if match is None:
            raise InvalidTypeException

        groups = match.groups()

        if groups[0] == 'b':
            return Boolean(n)
        elif groups[0] == 'i':
            try:
                return Signed(n, int(groups[1]))
            except:
                raise InvalidTypeException
        elif groups[0] == 'u':
            try:
                return Unsigned(n, int(groups[1]))
            except:
                raise InvalidTypeException
        else:
            raise InvalidTypeException

    def __getattr__(self, t):
        def _get_type(name):
            return self._classify_type(name, t)
        return _get_type


class Special:
    # High-impedance value
    Z = None
    # Unknown/don't care value
    X = None


class Channel(Generic[CT]):
    def __init__(self, name: str) -> None:
        self._name = name
        self.read = None
        self.write = None

    @property
    def name(self) -> str:
        return self._name

    @property
    def value(self) -> CT:
        if self.read is None:
            raise IllegalReadException("Bus had value " +
                                       anytostr(self.read))
        return self.read

    @value.setter
    def value(self, v: CT) -> CT:
        if self.write is None:
            self.write = v
        else:
            raise IllegalWriteException("Bus had value " +
                                        anytostr(self.write))

    def propagate(self) -> None:
        self.read = self.write
        self.write = None


class Bus(Generic[BT]):
    def __init__(self, name: str, channels: List["str"], dtype: Any) -> None:
        self.name = name
        self.chs = {}
        self._trace = None
        self._parent = None
        for ch in channels:
            chan = Channel(str(ch))
            self.chs[str(ch)] = chan

    def __getitem__(self, n: str) -> BT:
        ret = self.chs[n].value
        return ret

    def __setitem__(self, n: str, v: BT) -> None:
        self.chs[n].value = v

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, p):
        self._parent = p

    def read(self, n: str) -> BT:
        return self.chs[n].value

    def write(self, n: str, v: BT) -> None:
        self.chs[n].value = v

    def channames(self) -> KeysView[str]:
        return self.chs.keys()

    @property
    def trace(self):
        return self._trace

    def _trace_name(self, chn):
        return "%s_%s_%s" % (self.parent.name, self.name, chn)

    def _setup_trace(self, trace):
        for ch in self.chs.keys():
            tname = self._trace_name(ch)
            if tname not in trace:
                trace[tname] = []
        self._trace = trace

    def clock(self, tracing=False):
        for ch in self.chs.values():
            ch.propagate()
            if tracing:
                try:
                    self._trace[self._trace_name(ch.name)].append(ch.value)
                except IllegalReadException:
                    self._trace[self._trace_name(ch.name)].append(None)


class Function:
    def __init__(self, name, ins,
                 outs, *args, **kwargs):
        self._name = name
        self._parent = None
        self.setup(ins, outs, *args, **kwargs)

    def map_ins(self, busses, *args):
        self._map_busses(busses, *args)

    def map_outs(self, busses, *args):
        self._map_busses(busses, *args)

    def _map_busses(self, busses, *args):
        if len(busses) != len(args):
            raise(BusMapMismatch())
        for n, b in zip(args, busses):
            self.__dict__[n] = b

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, p):
        self._parent = p

    def setup(self, buses, *args, **kwargs) -> None:
        raise UnimplementedMethodException(
            "All subclasses of " + self.__class__.__name__ +
            " must implement the setup method")

    def clock(self, i: int=1) -> None:
        while i > 0:
            self.run()
            i -= 1

    def run(self) -> None:
        raise UnimplementedMethodException(
            "All subclasses of " + self.__class__.__name__ +
            " must implement a run method")


class External(Function):
    pass


class Network:
    def __init__(self, name: str, *args, **kwargs):
        self.name = name
        self.funs = []  # type: List[Function]
        self.busses = []  # type: List[Bus]
        self.externals = []  # type: List[External]

        self.tracing = False
        self.trace = {}
        # FIXME: This will give us class init time which may be a bit wierd
        self.trace_file = "trace-" + time.ctime().replace(" ", "-") + ".txt"
        self.graph = False
        self.graph_file = "graph-" + time.ctime().replace(" ", "-") + ".dot"

        self.deferred_init = lambda: self.wire(*args, **kwargs)

    def init(self):
        self.deferred_init()

    def tell(self, obj):
        if isinstance(obj, Bus):
            obj.parent = self
            if self.tracing:
                obj._setup_trace(self.trace)
            self.busses.append(obj)
        elif isinstance(obj, Function):
            obj.parent = self
            self.funs.append(obj)
        else:
            raise TypeError("Only instances deriving from Bus or Function can "
                            "be added to the network")

    def wire(self, *args, **kwargs) -> None:
        raise UnimplementedMethodException(
            "All Network subclasses must implement a wire method")

    def _set_opts(self, opts):
        if opts.trace:
            self.tracing = True
            if isinstance(opts.trace, str):
                self.trace_file = opts.trace
        if opts.graph is not None:
            self.graph = True
            if isinstance(opts.graph, str):
                self.graph_file = opts.graph

    def clock(self, cycles: int) -> None:
        while cycles > 0:
            for bus in self.busses:
                bus.clock(tracing=self.tracing)
            for fun in self.funs:
                fun.clock()

            cycles -= 1

        if self.tracing:
            # TODO: verify that file is valid and can be opened before getting
            # to this point.
            # Bus format: NetworkName_BusName_PortName

            # Reorder traces so that they can be read by the testbench in a
            # predictable order
            otrace = OrderedDict(sorted(self.trace.items(),
                                        key=lambda t: t[0]))
            with open(self.trace_file, 'w') as f:
                f.write(",".join(otrace.keys()) + "\n")
                # FIXME: Why does removing the first row from the trace work?
                for vals in zip(*otrace.values()):
                    # TODO: Check that values are within the bounds of their
                    # specified width.
                    f.write(",".join(map(lambda x: "U" if x is None else
                                         str(int(x)), vals)) + "\n")


class SME:
    def __init__(self):
        self._network = None
        self.opts = None
        self.unparsed_opts = None

        self._options()

    def _options(self):
        parser = argparse.ArgumentParser(description="PySME library options")
        parser.add_argument('-t', '--trace', nargs='?', type=str, const=True,
                            action='store', metavar='FILE',
                            help="Write trace of busses to FILE. If no FILE "
                            "is given it defaults to trace-<timestamp>.txt")
        parser.add_argument('-g', '--graph', nargs='?', type=str, const=True,
                            action='store', metavar='FILE',
                            help="Write graph of network to FILE. If no FILE "
                            "is given it defaults to graph-<timestamp>.dot")
        parser.add_argument('-C', '--outdir', nargs='?', type=str,
                            metavar="DIR",
                            help="Save output files to DIR, useful if default "
                            "filenames are desired but files should be stored "
                            "in a dir different from PWD")
        (ns, rest) = parser.parse_known_args()
        self.opts = ns
        self.unparsed_opts = rest

    @property
    def network(self):
        return self._network

    @network.setter
    def network(self, network):
        if not isinstance(network, Network):
            raise TypeError("network must be an instance of the Network class")
        network._set_opts(self.opts)
        self._network = network
        network.init()

    @property
    def remaining_options(self):
        return self.unparsed_opts
