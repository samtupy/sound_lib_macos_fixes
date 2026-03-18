"""Extract and identify library files from Bass archive zips."""
import os
import shutil
import zipfile
from pathlib import Path
from typing import Dict, Optional

from .config import SO_STEMS, TEMP_DIR, WIN_DLL_STEMS


# Maps archive-internal arch directory names -> our platform dir names
_LINUX_ARCH_MAP: Dict[str, str] = {
    "x86_64":  "linux_x64",
    "x86":     "linux_x86",
    "aarch64": "linux_aarch64",
    "armhf":   "linux_armhf",
}

_ANDROID_ARCH_MAP: Dict[str, str] = {
    "arm64-v8a":   "android_arm64-v8a",
    "armeabi-v7a": "android_armeabi-v7a",
    "x86":         "android_x86",
    "x86_64":      "android_x64",
}


class ArchiveExtractor:
    """Extract and categorise library files from Bass zip archives."""

    def __init__(self):
        self.temp_dir = TEMP_DIR

    def extract_archive(
        self, archive_path: Path, library_name: str, archive_type: str
    ) -> Dict[str, Path]:
        """Extract a zip archive and return files keyed by destination platform dir.

        Args:
            archive_path:  Path to downloaded zip file.
            library_name:  Internal library name (e.g. "bass", "bass_fx").
            archive_type:  One of "win", "linux", "macos", "android", "ios".

        Returns:
            Dict mapping platform-dir name -> extracted source file path.
        """
        extract_dir = self.temp_dir / f"{library_name}_{archive_type}_extracted"
        extract_dir.mkdir(parents=True, exist_ok=True)

        try:
            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(extract_dir)
        except zipfile.BadZipFile:
            raise RuntimeError(f"Corrupted zip file: {archive_path}")

        dispatch = {
            "win":     self._extract_win,
            "linux":   self._extract_linux,
            "macos":   self._extract_macos,
            "android": self._extract_android,
            "ios":     self._extract_ios,
        }
        extractor = dispatch.get(archive_type)
        if extractor is None:
            return {}
        return extractor(extract_dir, library_name)

    # ------------------------------------------------------------------
    # Per-archive-type extraction helpers
    # ------------------------------------------------------------------

    def _extract_win(self, extract_dir: Path, libname: str) -> Dict[str, Path]:
        """Windows zip: root-level DLL -> windows_x86, x64/ subdir -> windows_x64."""
        dll_stem = WIN_DLL_STEMS.get(libname, libname)
        target_name = f"{dll_stem}.dll"
        results: Dict[str, Path] = {}

        for fpath in extract_dir.rglob(target_name):
            rel_parts = [p.lower() for p in fpath.relative_to(extract_dir).parts[:-1]]
            if "x64" in rel_parts or "64" in rel_parts:
                results["windows_x64"] = fpath
            else:
                results["windows_x86"] = fpath

        return results

    def _extract_linux(self, extract_dir: Path, libname: str) -> Dict[str, Path]:
        """Linux zip: libs/{arch}/lib{name}.so structure."""
        return self._extract_shared_libs(extract_dir, libname, _LINUX_ARCH_MAP)

    def _extract_android(self, extract_dir: Path, libname: str) -> Dict[str, Path]:
        """Android zip: libs/{arch}/lib{name}.so structure (same layout as Linux)."""
        return self._extract_shared_libs(extract_dir, libname, _ANDROID_ARCH_MAP)

    def _extract_shared_libs(
        self, extract_dir: Path, libname: str, arch_map: Dict[str, str]
    ) -> Dict[str, Path]:
        """Shared helper for Linux/Android: look for libs/{arch}/lib{name}.so.

        Uses SO_STEMS to handle libraries whose archive filename differs from
        the library key (e.g. bass_alac ships as libbassalac.so).
        """
        stem = SO_STEMS.get(libname, libname)
        target_name = f"lib{stem}.so"
        results: Dict[str, Path] = {}

        for arch_key, dest_dir in arch_map.items():
            candidate = extract_dir / "libs" / arch_key / target_name
            if candidate.exists():
                results[dest_dir] = candidate

        return results

    def _extract_macos(self, extract_dir: Path, libname: str) -> Dict[str, Path]:
        """macOS zip: lib{name}.dylib in the archive root."""
        stem = SO_STEMS.get(libname, libname)
        target_name = f"lib{stem}.dylib"
        for fpath in extract_dir.rglob(target_name):
            return {"macos": fpath}
        return {}

    def _extract_ios(self, extract_dir: Path, libname: str) -> Dict[str, Path]:
        """iOS zip: xcframework bundle structure.

        Pattern (device):    {name}.xcframework/ios-arm64_armv7_armv7s/{name}.framework/{name}
        Pattern (simulator): {name}.xcframework/ios-arm64*simulator/{name}.framework/{name}

        The binary inside the framework has no file extension.  We copy it out
        as {name}.so so Briefcase can recreate the .framework during packaging.
        """
        results: Dict[str, Path] = {}

        for xcfw_dir in extract_dir.rglob("*.xcframework"):
            if not xcfw_dir.is_dir():
                continue

            for variant_dir in xcfw_dir.iterdir():
                if not variant_dir.is_dir():
                    continue

                is_simulator = "simulator" in variant_dir.name.lower()
                dest_key = "iphonesimulator" if is_simulator else "iphoneos"

                # Try the canonical name, the SO_STEMS override, then no-underscore variant
                so_stem = SO_STEMS.get(libname, libname)
                for candidate_name in dict.fromkeys((libname, so_stem, libname.replace("_", ""))):
                    binary = variant_dir / f"{candidate_name}.framework" / candidate_name
                    if binary.exists():
                        results[dest_key] = binary
                        break

        return results

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def cleanup_extraction(self, library_name: str, archive_type: str) -> None:
        """Remove the extraction working directory for a library+archive_type pair."""
        extract_dir = self.temp_dir / f"{library_name}_{archive_type}_extracted"
        if extract_dir.exists():
            shutil.rmtree(extract_dir)
