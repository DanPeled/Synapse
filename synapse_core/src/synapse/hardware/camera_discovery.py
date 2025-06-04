from dataclasses import dataclass
from typing import List, Tuple, Union
from synapse.hardware.metrics import Platform
import synapse.log as log
import cv2


@dataclass
class CameraDetectionData:
    bind: Union[str, int]
    name: str


def listCameras(system: Platform):
    if system.isWindows():
        return listWindowsCameras()
    elif system.isLinux():
        return listLinuxCameras()
    elif system.isMac():
        return listMacOSCameras()
    else:
        return []


# ---- Windows: list camera names ----
def listWindowsCameras():
    import pythoncom
    import win32com.client

    cameras = []
    dshow = win32com.client.Dispatch("SystemDeviceEnum")
    category = "{860BB310-5D01-11D0-BD3B-00A0C911CE86}"  # VideoInputDevice category
    enum = dshow.CreateClassEnumerator(category, 0)
    if enum is None:
        return []

    while True:
        moniker = enum.Next()
        if not moniker:
            break
        prop_bag = moniker.BindToStorage(None, None, pythoncom.IID_IPropertyBag)
        name = prop_bag.Read("FriendlyName")
        cameras.append(name)
    return cameras


# ---- Linux: list /dev/video* devices with names ----
def listLinuxCameras():
    import pyudev

    context = pyudev.Context()
    cameras = []
    for device in context.list_devices(subsystem="video4linux"):
        node = device.device_node  # e.g., /dev/video0
        name = device.get("ID_V4L_PRODUCT") or node
        if node:
            cameras.append((node, name))
    return cameras


# ---- macOS: list cameras via AVFoundation ----
def listMacOSCameras():
    import AVFoundation  # pyright: ignore

    devices = AVFoundation.AVCaptureDevice.devicesWithMediaType_("vide")
    if not devices:
        return []

    return [str(dev.localizedName()) for dev in devices]


# ---- OpenCV test ----
def testCameraOpen(device):
    """Test camera with OpenCV.
    device: int index (Windows/macOS) or string path (Linux)"""
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        return False
    ret, _ = cap.read()
    cap.release()
    return ret


def detect() -> List[CameraDetectionData]:
    system = Platform.getCurrentPlatform()
    cameras = listCameras(system)
    if not cameras:
        log.log("No cameras found.")
        return []

    working_cameras: List[CameraDetectionData] = []

    if system.isLinux():
        for device_path, name in cameras:
            result = testCameraOpen(device_path)
            if result:
                working_cameras.append(CameraDetectionData(device_path, name))

    elif system.isMac() or system.isWindows():
        for i in range(min(10, len(cameras))):
            result = testCameraOpen(i)
            if result:
                working_cameras.append(CameraDetectionData(i, cameras[i]))

    return working_cameras
