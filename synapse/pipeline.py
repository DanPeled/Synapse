from abc import ABC, abstractmethod
from typing import Optional
from typing_extensions import Any
import cv2

from synapse.pipeline_settings import PipelineSettings


# Abstract Pipeline class
class Pipeline(ABC):
    __is_enabled__ = True

    @abstractmethod
    def __init__(self, settings: PipelineSettings | None):
        self.nt_table = None

    @abstractmethod
    def process_frame(self, img, timestamp: float) -> cv2.typing.MatLike | None:
        """
        Abstract method that processes a single frame.

        :param img: The frame image
        :param timestamp: The time the frame was captured
        """
        pass

    def setValue(self, key: str, value: Any) -> None:
        """
        Sets a value in the network table.

        :param key: The key for the value.
        :param value: The value to store.
        """
        if self.nt_table is not None:
            self.nt_table.putValue(key, value)

    def getValue(self, key: str, default: Optional[Any] = None) -> Any:
        """
        Gets a value from the network table.

        :param key: The key for the value.
        :param default: The default value to return if the key does not exist.
        :return: The value associated with the key, or the default if the key doesn't exist.
        """
        if self.nt_table is not None:
            if self.nt_table.containsKey(key):
                return self.nt_table.getValue(key, default)
        return default


def disabled(cls):
    cls.__is_enabled__ = False

    return cls
