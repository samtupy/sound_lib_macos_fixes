from __future__ import absolute_import
"BASS_ALAC wrapper by Christopher Toth"""

import ctypes
import os
from . import pybass
from .find_library import find_library

_bass_alac_lib   = find_library('bass_alac')
bass_alac_module = _bass_alac_lib.module
func_type        = _bass_alac_lib.func_type
pybass.BASS_PluginLoad(_bass_alac_lib.path, 0)

BASS_TAG_MP4 = 7
BASS_CTYPE_STREAM_ALAC = 0x10e00


#HSTREAM BASSALACDEF(BASS_ALAC_StreamCreateFile)(BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_ALAC_StreamCreateFile = func_type(pybass.HSTREAM, ctypes.c_byte, ctypes.c_void_p, pybass.QWORD, pybass.QWORD, ctypes.c_ulong)

#HSTREAM BASSALACDEF(BASS_ALAC_StreamCreateFileUser)(DWORD system, DWORD flags, const BASS_FILEPROCS *procs, void *user);
BASS_ALAC_StreamCreateFileUser = func_type(pybass.HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_void_p)

