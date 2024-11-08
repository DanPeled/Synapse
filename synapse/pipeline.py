from abc import ABC, abstractmethod
import cv2


# Abstract Pipeline class
class Pipeline(ABC):
    __is_enabled__ = True

    @abstractmethod
    def process_frame(self, img, timestamp) -> cv2.typing.MatLike | None:
        """
        Abstract method that processes a single frame.

        :param img: The frame image
        :param timestamp: The time the frame was captured
        """
        pass


def disabled(cls):
    cls.__is_enabled__ = False

    return cls
