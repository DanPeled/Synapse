from abc import ABC, abstractmethod
import cv2

from synapse.pipeline_settings import PipelineSettings


# Abstract Pipeline class
class Pipeline(ABC):
    __is_enabled__ = True

    @abstractmethod
    def __init__(self, settings: PipelineSettings | None):
        pass

    @abstractmethod
    def process_frame(self, img, timestamp: float) -> cv2.typing.MatLike | None:
        """
        Abstract method that processes a single frame.

        :param img: The frame image
        :param timestamp: The time the frame was captured
        """
        pass


def disabled(cls):
    cls.__is_enabled__ = False

    return cls
