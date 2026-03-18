"""Executed at Python startup via the sound_lib.pth site hook.

Stages the platform-appropriate BASS libraries into the flat sound_lib/lib/
directory and removes the unused per-platform subdirectories.  This runs
once — on the first Python invocation after pip install — and then becomes a
near-instant no-op because the platform subdirectories will no longer exist.

Nothing here may raise an unhandled exception; a broken sound_lib.pth hook
would break *every* Python startup on this installation.
"""
from pathlib import Path

_lib_dir = Path(__file__).parent / "lib"

# Fast check: if no platform subdirectory exists, staging has already run.
# We do this without importing anything heavy to keep startup overhead minimal.
_KNOWN_SUBDIRS = (
    "windows_x86", "windows_x64",
    "linux_x64", "linux_x86", "linux_aarch64", "linux_armhf",
    "macos",
    "android_arm64-v8a", "android_armeabi-v7a", "android_x86", "android_x64",
    "iphoneos", "iphonesimulator",
)

if any((_lib_dir / d).is_dir() for d in _KNOWN_SUBDIRS):
    try:
        from sound_lib.external.find_library import _stage_platform_libs
        _stage_platform_libs()
    except Exception:
        pass  # Never break Python startup
