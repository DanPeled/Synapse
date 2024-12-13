from abc import ABC, abstractmethod
from typing import Optional
import typing
from ntcore import NetworkTable
from ntcore import Event, EventFlags
from typing_extensions import Any, Callable
import cv2

from synapse import log
from synapse.pipeline_settings import PipelineSettings


# Abstract Pipeline class
class Pipeline(ABC):
    __is_enabled__ = True
    VALID_ENTRY_TYPES = float | int | str | typing.Sequence | bytes | bool

    @abstractmethod
    def __init__(self, settings: PipelineSettings | None, camera_index: int):
        self.nt_table: Optional[NetworkTable] = None

    def setup(self):
        pass

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
            self.nt_table.getSubTable("data").putValue(key, value)

    def setDataListener(
        self,
        key: str,
        setter: Callable[[VALID_ENTRY_TYPES], None],
        getter: Callable[[], VALID_ENTRY_TYPES],
    ):
        if self.nt_table is not None:
            self.__setListener(
                key=key,
                setter=setter,
                getter=getter,
                table=self.nt_table.getSubTable("data"),
            )
        else:
            log.log(f"Error: trying to set data listener (key = {key}), for None table")

    def __setListener(
        self,
        key: str,
        setter: Callable[[VALID_ENTRY_TYPES], None],
        getter: Callable[[], VALID_ENTRY_TYPES],
        table: NetworkTable,
    ):
        def listener(_: NetworkTable, key: str, event: Event):
            setter(event.data.value.value())  # pyright: ignore

        table.addListener(eventMask=EventFlags.kValueAll, listener=listener, key=key)
        table.putValue(key, getter())


def disabled(cls):
    cls.__is_enabled__ = False

    return cls
