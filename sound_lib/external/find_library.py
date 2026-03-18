"""Platform-aware Bass library finder and loader.

Usage:
    from sound_lib.external.find_library import find_library

    _lib = find_library("bassmix")
    bassmix_module = _lib.module
    func_type       = _lib.func_type
    # path string for BASS_PluginLoad:
    pybass.BASS_PluginLoad(_lib.path, 0)
"""
import ctypes
import os
import platform
import shutil
import sys
from pathlib import Path
from typing import Optional


class LibraryInfo:
    """Holds a loaded ctypes library and its associated metadata."""

    __slots__ = ("module", "path", "func_type")

    def __init__(self, module, path: str, func_type):
        self.module = module       # ctypes.WinDLL / ctypes.CDLL instance
        self.path = path           # absolute string path (for BASS_PluginLoad)
        self.func_type = func_type # ctypes.WINFUNCTYPE or ctypes.CFUNCTYPE


# -----------------------------------------------------------------------
# All known platform subdirectory names (must match bass_updater/config.py)
# -----------------------------------------------------------------------

_ALL_PLATFORM_SUBDIRS = frozenset((
    "windows_x86", "windows_x64",
    "linux_x64", "linux_x86", "linux_aarch64", "linux_armhf",
    "macos",
    "android_arm64-v8a", "android_armeabi-v7a", "android_x86", "android_x64",
    "iphoneos", "iphonesimulator",
))


# -----------------------------------------------------------------------
# Module-level state
# -----------------------------------------------------------------------

_LIB_DIR: Optional[Path] = None
_STAGED = False


def _get_lib_dir() -> Path:
    global _LIB_DIR
    if _LIB_DIR is None:
        _LIB_DIR = Path(__file__).parent.parent / "lib"
    return _LIB_DIR


# -----------------------------------------------------------------------
# Platform detection helpers
# -----------------------------------------------------------------------

def is_android() -> bool:
    """Return True when running on Android (Beeware/Chaquopy)."""
    if sys.platform == "android":
        return True
    return sys.platform == "linux" and bool(os.environ.get("ANDROID_DATA"))


def is_ios() -> bool:
    """Return True when running inside a Beeware iOS app."""
    if sys.platform == "ios":
        return True
    return bool(os.environ.get("BRIEFCASE_MAIN_MODULE")) and sys.platform == "darwin"


def _subdir_from_sysconfig() -> Optional[str]:
    """Map sysconfig.get_platform() to one of our platform subdir names.

    sysconfig.get_platform() is the same source Python's wheel tag system uses
    (via the 'packaging' library) to decide which wheels are compatible with
    the current interpreter.  Using it here keeps our platform detection
    consistent with pip's own selection logic.

    Examples of what sysconfig.get_platform() returns:
      Windows 64-bit  ->  "win-amd64"
      Windows 32-bit  ->  "win32"
      macOS arm64     ->  "macosx-14-arm64"
      Linux x86_64    ->  "linux-x86_64"
      Linux aarch64   ->  "linux-aarch64"
      Linux armhf     ->  "linux-armv7l"
      iOS (Py 3.13+)  ->  "ios-iphoneos-arm64"
      Android arm64   ->  "android-arm64-v8a"
    """
    import sysconfig
    try:
        raw = sysconfig.get_platform()
    except Exception:
        return None

    # Normalise: lowercase, replace separators with underscores
    p = raw.lower().replace("-", "_").replace(".", "_")

    # Windows
    if p == "win_amd64":
        return "windows_x64"
    if p in ("win32", "win_x86"):
        return "windows_x86"

    # macOS — all version/arch variants map to a single dylib set
    if p.startswith("macosx_"):
        return "macos"

    # iOS (Python 3.13+)
    if "iphoneos" in p:
        return "iphoneos"
    if "iphonesimulator" in p:
        return "iphonesimulator"

    # Android (Python 3.13+)
    if "android" in p:
        if "arm64_v8a" in p or "aarch64" in p:
            return "android_arm64-v8a"
        if "armeabi_v7a" in p or "armv7" in p:
            return "android_armeabi-v7a"
        if "x86_64" in p:
            return "android_x64"
        if "x86" in p:
            return "android_x86"
        return None

    # Linux
    if p.startswith("linux_"):
        m = p[len("linux_"):]
        if "x86_64" in m or "amd64" in m:
            return "linux_x64"
        if "aarch64" in m or "arm64" in m:
            return "linux_aarch64"
        if "armv7l" in m or "armhf" in m:
            return "linux_armhf"
        if "i686" in m or "i386" in m or m == "x86":
            return "linux_x86"
        return "linux_x64"  # best-effort fallback

    return None


