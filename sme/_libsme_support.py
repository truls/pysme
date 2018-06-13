"""
libsme FFI interface.

Contains code for interfacing with libsme through the FFI and provides a
channel abstraction for use within buses.
"""
from os.path import isfile, dirname, join
import sys
import os

from ._libsme_ffi import ffi
from ._bus import _BaseChannel
from ._exceptions import SMEException

class _LibSmeException(Exception):
    pass

class _LibSme:

    def __init__(self, sme_file, options):
        self.sme = None

        sme_file = join(dirname(sys.argv[0]), sme_file)
        if not isfile(sme_file):
            raise FileNotFoundError("File not found " + sme_file)
        try:
            lib = os.environ["LIBSME_LIB"]
            sme = ffi.dlopen(lib)
        except (KeyError, OSError):
            raise FileNotFoundError("Couldn't locate the libsme library."
                                    " Please make sure that libsme.so"
                                    " and its dependencies are found in"
                                    " the folder set in the LIBSME_LIB"
                                    " environment variable.")
        ctx = sme.sme_init()
        self.ctx = ctx
        self.sme = sme
        self.ffi = ffi

        file_arg = ffi.new("char[]", bytes(sme_file, 'utf-8'))
        if options is None:
            argc = 0
            argv = ffi.NULL
        else:
            argc = len(options)
            argvl = list(map(lambda x: ffi.new("char[]", bytes(x, 'utf-8')),
                                                options))
            argv = ffi.new("char*[]", argvl)
        self._check_err(lambda x: sme.sme_open_file(x, file_arg, argc, argv))

        bm = sme.sme_get_busmap(ctx)
        bus_map = {}
        for i in range(bm.len):
            bus_name = str(ffi.string(bm.chans[i].bus_name), 'utf-8')
            chan_name = str(ffi.string(bm.chans[i].chan_name), 'utf-8')
            if bus_name not in bus_map:
                bus_map[bus_name] = {}

            bus_map[bus_name][chan_name] =\
                _ExtChannel(name=chan_name,
                            chan_ref=bm.chans[i],
                            chan_type=bm.chans[i].type,
                            library_handle=self.sme,
                            ffi_ref=self.ffi)
        sme.sme_free_busmap(bm)

        self.bus_map = bus_map

    def get_bus(self, name):
        return self.bus_map[name]

    def _check_err(self, f):
        f(self.ctx)
        if self.sme.sme_has_failed(self.ctx):
            err = self.ffi.string(self.sme.sme_get_error_buffer(self.ctx))
            raise _LibSmeException(str(err, 'utf-8'))

    def propagate(self):
        self._check_err(self.sme.sme_propagate)

    def tick(self):
        self._check_err(self.sme.sme_tick)

    def finalize(self):
        self._check_err(self.sme.sme_finalize)

    def gen_code(self, f):
        s = self.ffi.new("char[]", bytes(f, 'utf-8'))
        self._check_err(lambda x: self.sme.sme_gen_code(x, s))

    def __del__(self):
        # Only call free if library was actually instantiated
        if self.sme is not None:
            self.sme.sme_free(self.ctx)


class _ExtChannel(_BaseChannel):

    def __init__(self, *, name, chan_ref, chan_type, library_handle, ffi_ref):
        self._name = name
        self.chan_type = chan_type
        self.sme = library_handle
        self.read_ptr = chan_ref.read_ptr.value
        self.write_ptr = chan_ref.write_ptr.value
        self.write_value = chan_ref.write_ptr
        self.ffi = ffi_ref

    def _to_sme_int(self, signed, val):
        # Whatever val is, it must be cast-able to an integer
        val = int(val)
        # Number of bytes needed to represent val
        blen = (val.bit_length() + 7) // 8
        self.sme.sme_integer_resize(self.write_ptr.integer, blen)
        buf = self.ffi.buffer(self.write_ptr.integer.num, blen)
        buf[:] = abs(val).to_bytes(blen, 'little')
        # Set sign flag if value was negative
        self.write_ptr.integer.negative = val < 0 and signed

    def _from_sme_int(self, signed):
        buf = self.ffi.buffer(self.read_ptr.integer.num,
                              self.read_ptr.integer.len)
        val = int.from_bytes(buf, 'little')
        if self.read_ptr.integer.negative and signed:
            return -val
        else:
            return val

    def _bad_val_type(self):
        raise _LibSmeException("Unknown value type."
                               " There's a bug somewhere")

    @property
    def value(self):
        if self.chan_type == self.sme.SME_INT:
            return self._from_sme_int(True)
        elif self.chan_type == self.sme.SME_UINT:
            return self._from_sme_int(False)
        elif self.chan_type == self.sme.SME_BOOL:
            return self.read_ptr.boolean
        elif self.chan_type == self.sme.SME_FLOAT:
            return self.read_ptr.f32
        elif self.chan_type == self.sme.SME_DOUBLE:
            return self.read_ptr.f64
        else:
            self._bad_val_type()

    @value.setter
    def value(self, val):
        self.write_value.undef = 0;
        if self.chan_type == self.sme.SME_INT:
            self._to_sme_int(True, val)
        elif self.chan_type == self.sme.SME_UINT:
            self._to_sme_int(False, val)
        elif self.chan_type == self.sme.SME_BOOL:
            self.write_ptr.boolean = val
        elif self.chan_type == self.sme.SME_FLOAT:
            self.wrote_ptr.f32 = val
        elif self.chan_type == self.sme.SME_DOUBLE:
            self.write_ptr.f64 = val
        else:
            self._bad_val_type()

    def propagate(self):
        raise SMEException("Propagation of external buses"
                           " must be handled by calling the"
                           " sme_propagate() function of libsme")
