__author__ = "Christopher Toth"
__version__ = "0.8.6"


def find_datafiles():
    """Return a list of (dest_dir, [source_files]) tuples for the current platform.

    Used by cx_Freeze / similar tools that need explicit data-file lists.
    The find_library machinery handles staging automatically at runtime, so
    this helper is only needed for legacy freeze workflows.
    """
    from glob import glob
    import os
    import sound_lib
    from sound_lib.external.find_library import _detect_platform_subdir

    lib_root = os.path.join(sound_lib.__path__[0], "lib")
    subdir = _detect_platform_subdir() or "linux_x64"
    src_dir = os.path.join(lib_root, subdir)
    dest_dir = os.path.join("sound_lib", "lib", subdir)
    sources = glob(os.path.join(src_dir, "*"))
    return [(dest_dir, sources)]
