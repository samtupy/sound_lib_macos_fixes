"""Main Bass library updater orchestration."""
from pathlib import Path
from typing import Dict, List, Optional

from .config import ARCHIVE_PLATFORMS, BASS_LIBRARIES, FILES_BASE_URL
from .downloader import Downloader
from .extractor import ArchiveExtractor
from .file_manager import FileManager
from .version_parser import VersionParser
from .version_tracker import VersionTracker


class BassUpdater:
    """Main orchestrator for Bass library updates."""

    def __init__(self):
        self.version_parser = VersionParser()
        self.version_tracker = VersionTracker()
        self.downloader = Downloader()
        self.extractor = ArchiveExtractor()
        self.file_manager = FileManager()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check_for_updates(self) -> Dict[str, tuple]:
        """Check which libraries have updates available.

        Returns:
            Dict mapping library name to (old_version, new_version) tuples.
        """
        print("Checking for Bass library updates...")
        try:
            current_versions = self.version_parser.get_current_versions()
            updates_needed = self.version_tracker.get_updates_needed(current_versions)

            if updates_needed:
                print(f"Found {len(updates_needed)} libraries with updates:")
                for lib, (old, new) in updates_needed.items():
                    print(f"  {lib}: {old or 'not installed'} -> {new}")
            else:
                print("All libraries are up to date.")

            return updates_needed
        except Exception as exc:
            raise RuntimeError(f"Failed to check for updates: {exc}") from exc

    def update_library(
        self,
        library_name: str,
        new_version: str,
        archive_types: Optional[List[str]] = None,
    ) -> bool:
        """Download, extract, and install a single library.

        Args:
            library_name:  Internal library key (e.g. "bass", "bassmix").
            new_version:   Version string being installed.
            archive_types: Which archive types to process.  Defaults to all
                           platforms listed in the library's definition.

        Returns:
            True on success, False if any error occurred.
        """
        if library_name not in BASS_LIBRARIES:
            raise ValueError(f"Unknown library: {library_name}")

        lib_def = BASS_LIBRARIES[library_name]
        if archive_types is None:
            archive_types = list(lib_def.archive_platforms)

        print(f"Updating {lib_def.display_name} to {new_version}...")
        backup_dir = self.file_manager.create_backup(library_name)

        try:
            all_platform_files: Dict[str, Path] = {}
            extracted_types: list = []

            for archive_type in archive_types:
                archive_path = self._download_archive(library_name, lib_def, archive_type)
                if archive_path is None:
                    continue

                platform_files = self.extractor.extract_archive(
                    archive_path, library_name, archive_type
                )
                all_platform_files.update(platform_files)
                extracted_types.append(archive_type)

            if not all_platform_files:
                raise RuntimeError(f"No files extracted for {library_name}")

            # Install first, then clean up extraction dirs
            self.file_manager.install_files(all_platform_files, library_name)

            for archive_type in extracted_types:
                self.extractor.cleanup_extraction(library_name, archive_type)

            self.version_tracker.mark_updated(library_name, new_version)
            self.file_manager.cleanup_backup(backup_dir)

            print(f"Successfully updated {lib_def.display_name} to {new_version}")
            return True

        except Exception as exc:
            print(f"Update failed for {lib_def.display_name}: {exc}")
            print("Restoring from backup...")
            try:
                self.file_manager.restore_from_backup(backup_dir)
                print("Restored from backup.")
            except Exception as restore_exc:
                print(f"Backup restore also failed: {restore_exc}")
            return False

    def update_all(self, dry_run: bool = False) -> Dict[str, bool]:
        """Update all libraries that have updates available.

        Args:
            dry_run: If True, only show what would be updated without making changes.

        Returns:
            Dict mapping library name to update success status.
        """
        updates_needed = self.check_for_updates()
        if not updates_needed:
            return {}

        if dry_run:
            print("DRY RUN - Would update:")
            for lib, (old, new) in updates_needed.items():
                print(f"  {lib}: {old or 'not installed'} -> {new}")
            return {lib: True for lib in updates_needed}

        results: Dict[str, bool] = {}
        for library_name, (_, new_version) in updates_needed.items():
            results[library_name] = self.update_library(library_name, new_version)
        return results

    def cleanup(self) -> None:
        """Clean up temporary download files."""
        self.downloader.cleanup_downloads()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _download_archive(self, library_name: str, lib_def, archive_type: str) -> Optional[Path]:
        """Build the download URL and fetch one archive zip.

        For ios/android archives the zip may use a different filename prefix
        (e.g. tags uses "basstags" instead of "tags19").
        """
        url_suffix, _ = ARCHIVE_PLATFORMS[archive_type]

        # Use mobile_prefix override for ios/android when defined
        if archive_type in ("ios", "android") and lib_def.mobile_prefix:
            prefix = lib_def.mobile_prefix
        else:
            prefix = lib_def.file_prefix

        filename = f"{prefix}{url_suffix}.zip"

        if lib_def.url_subpath:
            url = f"{FILES_BASE_URL}/{lib_def.url_subpath}/{filename}"
        else:
            url = f"{FILES_BASE_URL}/{filename}"

        try:
            return self.downloader.download_file(url, filename)
        except Exception as exc:
            print(f"  Failed to download {filename}: {exc}")
            return None
