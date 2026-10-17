#!/usr/bin/env python3
"""Atomically publish a same-filesystem directory, refusing any existing entry."""
import ctypes
import os
import sys

source, destination = map(os.fsencode, sys.argv[1:])
libc = ctypes.CDLL(None, use_errno=True)
if sys.platform == 'darwin':
    rename = libc.renamex_np
    rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
    result = rename(source, destination, 4)  # RENAME_EXCL
elif sys.platform.startswith('linux'):
    rename = libc.renameat2
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    result = rename(-100, source, -100, destination, 1)  # AT_FDCWD, RENAME_NOREPLACE
else:
    raise SystemExit('Atomic no-replace directory publication is unsupported on this platform')
if result:
    error = ctypes.get_errno()
    raise OSError(error, os.strerror(error), os.fsdecode(destination))
