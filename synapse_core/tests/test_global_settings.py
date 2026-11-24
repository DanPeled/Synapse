# SPDX-FileCopyrightText: 2026 Dan Peled
#
# SPDX-License-Identifier: GPL-3.0-or-later

from synapse.core.camera_factory import CameraConfig
from synapse.core.global_settings import GlobalSettings

_CONFIG_KEY = "_GlobalSettingsMeta__cameraConfigs"


def test_camera_config_map_updates_publish_a_new_snapshot(monkeypatch) -> None:
    monkeypatch.setattr(GlobalSettings, _CONFIG_KEY, {}, raising=False)
    before = GlobalSettings.getCameraConfigMap()
    config = CameraConfig(
        name="camera",
        id="/dev/video0",
        calibration={},
        defaultPipeline=0,
        streamRes=(640, 480),
    )

    GlobalSettings.setCameraConfig(0, config)

    after = GlobalSettings.getCameraConfigMap()
    assert after is not before
    assert 0 not in before
    assert after[0] is config
    assert GlobalSettings.getCameraConfig(0) is config
