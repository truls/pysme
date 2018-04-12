"""
The PySME implementation.

Licensed under the LGPL-3 license.

"""

import argparse
import time
import re
from abc import ABC, abstractmethod
from collections import OrderedDict

from ._bus import _BaseBus, _Channel
from ._libsme_support import _LibSme
from ._exceptions import InvalidTypeException, SMEException,\
    UnimplementedMethodException, BusMapMismatch, IllegalReadException


class _BaseType(ABC):
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

    @abstractmethod
    def __repr__(self):
        pass


class _Boolean(_BaseType):

    def __init__(self, name):
        _BaseType.__init__(self, name)


class _Integer(_BaseType):
    def __init__(self, name, width):
        _BaseType.__init__(self, name)
        self._width = width

    @property
    def width(self):
        return self._width


class _Signed(_Integer):
    def __init__(self, name, width):
        _Integer.__init__(self, name, width)


class _Unsigned(_Integer):
    def __init__(self, name, width):
        _Integer.__init__(self, name, width)


class Types:
    """Class for expressing special SME types."""

    typere = re.compile(r'^(b|(?:i|u)(?=\d+))((?<=(?:i|u))\d+)?$')

    def __init__(self):
        self._name = ""
        self._type = None

    def _classify_type(self, n, t):
        match = Types.typere.match(t)

        if match is None:
            raise InvalidTypeException

        groups = match.groups()

        if groups[0] == 'b':
            return _Boolean(n)
        elif groups[0] == 'i':
            try:
                return _Signed(n, int(groups[1]))
            except Exception:
                raise InvalidTypeException
        elif groups[0] == 'u':
            try:
                return _Unsigned(n, int(groups[1]))
            except Exception:
                raise InvalidTypeException
        else:
            raise InvalidTypeException

    def __getattr__(self, t):
        """Retrieve the type representation of the attribute."""
        def _get_type(name):
            return self._classify_type(name, t)
        return _get_type


class Special:
    """Special hardware-related values."""

    # High-impedance value
    Z = None
    # Unknown/don't care value
    X = None


class Bus(_BaseBus):
    """An internal SME bus."""

    def __init__(self, name, channels):
        self.name = name
        self.chs = {}
        self._trace = None
        self._parent_name = None
        for ch in channels:
            chan = _Channel(str(ch))
            self.chs[str(ch)] = chan

    @property
    def _trace(self):
        return self._trace

    def _trace_name(self, chn):
        return "%s_%s_%s" % (self._parent_name, self.name, chn)

    def _setup_trace(self, trace):
        for ch in self.chs.keys():
            tname = self._trace_name(ch)
            if tname not in trace:
                trace[tname] = []
        self._trace = trace

    def _clock(self, tracing=False):
        for ch in self.chs.values():
            ch.propagate()
            if tracing:
                try:
                    self._trace[self._trace_name(ch.name)].append(ch.value)
                except IllegalReadException:
                    self._trace[self._trace_name(ch.name)].append(None)


class ExternalBus(_BaseBus):
    """Initializes a class declared externally."""

    def __init__(self, name):
        self.name = name
        self.chs = {}
        self._trace = None

    def _init_ext_bus(self, lib_handle):
        self.chs = lib_handle.get_bus(self.name)

    def _trace(self):
        raise SMEException("Traces not supported for external buses")

    def _clock(self):
        raise SMEException("External buses are propagated by calling"
                           " the sme_propagate() method of libsme")


class Process(ABC):
    """Abstract base class for SME processes."""

    def __init__(self, name, ins,
                 outs, *args, **kwargs):
        self._name = name
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

    def setup(self, buses, *args, **kwargs) -> None:
        raise UnimplementedMethodException(
            "All subclasses of " + self.__class__.__name__ +
            " must implement the setup method")

    def _clock(self, i: int=1) -> None:
        while i > 0:
            self.run()
            i -= 1

    @abstractmethod
    def run(self):
        pass


class SimulationProcess(Process):
    """
    A process is purely used simulation.

    Functionally identical to Process
    """

    pass


def extends(file_name, options=""):
    """Extend a network with definitions from an SMEIL program."""
    def f(original_class):
        # From: https://stackoverflow.com/a/682242/9175124
        orig_init = original_class.__init__
        # make copy of original __init__, so we can call it without recursion

        def __init__(self, id, *args, **kws):
            self.__id = id
            self.puppeteer = True
            self.lib_handle = _LibSme(file_name, options)

            orig_init(self, *args, **kws)

        original_class.__init__ = __init__
        return original_class
    return f


class Network(ABC):
    """Class for declaring a network."""

    def __init__(self, name, *args, **kwargs):
        self.name = name
        #print("Name was ", name)
        self.funs = []
        self.busses = []
        self.externals = []

        if not hasattr(self, "puppeteer"):
            self.puppeteer = False

        self.tracing = False
        self.trace = {}
        # FIXME: This will give us class init time which may be a bit wierd
        self.trace_file = "trace-" + time.ctime().replace(" ", "-") + ".txt"
        self.graph = False
        self.graph_file = "graph-" + time.ctime().replace(" ", "-") + ".dot"

        #print("__init__:", args, kwargs)
        self.deferred_init = lambda: self.wire(*args, **kwargs)

    def _init(self):
        self.deferred_init()

    def add(self, obj):
        """Add a Bus or Process to the network.

        This functions should be called from within the wire method of a
        network to tell the network about declared entities.
        """
        if isinstance(obj, Bus):
            obj._parent_name = self.name
            if self.tracing:
                obj._setup_trace(self.trace)
            self.busses.append(obj)
        elif isinstance(obj, ExternalBus):
            if not self.puppeteer:
                raise SMEException("External buses may only be defined"
                                   " when we are extending an"
                                   " SMEIL-defined network. Use the"
                                   " @extends decorator")
            obj._init_ext_bus(self.lib_handle)
        elif isinstance(obj, Process):
            self.funs.append(obj)
        else:
            raise TypeError("Only instances deriving from Bus or Function can "
                            "be added to the network")


    @abstractmethod
    def wire(self, *args, **kwargs):
        pass

    def _set_opts(self, opts):
        if opts.trace:
            if self.puppeteer:
                raise Exception("Genertaing traces is handeled by libsme")
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
                bus._clock(tracing=self.tracing)
            if self.puppeteer:
                self.lib_handle.propagate()
            for fun in self.funs:
                fun._clock()
            if self.puppeteer:
                self.lib_handle.tick()

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
                for vals in zip(*otrace.values()):
                    # TODO: Check that values are within the bounds of their
                    # specified width.
                    f.write(",".join(map(lambda x: "U" if x is None else
                                         str(int(x)), vals)) + "\n")


class SME:
    """Class used for initializing and running SME networks."""

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
        """Return the top-level network."""
        return self._network

    @network.setter
    def network(self, network):
        """Set the top-level network."""
        if not isinstance(network, Network):
            raise TypeError("network must be an instance of the Network class")
        network._set_opts(self.opts)
        self._network = network
        network._init()

    @property
    def remaining_options(self):
        """Get non-SME options passed to the command line."""
        return self.unparsed_opts
