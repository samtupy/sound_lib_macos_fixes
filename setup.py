"""Custom wheel building for sound_lib.

When platform-specific lib subdirectories exist under sound_lib/lib/
(populated by update_bass_libs.py), the build produces a platform-specific
wheel that contains only the current platform's BASS libraries placed
directly in the flat sound_lib/lib/ structure that find_library.py expects.

If no platform subdirectories exist (already flat or a dev checkout with only
flat libs), the build falls back to a normal py3-none-any universal wheel.
"""
import base64
import hashlib
import sysconfig
import zipfile
from pathlib import Path

from setuptools import setup
from setuptools.command.bdist_wheel import bdist_wheel as _bdist_wheel

_ALL_PLATFORM_SUBDIRS = frozenset((
    "windows_x86", "windows_x64",
    "linux_x64", "linux_x86", "linux_aarch64", "linux_armhf",
    "macos",
    "android_arm64-v8a", "android_armeabi-v7a", "android_x86", "android_x64",
    "iphoneos", "iphonesimulator",
))


def _detect_platform_subdir() -> "str | None":
    """Map sysconfig.get_platform() to our lib subdir name."""
    try:
        raw = sysconfig.get_platform()
    except Exception:
        return None
    p = raw.lower().replace("-", "_").replace(".", "_")
    if p == "win_amd64":
        return "windows_x64"
    if p in ("win32", "win_x86"):
        return "windows_x86"
    if p.startswith("macosx_"):
        return "macos"
    if "iphoneos" in p:
        return "iphoneos"
    if "iphonesimulator" in p:
        return "iphonesimulator"
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
    if p.startswith("linux_"):
        m = p[len("linux_"):]
        if "x86_64" in m or "amd64" in m:
            return "linux_x64"
        if "aarch64" in m or "arm64" in m:
            return "linux_aarch64"
        if "armv7l" in m or "armhf" in m:
            return "linux_armhf"
        if "i686" in m or "i386" in m:
            return "linux_x86"
        return "linux_x64"
    return None


def _sha256_record(data: bytes) -> str:
    digest = hashlib.sha256(data).digest()
    return "sha256=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def _rewrite_wheel(wheel_path: Path, platform_subdir: str) -> None:
    """Rewrite wheel in-place: keep only libs for *platform_subdir* at flat lib/.

    Files matching sound_lib/lib/{platform_subdir}/{file} are moved to
    sound_lib/lib/{file}.  All other platform subdir entries are dropped.
    The WHEEL RECORD is rebuilt from scratch to reflect the new paths/hashes.
    """
    lib_prefix = "sound_lib/lib/"
    tmp = wheel_path.with_suffix(".tmp")
    record_path: "str | None" = None
    new_record: "list[str]" = []

    with zipfile.ZipFile(wheel_path, "r") as zin, \
         zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as zout:

        for item in zin.infolist():
            name = item.filename

            # Locate the RECORD entry to rebuild later.
            if name.endswith("/RECORD"):
                record_path = name
                continue

            # Handle sound_lib/lib/ entries.
            if name.startswith(lib_prefix) and not name.endswith("/"):
                rest = name[len(lib_prefix):]
                parts = rest.split("/")
                if parts[0] in _ALL_PLATFORM_SUBDIRS:
                    # Keep only the target platform's files, rewritten to flat path.
                    if parts[0] == platform_subdir and len(parts) == 2 and parts[1]:
                        new_name = lib_prefix + parts[1]
                        data = zin.read(name)
                        info = zipfile.ZipInfo(new_name)
                        info.compress_type = zipfile.ZIP_DEFLATED
                        zout.writestr(info, data)
                        new_record.append(
                            f"{new_name},{_sha256_record(data)},{len(data)}"
                        )
                    # All other platform subdir files are silently dropped.
                    continue

            # Copy everything else verbatim.
            data = zin.read(name)
            zout.writestr(item, data)
            new_record.append(f"{name},{_sha256_record(data)},{len(data)}")

        # Rebuild RECORD.
        if record_path:
            new_record.append(f"{record_path},,")
            zout.writestr(record_path, "\r\n".join(new_record) + "\r\n")

    wheel_path.unlink()
    tmp.rename(wheel_path)


class bdist_wheel_platform(_bdist_wheel):
    """bdist_wheel subclass that produces a platform-specific wheel when
    platform lib subdirectories are present under sound_lib/lib/.

    If no platform subdirs exist the command behaves identically to the
    standard bdist_wheel, producing a py3-none-any wheel.
    """

    def _has_platform_subdirs(self) -> bool:
        lib_dir = Path("sound_lib/lib")
        return any((lib_dir / d).is_dir() for d in _ALL_PLATFORM_SUBDIRS)

    def get_tag(self) -> "tuple[str, str, str]":
        python, abi, plat = super().get_tag()
        if self._has_platform_subdirs():
            # Override the 'any' platform with the actual build platform so
            # pip only installs this wheel on a matching system.
            plat = (
                sysconfig.get_platform()
                .lower()
                .replace("-", "_")
                .replace(".", "_")
            )
        return python, abi, plat

    def run(self) -> None:
        super().run()

        if not self._has_platform_subdirs():
            return  # Universal wheel; nothing to rewrite.

        platform_subdir = _detect_platform_subdir()
        if platform_subdir is None:
            return

        lib_dir = Path("sound_lib/lib")
        if not (lib_dir / platform_subdir).is_dir():
            return  # No libs for this platform; leave wheel as-is.

        dist_dir = Path(self.dist_dir)
        for whl in sorted(dist_dir.glob("*.whl")):
            _rewrite_wheel(whl, platform_subdir)


setup(cmdclass={"bdist_wheel": bdist_wheel_platform})
