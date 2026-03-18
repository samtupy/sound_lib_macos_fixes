
__version__ = '0.1'
__versionTime__ = '2009-11-15'
__author__ = 'Max Kolosov <maxkolosov@inbox.ru>'

import os, sys, ctypes
from . import pybass
from .find_library import find_library

_bassopus_lib   = find_library('bassopus')
bassopus_module = _bassopus_lib.module
func_type       = _bassopus_lib.func_type
pybass.BASS_PluginLoad(_bassopus_lib.path, 0)

QWORD = pybass.QWORD
HSTREAM = pybass.HSTREAM
DOWNLOADPROC = pybass.DOWNLOADPROC
BASS_FILEPROCS = pybass.BASS_FILEPROCS

# BASS_CHANNELINFO type
BASS_CTYPE_STREAM_OPUS = 0x11200


#HSTREAM BASSOPUSDEF(BASS_OPUS_StreamCreateFile)(BOOL mem, const void *file, QWORD offset, QWORD length, DWORD flags);
BASS_OPUS_StreamCreateFile = func_type(HSTREAM, ctypes.c_byte, ctypes.c_void_p, QWORD, QWORD, ctypes.c_ulong)(('BASS_OPUS_StreamCreateFile', bassopus_module))
#HSTREAM BASSFLACDEF(BASS_FLAC_StreamCreateURL)(const char *url, DWORD offset, DWORD flags, DOWNLOADPROC *proc, void *user);
BASS_OPUS_StreamCreateURL = func_type(HSTREAM, ctypes.c_char_p, ctypes.c_ulong, ctypes.c_ulong, DOWNLOADPROC, ctypes.c_void_p)(('BASS_OPUS_StreamCreateURL', bassopus_module))
#HSTREAM BASSFLACDEF(BASS_FLAC_StreamCreateFileUser)(DWORD system, DWORD flags, const BASS_FILEPROCS *procs, void *user);
BASS_OPUS_StreamCreateFileUser = func_type(HSTREAM, ctypes.c_ulong, ctypes.c_ulong, ctypes.POINTER(BASS_FILEPROCS), ctypes.c_void_p)(('BASS_OPUS_StreamCreateFileUser', bassopus_module))

