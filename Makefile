all: libsme.h sme/_libsme_ffi.py

libsme.h:/home/truls/uni/thesis/libsme/cbits/libsme.h
	cp $< $@

sme/_libsme_ffi.py:libsme.h
	python3.6 sme/libsme_support_build.py
