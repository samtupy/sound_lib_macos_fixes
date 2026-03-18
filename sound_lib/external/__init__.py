from __future__ import absolute_import
import sys

from .find_library import is_android, is_ios

# Core add-ons available on all supported platforms
from . import pybassopus

# Windows-only libraries
if sys.platform == 'win32':
    from . import pybasswma

# bass_aac: Windows + Android (no iOS package available from Un4seen)
if sys.platform == 'win32' or is_android():
    from . import pybass_aac

# bass_alac: Windows + Android only
if sys.platform == 'win32' or is_android():
    from . import pybass_alac

# These are available on all platforms including macOS and mobile
from . import pybassflac
from . import pybassmidi
