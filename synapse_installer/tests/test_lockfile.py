import hashlib
import json
from pathlib import Path

import pytest
from synapse_installer.lockfile import (LOCK_FILE, OUTPUT_ZIP,
                                        calculateFileHashesFromPaths,
                                        createDirectoryZIP, getFileHash,
                                        loadExistingHashes, saveHashes,
                                        zipFiles)


def create_temp_file_with_content(tmp_path, name: str, content: bytes):
    file = tmp_path / name
    file.write_bytes(content)
    return file


def test_get_file_hash(tmp_path):
    file = create_temp_file_with_content(tmp_path, "file.txt", b"hello")
    expected = hashlib.sha256(b"hello").hexdigest()
    assert getFileHash(str(file)) == expected


def test_load_existing_hashes_when_file_exists(tmp_path):
    data = {"file.txt": "123abc"}
    lock_file = tmp_path / LOCK_FILE
    lock_file.write_text(json.dumps(data))
    assert loadExistingHashes(tmp_path) == data


def test_load_existing_hashes_when_file_missing(tmp_path):
    assert loadExistingHashes(tmp_path) == {}


def test_save_hashes_and_reload(tmp_path):
    data = {"a.txt": "deadbeef"}
    saveHashes(data, tmp_path)
    loaded = loadExistingHashes(tmp_path)
    assert loaded == data


def test_calculate_file_hashes_from_paths(tmp_path):
    file1 = create_temp_file_with_content(tmp_path, "f1.txt", b"abc")
    file2 = create_temp_file_with_content(tmp_path, "f2.txt", b"xyz")
    result = calculateFileHashesFromPaths([file1, file2], tmp_path)
    assert result == {
        "f1.txt": hashlib.sha256(b"abc").hexdigest(),
        "f2.txt": hashlib.sha256(b"xyz").hexdigest(),
    }


def test_zip_files_creates_zip_and_warns(tmp_path):
    file1 = create_temp_file_with_content(tmp_path, "f1.txt", b"test")
    file2 = create_temp_file_with_content(tmp_path, "f2.txt", b"test2")
    zip_path = tmp_path / "out.zip"
    warnings = zipFiles([file1, file2], tmp_path, zip_path)
    assert zip_path.exists()
    assert warnings == []


def test_create_directory_zip_creates_zip(tmp_path):
    (tmp_path / "subdir").mkdir()
    _ = create_temp_file_with_content(tmp_path / "subdir", "f.txt", b"data")

    createDirectoryZIP(tmp_path)

    assert (tmp_path / OUTPUT_ZIP).exists()


def test_create_directory_zip_skips_if_no_change(tmp_path, capsys):
    file = create_temp_file_with_content(tmp_path, "a.txt", b"123")
    hashes = calculateFileHashesFromPaths([file], tmp_path)
    saveHashes(hashes, tmp_path)

    createDirectoryZIP(tmp_path)

    captured = capsys.readouterr()
    assert len(captured.out) == 0


def test_create_directory_zip_raises_if_not_exist(tmp_path):
    non_existent = tmp_path / "nope"
    with pytest.raises(FileNotFoundError):
        createDirectoryZIP(non_existent)


def test_create_directory_zip_with_filter(tmp_path):
    create_temp_file_with_content(tmp_path, "keep.txt", b"yes")
    create_temp_file_with_content(tmp_path, "skip.log", b"no")

    def filter_func(p: Path):
        return p.suffix != ".log"

    createDirectoryZIP(tmp_path, filterFunc=filter_func)
    assert (tmp_path / OUTPUT_ZIP).exists()
