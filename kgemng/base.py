import inspect
import logging
import timeit
from types import FunctionType
from typing import Callable, Union

from RelativeAddonsSystem import Addon


class BaseManager:
    NO_ADDON = None

    def __init__(self, addon: Addon | NO_ADDON = NO_ADDON, enabled: bool = False):
        self._logger = logging.getLogger(f"{addon.meta.name} | {type(self).__name__}")

        self._enabled = enabled

        self._executable: Union[FunctionType, None] = None

        self._parent = None

        self._included_managers: set[BaseManager] = set()

        self._addon = addon

    def include_manager(self, value):
        if not isinstance(value, type(self)):
            raise ValueError(
                "Cannot operate with {type} as manager".format(type=type(value))
            )

        self._included_managers.add(value)
        value.parent = self

        self._logger.debug(f"Included child manager {value}")

    def exclude_manager(self, value):
        if not isinstance(value, type(self)):
            raise ValueError(
                "Cannot operate with {type} as manager".format(type=type(value))
            )

        self._included_managers.remove(value)
        value.parent = None

        self._logger.debug(f"Excluded child manager {value}")

    def get_included_managers(self):
        return self._included_managers.copy()

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, value):
        if not isinstance(value, type(self)) and value is not None:
            raise ValueError(
                "Cannot operate with {type} as manager".format(type=type(value))
            )
        former_parent = self._parent
        self._parent = value
        self._logger.debug(f"Changed parent for manager. {former_parent} => {value}")

    def executable(self, value: Callable):
        if (
            not (inspect.isfunction(value) or inspect.iscoroutinefunction(value))
            and value is not None
        ):
            raise ValueError("executable must be a function")
        former_executable = self._executable
        self._executable = value
        self._logger.debug(
            f"Changed executable in manager. {former_executable} => {value}"
        )

    executable = property(fset=executable)

    @property
    def addon(self):
        return self._addon

    def disable(self):
        self._enabled = False
        self._logger.debug("Manager is disabled")

    def enable(self):
        self._enabled = True
        self._logger.debug("Manager is enabled")

    def toggle(self):
        self._enabled = not self._enabled
        self._logger.debug("Manager is toggled")

    def is_enabled(self):
        return self._enabled

    async def execute(self, *args, **kwargs):
        self._logger.debug(
            f"Executing manager with arguments > positional: {args} | keyword: {kwargs}"
        )
        if not self._enabled:
            self._logger.debug("Manager is disabled > exit")
            return

        if not self._executable:
            self._logger.warning(
                "Manager doesn't have executable, but tried to be executed".format(
                    mng=self
                )
            )
            return

        start = timeit.default_timer()

        result = self._executable(*args, **kwargs)

        if inspect.iscoroutine(result):
            self._logger.debug(f"Executable returned the coroutine. Waiting it...")
            await result

        self._logger.debug(
            f"Manager executed. Took {(timeit.default_timer() - start) * 1000:2f}ms"
        )

        return result