def _detect_platform_subdir() -> Optional[str]:
    """Return the sound_lib/lib/ subdirectory name for the current runtime.

    Tries sysconfig.get_platform() first (same source as Python wheel tags),
    then falls back to manual sys.platform + platform.machine() inspection
    for edge cases (older Python builds, unusual environments).
    """
    # Primary: sysconfig — matches what pip uses for wheel compatibility
    subdir = _subdir_from_sysconfig()
    if subdir:
        return subdir

    # Fallback: manual detection for mobile / edge cases
    if is_ios():
        return "iphoneos"

    if is_android():
        machine = platform.machine().lower()
        if "aarch64" in machine or "arm64" in machine:
            return "android_arm64-v8a"
        elif "arm" in machine:
            return "android_armeabi-v7a"
        elif "x86_64" in machine or "amd64" in machine:
            return "android_x64"
        else:
            return "android_x86"

    if sys.platform == "win32":
        return "windows_x64" if platform.architecture()[0] == "64bit" else "windows_x86"

    if sys.platform == "darwin":
        return "macos"

    if sys.platform == "linux":
        machine = platform.machine().lower()
        if machine in ("x86_64", "amd64"):
            return "linux_x64"
        elif machine in ("i386", "i486", "i586", "i686"):
            return "linux_x86"
        elif machine in ("aarch64", "arm64"):
            return "linux_aarch64"
        elif "arm" in machine:
            return "linux_armhf"
        else:
            return "linux_x64"

    return None


def _get_filename(libname: str) -> str:
    """Return the expected filename for *libname* on the current platform."""
    if sys.platform == "win32":
        return f"{libname}.dll"
    elif sys.platform == "darwin" and not is_ios():
        return f"lib{libname}.dylib"
    elif is_ios():
        return f"{libname}.so"
    else:
        return f"lib{libname}.so"


# -----------------------------------------------------------------------
# One-time staging: copy platform libs to flat lib/ dir, prune the rest
# -----------------------------------------------------------------------

