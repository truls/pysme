from cffi import FFI
from distutils.ccompiler import new_compiler


c = new_compiler()
# FIXME: This doesn't really give us the cross-platform-ness we wanted from
# using the distutils compiling functions
c.set_executables(preprocessor="cpp")
c.preprocess("libsme.h", output_file="libsme_ffiinclude.h")

with open("libsme_ffiinclude.h", "r") as f:
    src = "".join(f.readlines())

ffibuilder = FFI()
ffibuilder.set_source("sme._libsme_ffi", None)
ffibuilder.cdef(src)

if __name__ == "__main__":
    ffibuilder.compile(verbose=True)
