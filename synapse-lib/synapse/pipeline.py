from abc import ABC, abstractmethod
from typing import Optional, Callable, Any
from ntcore import NetworkTable, Event, EventFlags
from wpilib import SendableBuilderImpl
from wpiutil import Sendable, SendableBuilder
import cv2
from synapse import log
from synapse.pipeline_settings import PipelineSettings


class Pipeline(ABC):
    __is_enabled__ = True
    VALID_ENTRY_TYPES = Any

    @abstractmethod
    def __init__(self, settings: PipelineSettings, camera_index: int):
        self.nt_table: Optional[NetworkTable] = None
        self.builder_cache: dict[str, SendableBuilder] = {}

    def setup(self):
        pass

    @abstractmethod
    def process_frame(self, img, timestamp: float) -> cv2.typing.MatLike:
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
            if isinstance(value, Sendable):
                builder = self.__getOrCreateBuilder(key)
                value.initSendable(builder)
                builder.update()
            else:
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
            log.err(f"trying to set data listener (key = {key}), for None table")

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

    def __getOrCreateBuilder(self, key: str) -> SendableBuilder:
        """
        Retrieves a cached builder for the given key, or creates and caches a new one.

        :param key: The key associated with the builder.
        :return: A SendableBuilder instance.
        """
        if key not in self.builder_cache and self.nt_table is not None:
            sub_table = self.nt_table.getSubTable(f"data/{key}")
            builder = SendableBuilderImpl()
            builder.setTable(sub_table)
            builder.startListeners()
            self.builder_cache[key] = builder
        return self.builder_cache[key]


def disabled(cls):
    cls.__is_enabled__ = False
    return cls
