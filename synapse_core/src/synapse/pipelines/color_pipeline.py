import cv2
import numpy as np
from cv2.typing import MatLike
from synapse.core.pipeline import Pipeline, PipelineSettings
from synapse.stypes import Frame


class ColorPipeline(Pipeline):
    def __init__(self, settings: PipelineSettings, cameraIndex: int):
        self.cameraIndex = cameraIndex
        self.settings = settings
        settings["minSize"] = 0.001

    def processFrame(self, img: MatLike, timestamp: float) -> Frame:
        hsv = None
        # Convert the image to the HSV color space
        if self.getSetting("color_space") == "RGB":
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        if self.getSetting("color_space") == "HSV":
            hsv = cv2.cvtColor(img, cv2.COLOR_BGR2HSV)

        # Define the range for the color red in HSV
        lower = self.getSetting("lower")
        upper = self.getSetting("upper")
        lower_red = np.array(lower, np.uint8)
        upper_red = np.array(upper, np.uint8)

        if hsv is not None:
            mask = cv2.inRange(hsv, lower_red, upper_red)

            # Find contours in the mask
            contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

            minSize = self.getSetting("minSize")

            if minSize is not None:
                # Get the dimensions of the image
                height, width = img.shape[:2]
                min_contour_area = minSize * height * width  # 0.1% of the screen size

                # Filter contours by area and draw them on the image
                for contour in contours:
                    area = cv2.contourArea(contour)
                    if area >= min_contour_area:
                        cv2.drawContours(img, [contour], -1, (0, 255, 0), 2)

        return img
