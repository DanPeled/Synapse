# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import hashlib
import json
import os
import warnings
import zipfile
from importlib.metadata import Distribution, distribution
from pathlib import Path
from typing import Any, Callable, Dict, Final, List, Optional

from tqdm import tqdm

PACKAGE_NAME: Final[str] = "synapsefrc"
OUTPUT_ZIP: Final[str] = "synapse.zip"
LOCK_FILE: Final[str] = ".synapse.lock"


def getFileHash(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def loadExistingHashes(path: Path) -> Dict[str, str]:
    lock_file_path: Path = path / LOCK_FILE
    if lock_file_path.exists():
        with open(lock_file_path, "r") as f:
            data: Any = json.load(f)
            if isinstance(data, dict):
                return {str(k): str(v) for k, v in data.items()}
    return {}


def saveHashes(hashes: Dict[str, str], distPath: Path) -> None:
    with open(distPath / LOCK_FILE, "w") as f:
        json.dump(hashes, f, indent=2)


def calculateFileHashesFromPaths(files: List[Path], root_path: Path) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for file in files:
        if file.is_file():
            rel_path = str(file.relative_to(root_path))
            hashes[rel_path] = getFileHash(str(file))
    return hashes


def zipFiles(
    files: List[Path], root_path: Path, zip_path: Path, desc: str = "Zipping files"
) -> List[str]:
    caught_warnings: List[str] = []

    def custom_warn_handler(message, category, filename, lineno, file=None, line=None):
        caught_warnings.append(f"{category.__name__}: {message} ({filename}:{lineno})")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        warnings.showwarning = custom_warn_handler  # type: ignore

        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for file in tqdm(files, desc=desc, unit="file"):
                arcname = file.relative_to(root_path)
                zf.write(str(file), str(arcname))

    return caught_warnings


def createPackageZIP(baseDestPath: Path) -> None:
    if not baseDestPath.exists():
        os.makedirs(baseDestPath)

    dist: Distribution = distribution(PACKAGE_NAME)
    files: List[Path] = [
        Path(str(dist.locate_file(f)))
        for f in dist.files or []
        if Path(str(dist.locate_file(f))).is_file() and "__pycache__" not in str(f)
    ]

    root_path = Path(str(dist.locate_file("")))
    new_hashes = calculateFileHashesFromPaths(files, root_path)
    old_hashes = loadExistingHashes(baseDestPath)

    if new_hashes == old_hashes:
        return

    caught_warnings = zipFiles(
        files, root_path, baseDestPath / OUTPUT_ZIP, f"Packaging {PACKAGE_NAME}"
    )
    saveHashes(new_hashes, baseDestPath)

    if caught_warnings:
        print("\nWarnings encountered during zip creation:")
        for w in caught_warnings:
            print(w)


def createDirectoryZIP(
    directory: Path,
    output_path: Optional[Path] = None,
    filterFunc: Optional[Callable[[Path], bool]] = None,
) -> None:
    directory = Path(directory)
    output_path = output_path or (directory / OUTPUT_ZIP)
    if not directory.exists():
        raise FileNotFoundError(f"Directory {directory} does not exist")

    all_files = [f for f in directory.rglob("*") if f.is_file()]

    if filter:
        all_files = list(filter(filterFunc, all_files))

    new_hashes = calculateFileHashesFromPaths(all_files, directory)
    old_hashes = loadExistingHashes(directory)

    if new_hashes == old_hashes:
        print("No changes detected. Skipping zip creation.")
        return

    caught_warnings = zipFiles(all_files, directory, output_path, "Packaging directory")
    if caught_warnings:
        print("\nWarnings encountered during zip creation:")
        for w in caught_warnings:
            print(w)
