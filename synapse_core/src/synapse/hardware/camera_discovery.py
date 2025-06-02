import platform

import cv2
from synapse.core.camera_factory import time


def list_cameras():
    system = platform.system()

    if system == "Windows":
        return list_windows_cameras()
    elif system == "Linux":
        return list_linux_cameras()
    elif system == "Darwin":
        return list_macos_cameras()
    else:
        return []


# ---- Windows: list camera names ----
def list_windows_cameras():
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
def list_linux_cameras():
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
def list_macos_cameras():
    import AVFoundation

    devices = AVFoundation.AVCaptureDevice.devicesWithMediaType_("vide")
    if not devices:
        return []

    return [str(dev.localizedName()) for dev in devices]


# ---- OpenCV test ----
def test_camera_open(device):
    """Test camera with OpenCV.
    device: int index (Windows/macOS) or string path (Linux)"""
    cap = cv2.VideoCapture(device)
    if not cap.isOpened():
        return False
    ret, _ = cap.read()
    cap.release()
    return ret


# ---- Main: detect + test ----
def main():
    start = time.time()
    system = platform.system()
    print(f"Platform: {system}\n")

    cameras = list_cameras()
    if not cameras:
        print("No cameras found.")
        return

    print("Detected cameras:")

    if system == "Linux":
        # cameras are (device_path, name)
        for device_path, name in cameras:
            print(f" - {device_path}: {name}")
        print("\nTesting cameras with OpenCV:")
        for device_path, name in cameras:
            result = test_camera_open(device_path)
            print(f" {device_path}: {'✅ works' if result else '❌ failed'}")

    elif system == "Windows":
        # cameras are names only, OpenCV needs indices - try indices 0..9
        for i, name in enumerate(cameras):
            print(f" - Index {i}: {name}")
        print("\nTesting cameras with OpenCV by index:")
        for i in range(min(10, len(cameras))):
            result = test_camera_open(i)
            print(f" Index {i}: {'✅ works' if result else '❌ failed'}")

    elif system == "Darwin":
        # cameras are names only, OpenCV needs indices - try indices 0..9
        for i, name in enumerate(cameras):
            print(f" - Index {i}: {name}")
        print("\nTesting cameras with OpenCV by index:")
        for i in range(min(10, len(cameras))):
            result = test_camera_open(i)
            print(f" Index {i}: {'✅ works' if result else '❌ failed'}")

    end_time = time.time()
    print(end_time - start)


if __name__ == "__main__":
    main()
