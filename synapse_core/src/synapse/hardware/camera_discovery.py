import platform
import synapse.log as log
import cv2


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
    import AVFoundation  # pyright: ignore

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


def detect():
    system = platform.system()
    log.log(f"Platform: {system}\n")

    cameras = list_cameras()
    if not cameras:
        log.log("No cameras found.")
        return []

    log.log("Detected cameras:")
    working_cameras = []

    if system == "Linux":
        for device_path, name in cameras:
            log.log(f" - {device_path}: {name}")
        log.log("\nTesting cameras with OpenCV:")
        for device_path, name in cameras:
            result = test_camera_open(device_path)
            log.log(f" {device_path}: {'✅ works' if result else '❌ failed'}")
            if result:
                working_cameras.append((device_path, name))

    elif system == "Windows":
        for i, name in enumerate(cameras):
            log.log(f" - Index {i}: {name}")
        log.log("\nTesting cameras with OpenCV by index:")
        for i in range(min(10, len(cameras))):
            result = test_camera_open(i)
            log.log(f" Index {i}: {'✅ works' if result else '❌ failed'}")
            if result:
                working_cameras.append((i, cameras[i]))

    elif system == "Darwin":
        for i, name in enumerate(cameras):
            log.log(f" - Index {i}: {name}")
        log.log("\nTesting cameras with OpenCV by index:")
        for i in range(min(10, len(cameras))):
            result = test_camera_open(i)
            log.log(f" Index {i}: {'✅ works' if result else '❌ failed'}")
            if result:
                working_cameras.append((i, cameras[i]))

    return working_cameras
