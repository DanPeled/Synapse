import cv2
import numpy as np
from cv2.typing import MatLike
from synapse.pipeline import Pipeline, PipelineSettings

class ColorPipeline(Pipeline):
    def __init__(self, settings: PipelineSettings, camera_index: int):
        self.camera_index = camera_index
        self.settings = settings
        print(self.settings.getMap())

    def process_frame(self, img: MatLike, timestamp: float) -> MatLike:
        # Convert the image to the HSV color space
        hsv = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)

        # Define the range for the color red in HSV
        # lower_red = np.array([int(self.settings["LR"]), int(self.settings["LG"]), int(self.settings["LB"])], np.uint8)
        # upper_red = np.array([int(self.settings["UR"]), int(self.settings["UG"]), int(self.settings["UB"])], np.uint8)
        lower_red = np.array([100, 0, 0], np.uint8)
        upper_red = np.array([255, 100, 100], np.uint8)
        mask = cv2.inRange(hsv, lower_red, upper_red)

        # Find contours in the mask
        contours, _ = cv2.findContours(mask, cv2.RETR_TREE, cv2.CHAIN_APPROX_SIMPLE)

        # If contours are found, find the largest contour
        if contours:
            largest_contour = max(contours, key=cv2.contourArea)
            # Get the bounding box coordinates of the largest contour
            x, y, w, h = cv2.boundingRect(largest_contour)

            # Set the x and y coordinates with setValue
            self.setValue("x", x)
            self.setValue("y", y)
            self.setValue("width", w)
            self.setValue("height", h)

            # Optional: Draw the bounding box on the image for visualization
            cv2.rectangle(img, (x, y), (x + w, y + h), (0, 255, 0), 2)

        return img

# Example usage:
# settings = PipelineSettings(...)
# pipeline = ColorPipeline(settings, camera_index=0)
# frame = ... # Get the frame from the camera
# timestamp = ... # Get the current timestamp
# processed_frame = pipeline.process_frame(frame, timestamp)