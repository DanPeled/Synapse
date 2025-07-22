from pathlib import Path
import zipfile
import warnings
from tqdm import tqdm
import os
import hashlib
import json
from importlib.metadata import distribution, Distribution, PackagePath
from typing import Dict, Final, List, Any


PACKAGE_NAME: Final[str] = "Synapse"
OUTPUT_ZIP: Final[str] = "synapse.zip"
LOCK_FILE: Final[str] = ".synapse.lock"


def getFileHash(path: str) -> str:
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def calculateFilesHashes(
    files: List[PackagePath], dist: Distribution
) -> Dict[str, str]:
    hashes: Dict[str, str] = {}
    for file in files:
        full_path: Path = Path(str(dist.locate_file(file)))
        if full_path.is_file():
            rel_path: str = str(file)
            hashes[rel_path] = getFileHash(str(full_path))
    return hashes


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


def createSynapseZIP(baseDistPath: Path) -> None:
    if not baseDistPath.exists():
        os.makedirs(baseDistPath)
    dist: Distribution = distribution(PACKAGE_NAME)
    files: List[PackagePath] = [
        f
        for f in dist.files or []
        if Path(str(dist.locate_file(f))).is_file()
        if "__pycache__" not in str(f)
    ]

    new_hashes: Dict[str, str] = calculateFilesHashes(files, dist)
    old_hashes: Dict[str, str] = loadExistingHashes(baseDistPath)

    if new_hashes == old_hashes:
        print("No changes detected. Skipping zip creation.")
        return

    root_path: Path = Path(str(dist.locate_file("")))

    caught_warnings: List[str] = []

    def custom_warn_handler(
        message: Warning,
        category: type[Warning],
        filename: str,
        lineno: int,
        file: Any = None,
        line: Any = None,
    ) -> None:
        caught_warnings.append(f"{category.__name__}: {message} ({filename}:{lineno})")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # suppress warnings
        warnings.showwarning = custom_warn_handler  # type: ignore

        with zipfile.ZipFile(
            baseDistPath / OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED
        ) as zf:
            for file in tqdm(files, desc="Packaging project", unit="file"):
                full_path: Path = Path(str(dist.locate_file(file)))
                arcname: str = os.path.relpath(str(full_path), str(root_path))
                zf.write(str(full_path), arcname)

    saveHashes(new_hashes, baseDistPath)

    if caught_warnings:
        print("\nWarnings encountered during zip creation:")
        for w in caught_warnings:
            print(w)
