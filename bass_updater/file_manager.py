"""Manage Bass library file placement, naming, and backup."""
import shutil
from datetime import datetime
from pathlib import Path
from typing import Dict

from .config import ARCHIVE_PLATFORMS, LIB_DIR


def _target_filename(libname: str, dest_platform_dir: str) -> str:
    """Return the canonical filename for a library in a given platform directory.

    Naming conventions:
      Windows   ->  {name}.dll           (bass.dll, bassmix.dll, bass_fx.dll …)
      macOS     ->  lib{name}.dylib      (libbass.dylib, libbassmix.dylib …)
      iOS       ->  {name}.so            (bass.so, bassmix.so …)   no lib-prefix
      Linux/Android -> lib{name}.so      (libbass.so, libbassmix.so …)
    """
    if dest_platform_dir.startswith("windows"):
        return f"{libname}.dll"
    elif dest_platform_dir == "macos":
        return f"lib{libname}.dylib"
    elif dest_platform_dir.startswith("iphon"):   # iphoneos / iphonesimulator
        return f"{libname}.so"
    else:                                          # linux_* / android_*
        return f"lib{libname}.so"


class FileManager:
    """Install, back up, and restore Bass library files."""

    # Collect all known platform dirs from config for backup sweeps
    _ALL_PLATFORM_DIRS = [d for _, dirs in ARCHIVE_PLATFORMS.values() for d in dirs]

    def create_backup(self, library_name: str) -> Path:
        """Back up existing files for *library_name* across all platform dirs."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup_dir = Path(f"bass_backup_{library_name}_{timestamp}")
        backup_dir.mkdir(parents=True, exist_ok=True)

        for platform_dir in self._ALL_PLATFORM_DIRS:
            src_dir = LIB_DIR / platform_dir
            if not src_dir.exists():
                continue
            backup_sub = backup_dir / platform_dir
            backup_sub.mkdir(parents=True, exist_ok=True)
            for f in src_dir.iterdir():
                if f.is_file() and self._belongs_to(f, library_name):
                    shutil.copy2(f, backup_sub / f.name)

        return backup_dir

    def install_files(self, platform_files: Dict[str, Path], library_name: str) -> None:
        """Copy extracted files to their target platform directories.

        Args:
            platform_files: Mapping of platform-dir name -> source file path
                            (as returned by ArchiveExtractor.extract_archive).
            library_name:   Internal library name used to compute target filenames.
        """
        installed: list[Path] = []
        try:
            for dest_platform_dir, src_file in platform_files.items():
                target_dir = LIB_DIR / dest_platform_dir
                target_dir.mkdir(parents=True, exist_ok=True)

                filename = _target_filename(library_name, dest_platform_dir)
                target_file = target_dir / filename

                shutil.copy2(src_file, target_file)
                installed.append(target_file)
                rel = target_file.relative_to(LIB_DIR.parent.parent)
                print(f"  Installed: {rel}")

        except Exception as exc:
            # Roll back any files we already copied
            for f in installed:
                try:
                    f.unlink(missing_ok=True)
                except OSError:
                    pass
            raise RuntimeError(f"Failed to install {library_name}: {exc}") from exc

    def restore_from_backup(self, backup_dir: Path) -> None:
        """Restore previously backed-up files."""
        if not backup_dir.exists():
            return
        for sub in backup_dir.iterdir():
            if not sub.is_dir():
                continue
            target_dir = LIB_DIR / sub.name
            target_dir.mkdir(parents=True, exist_ok=True)
            for f in sub.iterdir():
                if f.is_file():
                    dst = target_dir / f.name
                    shutil.copy2(f, dst)
                    print(f"  Restored: {f.name} -> {sub.name}/")

    def cleanup_backup(self, backup_dir: Path) -> None:
        """Remove backup directory after a successful update."""
        if backup_dir and backup_dir.exists():
            shutil.rmtree(backup_dir)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _belongs_to(file_path: Path, library_name: str) -> bool:
        """Return True if *file_path* looks like it belongs to *library_name*."""
        stem = file_path.stem.lower().lstrip("lib")
        clean = library_name.lower().replace("_", "")
        return stem == library_name.lower() or stem == clean
