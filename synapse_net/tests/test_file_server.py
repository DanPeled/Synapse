# SPDX-FileCopyrightText: 2025 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import http.client
import shutil
import tempfile
import unittest
from pathlib import Path

from synapse_net.file_server import FileServer


class TestFileServer(unittest.TestCase):
    def setUp(self) -> None:
        # Create a temporary directory for uploads
        self.temp_dir = Path(tempfile.mkdtemp())
        self.port = 9090
        self.server = FileServer(files_dir=self.temp_dir, port=self.port)
        self.server.start()

    def tearDown(self) -> None:
        # Stop the server and remove temp directory
        self.server.stop()
        shutil.rmtree(self.temp_dir)

    def test_file_upload(self) -> None:
        """Test that a file can be uploaded successfully."""
        conn = http.client.HTTPConnection("localhost", self.port)
        boundary = "testboundary"
        file_content = b"Hello, world!"
        filename = "test.txt"

        body = (
            (
                f"--{boundary}\r\n"
                f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n\r\n'
            ).encode()
            + file_content
            + f"\r\n--{boundary}--\r\n".encode()
        )

        headers = {
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Content-Length": str(len(body)),
        }

        conn.request("POST", "/", body=body, headers=headers)
        response = conn.getresponse()
        resp_body = response.read()
        conn.close()

        self.assertEqual(response.status, 200)
        self.assertIn(b"Upload successful", resp_body)
        # Check that file exists
        uploaded_file = self.temp_dir / filename
        self.assertTrue(uploaded_file.exists())
        self.assertEqual(uploaded_file.read_bytes(), file_content)

    def test_file_download(self) -> None:
        """Test that a file can be downloaded successfully."""
        # First, create a file in the directory
        filename = "download.txt"
        content = b"Download me!"
        file_path = self.temp_dir / filename
        file_path.write_bytes(content)

        conn = http.client.HTTPConnection("localhost", self.port)
        conn.request("GET", f"/{filename}")
        response = conn.getresponse()
        resp_body = response.read()
        conn.close()

        self.assertEqual(response.status, 200)
        self.assertEqual(resp_body, content)


if __name__ == "__main__":
    unittest.main()