def _is_subpath(child: Path, parent: Path) -> bool:
    """Return True if *child* is at or below *parent* (resolved paths)."""
    try:
        child.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def _stage_platform_libs() -> None:
    """Stage platform-specific libs into the flat sound_lib/lib/ directory.

    On first call after pip install this:
      1. Detects the current platform using sysconfig.get_platform()
      2. Copies all files from sound_lib/lib/{platform_subdir}/ to the flat
         sound_lib/lib/ directory (e.g. lib/bassmix.dll, lib/libbass.so …)
      3. Removes every platform subdirectory to reclaim disk space

    Subsequent calls are a near-instant no-op: if no platform subdirectory
    exists, staging has already been done.

    On read-only installs (e.g. system-wide site-packages) staging is skipped
    silently; find_library() falls back to looking in the platform subdir.

    On mobile (iOS / Android) staging is skipped because the system / app
    bundle linker already provides the libraries at the right paths.
    """
    global _STAGED
    if _STAGED:
        return

    lib_dir = _get_lib_dir()

    # If no platform subdirs exist, staging was already done (or this is a
    # development checkout where libs live in the flat dir already).
    if not any((lib_dir / d).is_dir() for d in _ALL_PLATFORM_SUBDIRS):
        _STAGED = True
        return

    # Skip staging in development checkouts (lib_dir not under site-packages).
    # This prevents the updater-populated platform subdirs from being pruned
    # when a developer imports sound_lib from the source tree.
    try:
        import site as _site
        _sp = getattr(_site, "getsitepackages", lambda: [])()
        if not any(_is_subpath(lib_dir, Path(sp)) for sp in _sp):
            _STAGED = True
            return
    except Exception:
        pass  # If we can't determine, proceed with staging

    # Mobile: system/app-bundle linker handles lib loading; nothing to stage.
    if is_ios() or is_android():
        _STAGED = True
        return

    subdir = _detect_platform_subdir()
    if not subdir:
        _STAGED = True
        return

    src_dir = lib_dir / subdir
    if not src_dir.is_dir():
        _STAGED = True
        return

    staged_ok = False
    try:
        for f in src_dir.iterdir():
            if f.is_file():
                dst = lib_dir / f.name
                if not dst.exists():
                    shutil.copy2(f, dst)
        staged_ok = True
    except (OSError, PermissionError):
        pass  # Read-only install — fall back to subdir lookup in find_library

    if staged_ok:
        # Prune all platform subdirectories; we no longer need them.
        # Handles upgrades correctly: pip re-installs the subdirs on upgrade,
        # which makes the platform-subdirs-exist check True again, triggering
        # a fresh staging cycle.
        for subdir_name in _ALL_PLATFORM_SUBDIRS:
            candidate = lib_dir / subdir_name
            try:
                if candidate.is_dir():
                    shutil.rmtree(candidate)
            except (OSError, PermissionError):
                pass  # Best-effort; leftover dirs are harmless

    _STAGED = True


# -----------------------------------------------------------------------
# Public API
# -----------------------------------------------------------------------

def find_library(libname: str, rtld_global: bool = False) -> LibraryInfo:
    """Find and load a BASS library by name.

    On desktop platforms (Windows / Linux / macOS) this stages the
    platform-appropriate lib files to the flat sound_lib/lib/ directory on
    first call (or the sound_lib.pth hook will have done it already), then
    loads from there.  On mobile the system linker is expected to have already
    made the library available.

    Args:
        libname:     Library name without any prefix or extension
                     (e.g. "bass", "bassmix", "bass_fx", "tags").
        rtld_global: If True, load with RTLD_GLOBAL so symbols are visible to
                     subsequently loaded libraries.  Required for "bass" itself.

    Returns:
        LibraryInfo with .module, .path, and .func_type populated.

    Raises:
        OSError: When the library file cannot be located.
    """
    _stage_platform_libs()

    lib_dir = _get_lib_dir()
    filename = _get_filename(libname)

    # 1. Flat lib dir (populated by staging)
    path = lib_dir / filename

    # 2. Platform-specific subdir fallback (staging failed / read-only install)
    if not path.exists():
        subdir = _detect_platform_subdir()
        if subdir:
            path = lib_dir / subdir / filename

    # 3. Mobile fallback: let the OS linker find the library by name alone
    if not path.exists() and (is_ios() or is_android()):
        path_str = filename
        try:
            module = ctypes.CDLL(path_str)
            return LibraryInfo(module, path_str, ctypes.CFUNCTYPE)
        except OSError:
            pass

    if not path.exists():
        raise OSError(
            f"Cannot find library '{libname}': '{filename}' not found in '{lib_dir}'"
        )

    path_str = str(path)

    if sys.platform == "win32":
        module = ctypes.WinDLL(path_str)
        func_type = ctypes.WINFUNCTYPE
    else:
        if rtld_global:
            module = ctypes.CDLL(path_str, mode=ctypes.RTLD_GLOBAL)
        else:
            module = ctypes.CDLL(path_str)
        func_type = ctypes.CFUNCTYPE

    return LibraryInfo(module, path_str, func_type)
