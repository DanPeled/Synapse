# Simulator benchmarks

`bench_sim.py` measures the full simulated-camera path: `SimCamera.grabFrame`
publishes a pose, the headless-Chrome renderer draws the field and reads the
pixels back, the frame travels over a WebSocket, and Python decodes it into a
BGR image.

Run it from the repository root with the development paths on `PYTHONPATH`:

```bash
PYTHONPATH=synapse_sim/src:synapse_core/src:synapse_net/src \
    python synapse_sim/tests/benchmarks/bench_sim.py
```

By default it measures 640x480, 1280x720, and 1920x1080 for five seconds each.
Each resolution runs in its own process because `getViewer()` is a
process-wide singleton and a reused viewer can serve frames from the previous
resolution.

Useful options:

```bash
# One resolution, machine-readable
python synapse_sim/tests/benchmarks/bench_sim.py \
    --size 1280x720 --seconds 10 --json

# Fail if the camera drops below 60 FPS
python synapse_sim/tests/benchmarks/bench_sim.py \
    --size 640x480 --min-fps 60

# Skip renderer diagnostics
python synapse_sim/tests/benchmarks/bench_sim.py --no-stats
```

The table reports:

- `fps` / `recv`: frames returned by `grabFrame` and frames received over the
  WebSocket, per second.
- `mean`, `p50`, `p95`: per-frame `grabFrame` latency in milliseconds.
- `render`, `copy`, `send`: renderer-side averages for drawing, GPU readback,
  and handing the frame to the WebSocket.
- `drop`: frames the renderer discarded because the transport was still busy.

## Opt-in test

`synapse_sim/tests/test_sim_perf.py` wraps this benchmark as an opt-in
regression test. It is disabled by default because frame rates depend heavily
on the GPU and CI machine:

```bash
SYNAPSE_TEST_SIM_BENCH=1 \
PYTHONPATH=synapse_sim/src:synapse_core/src:synapse_net/src \
    python -m pytest synapse_sim/tests/test_sim_perf.py

# Choose the floor and resolutions
SYNAPSE_TEST_SIM_BENCH=1 \
SYNAPSE_TEST_SIM_MIN_FPS=30 \
SYNAPSE_TEST_SIM_BENCH_SIZES=640x480,1280x720 \
    python -m pytest synapse_sim/tests/test_sim_perf.py
```

The test asserts a conservative default floor of 15 FPS at 640x480 so it
catches catastrophic regressions without turning GPU variance into failures.
