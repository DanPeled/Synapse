# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

"""Opt-in end-to-end throughput test for the simulated camera.

Frame rate depends on the host GPU, browser, and load, so this test is
disabled by default. Enable it explicitly:

    SYNAPSE_TEST_SIM_BENCH=1 \\
    PYTHONPATH=synapse_sim/src:synapse_core/src:synapse_net/src \\
        python -m pytest synapse_sim/tests/test_sim_perf.py

The optional ``SYNAPSE_TEST_SIM_MIN_FPS`` and ``SYNAPSE_TEST_SIM_BENCH_SIZES``
environment variables control the required frame rate and the resolutions
measured. The benchmark itself lives in ``tests/benchmarks/bench_sim.py``.
"""

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from synapse_sim.viewer import findChrome

RUN_BENCHMARKS = os.environ.get("SYNAPSE_TEST_SIM_BENCH") == "1"
MIN_FPS = float(os.environ.get("SYNAPSE_TEST_SIM_MIN_FPS", "15"))
SIZES = [
    size.strip()
    for size in os.environ.get("SYNAPSE_TEST_SIM_BENCH_SIZES", "640x480").split(",")
    if size.strip()
]
BENCHMARK = Path(__file__).parent / "benchmarks" / "bench_sim.py"


@unittest.skipUnless(
    RUN_BENCHMARKS,
    "set SYNAPSE_TEST_SIM_BENCH=1 to run the simulator throughput benchmark",
)
class TestSimCameraThroughput(unittest.TestCase):
    def test_renders_at_a_usable_frame_rate(self):
        if findChrome() is None:
            self.skipTest("Chrome or Chromium is not installed")

        for size in SIZES:
            with self.subTest(size=size):
                result = self._runBenchmark(size)
                self.assertGreaterEqual(
                    result["fps"],
                    MIN_FPS,
                    f"{size} rendered at {result['fps']:.1f} FPS, below the "
                    f"{MIN_FPS:.1f} FPS minimum: {result}",
                )

    def _runBenchmark(self, size: str):
        process = subprocess.run(
            [
                sys.executable,
                str(BENCHMARK),
                "--size",
                size,
                "--seconds",
                "3",
                "--warmup",
                "1",
                "--json",
            ],
            capture_output=True,
            text=True,
            env=os.environ.copy(),
            timeout=240,
        )
        if process.returncode != 0:
            self.fail(
                f"benchmark failed for {size}:\n"
                f"stdout:\n{process.stdout}\n"
                f"stderr:\n{process.stderr}"
            )

        lines = [line for line in process.stdout.splitlines() if line.strip()]
        if not lines:
            self.fail(f"benchmark produced no output for {size}")
        return json.loads(lines[-1])


if __name__ == "__main__":
    unittest.main()
