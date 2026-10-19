"""Bounded, read-only local MetaScalp installation discovery (Windows)."""
from __future__ import annotations

import os
from pathlib import Path


def find_metascalp() -> list[str]:
    """Return existing likely MetaScalp executables; never start a process."""
    if os.name != "nt":
        return []
    roots = [os.environ.get(k, "") for k in ("PROGRAMFILES", "PROGRAMFILES(X86)", "LOCALAPPDATA", "APPDATA")]
    candidates = []
    for root in filter(None, roots):
        base = Path(root)
        for relative in ("MetaScalp/MetaScalp.exe", "MetaScalp/metascalp.exe",
                         "Programs/MetaScalp/MetaScalp.exe", "MetaScalp.exe"):
            path = base / relative
            if path.is_file():
                candidates.append(str(path))
    # Uninstall metadata is queried without recursively scanning the disk.
    try:
        import winreg
        for hive in (winreg.HKEY_CURRENT_USER, winreg.HKEY_LOCAL_MACHINE):
            for key_name in (r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall",
                             r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"):
                try:
                    with winreg.OpenKey(hive, key_name) as parent:
                        count = winreg.QueryInfoKey(parent)[0]
                        for i in range(count):
                            with winreg.OpenKey(parent, winreg.EnumKey(parent, i)) as item:
                                try:
                                    name = winreg.QueryValueEx(item, "DisplayName")[0]
                                except OSError:
                                    continue
                                if "metascalp" not in str(name).lower():
                                    continue
                                for field in ("DisplayIcon", "InstallLocation"):
                                    try:
                                        value = str(winreg.QueryValueEx(item, field)[0]).strip('"')
                                        value = value.split('",')[0]
                                        path = Path(value)
                                        if path.is_file() and path.suffix.lower() == ".exe":
                                            candidates.append(str(path))
                                        elif path.is_dir():
                                            exe = path / "MetaScalp.exe"
                                            if exe.is_file():
                                                candidates.append(str(exe))
                                    except (OSError, ValueError):
                                        continue
                except OSError:
                    continue
    except ImportError:
        pass
    return sorted(set(candidates), key=str.casefold)
