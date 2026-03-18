"""Configuration for Bass library updater."""
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent

# Library directory (new flat-platform structure)
LIB_DIR = PROJECT_ROOT / "sound_lib" / "lib"

# Version tracking file
VERSION_FILE = PROJECT_ROOT / "bass_versions.json"

# Un4seen website configuration
BASS_BASE_URL = "https://www.un4seen.com"
BASS_PAGE_URL = f"{BASS_BASE_URL}/bass.html"
FILES_BASE_URL = f"{BASS_BASE_URL}/files"

# Download settings
DOWNLOAD_TIMEOUT = 30
MAX_RETRIES = 3
RETRY_BACKOFF_FACTOR = 1
CHUNK_SIZE = 8192

# Temp directory for downloads
TEMP_DIR = PROJECT_ROOT / "temp_bass_update"


class LibraryDef(NamedTuple):
    """Definition of a Bass library for the updater."""
    display_name: str          # Human-readable name shown on un4seen.com
    file_prefix: str           # Base filename prefix used in zip names (e.g. "bass24")
    url_subpath: str           # Sub-path under /files/ (e.g. "z/0" for third-party)
    archive_platforms: List[str]  # Archive types supported: win/linux/macos/android/ios
    mobile_prefix: Optional[str] = None  # Override prefix for ios/android zips (e.g. tags)


# Library definitions keyed by our internal name.
# archive_platforms controls which zip archives are fetched and extracted.
BASS_LIBRARIES: Dict[str, LibraryDef] = {
    "bass":       LibraryDef("BASS",       "bass24",       "",    ["win", "linux", "macos", "android", "ios"]),
    "bassopus":   LibraryDef("BASSOPUS",   "bassopus24",   "",    ["win", "linux", "macos", "android", "ios"]),
    "bassflac":   LibraryDef("BASSFLAC",   "bassflac24",   "",    ["win", "linux", "macos", "android", "ios"]),
    "bassmidi":   LibraryDef("BASSMIDI",   "bassmidi24",   "",    ["win", "linux", "macos", "android", "ios"]),
    "bassmix":    LibraryDef("BASSmix",    "bassmix24",    "",    ["win", "linux", "macos", "android", "ios"]),
    "bassenc":    LibraryDef("BASSenc",    "bassenc24",    "",    ["win", "linux", "macos", "android", "ios"]),
    "basswasapi": LibraryDef("BASSWASAPI", "basswasapi24", "",    ["win"]),
    "basswma":    LibraryDef("BASSWMA",    "basswm24",     "",    ["win"]),
    # bass_aac: Windows + Android only (no iOS or Linux package from Un4seen)
    "bass_aac":   LibraryDef("BASS_AAC",   "bass_aac24",   "z/2", ["win", "android"]),
    # bass_alac: Windows + Android only
    "bass_alac":  LibraryDef("BASSALAC",   "bassalac24",   "",    ["win", "android"]),
    # bass_fx is a third-party add-on hosted under files/z/0/
    "bass_fx":    LibraryDef("BASS FX",    "bass_fx24",    "z/0", ["win", "linux", "macos", "android", "ios"]),
    # tags uses a different zip prefix for mobile ("basstags") vs desktop ("tags19")
    "tags":       LibraryDef("Tags",       "tags19",       "z/3", ["win", "linux", "macos", "android", "ios"],
                             mobile_prefix="basstags"),
}

# Archive platform definitions.
# key -> (url_suffix_for_zip, [dest_platform_directory_names])
# Each archive type may yield files for one or more destination platform dirs.
ARCHIVE_PLATFORMS: Dict[str, tuple] = {
    "win":     ("",         ["windows_x86", "windows_x64"]),
    "linux":   ("-linux",   ["linux_x64", "linux_x86", "linux_aarch64", "linux_armhf"]),
    "macos":   ("-osx",     ["macos"]),
    "android": ("-android", ["android_arm64-v8a", "android_armeabi-v7a", "android_x86", "android_x64"]),
    "ios":     ("-ios",     ["iphoneos", "iphonesimulator"]),
}

# Some Windows DLL names in the archive differ from our internal library key.
# Maps internal lib key -> DLL stem (without .dll extension) as found in the archive.
WIN_DLL_STEMS: Dict[str, str] = {
    "bass_alac": "bassalac",   # archive ships bassalac.dll, not bass_alac.dll
}

# Shared-library stems (Linux / Android / macOS) that differ from the library key.
# Maps lib key -> stem as found in the archive (no lib-prefix, no extension).
# The target filename written into sound_lib/lib/ always uses the lib key so
# callers can uniformly do find_library("bass_alac") regardless of platform.
SO_STEMS: Dict[str, str] = {
    "bass_alac": "bassalac",   # archive ships libbassalac.so
}
