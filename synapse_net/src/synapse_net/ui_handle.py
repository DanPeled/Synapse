# SPDX-FileCopyrightText: 2025 Dan Peled
# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

import importlib.util
from http.server import SimpleHTTPRequestHandler
from pathlib import Path
from socketserver import TCPServer
from threading import Thread

from synapse.log import log
from synapse.util import getIP


class MultiHTMLHandler(SimpleHTTPRequestHandler):
    """
    Custom HTTP handler that serves:
    1. Requested file if it exists.
    2. Requested file with ".html" extension if it exists.
    3. 404.html if it exists.
    4. Standard 404 otherwise.
    """

    def do_GET(self):
        # Remove query parameters from the path
        requested_path = self.path.split("?")[0].lstrip("/")

        # Redirect root to dashboard.html
        if requested_path == "":
            self.path = "/dashboard.html"
            return super().do_GET()

        # Determine the full paths for requested file, .html, and 404
        file_path = Path(self.directory) / requested_path
        html_path = Path(self.directory) / f"{requested_path}.html"
        error_page = Path(self.directory) / "404.html"

        # Serve existing file
        if file_path.is_file():
            return super().do_GET()

        # Serve requested file with .html extension
        if html_path.is_file():
            self.path = f"/{requested_path}.html"
            return super().do_GET()

        # Serve 404.html if exists
        if error_page.is_file():
            self.path = "/404.html"
            return super().do_GET()

        # Default 404 error
        return super().send_error(404)


class UIHandle:
    """
    Handles launching the Synapse UI (Next.js compatible) HTTP server.
    """

    @staticmethod
    def startUI(port: int = 3000):
        """
        Start the Python HTTP server for the Synapse UI.

        Args:
            port (int): Port number to serve the UI on. Defaults to 3000.
        """

        # Find the synapse_ui module to determine the serve directory
        spec = importlib.util.find_spec("synapse_ui")
        if not spec or not spec.origin:
            log("Error: synapse_ui module not found!")
            return

        serve_dir = Path(spec.origin).parent

        # Custom TCPServer that allows address reuse (helps restart server quickly)
        class ReusableTCPServer(TCPServer):
            allow_reuse_address = True

        def serve():
            try:
                with ReusableTCPServer(
                    ("", port),
                    lambda *args, **kwargs: MultiHTMLHandler(
                        *args, directory=str(serve_dir), **kwargs
                    ),
                ) as httpd:
                    actual_port = httpd.server_address[1]
                    log(f"UI available at: https://{getIP()}:{actual_port}")
                    httpd.serve_forever()
            except OSError as e:
                log(f"Failed to start server on port {port}: {e}")

        # Run server in a daemon thread (will stop automatically when app exits)
        thread = Thread(target=serve, daemon=True)
        thread.start()
