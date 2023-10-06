import inspect
import logging
import timeit
from pathlib import Path
from types import FunctionType
from typing import Callable, Union, Any

from RelativeAddonsSystem import Addon
from pyrogram import ContinuePropagation, StopPropagation


class SkipMe(Exception):
    """Exception used to skip current event manager execution and start executing the included managers"""


class AddonNotSet:
    pass


def try_to_get_addon(back_for: int = 3):
    try:
        frame_info = inspect.stack()[back_for]

        return Addon(Path(frame_info.filename).parent)

    except FileNotFoundError:
        return None


class BaseManager:
    NO_ADDON = None

    _parent: type["BaseManager"] | None = None

    def __init__(
        self,
        addon: Addon | NO_ADDON = AddonNotSet,
        enabled: bool = False,
        log_level: int = logging.WARNING,
    ):
        if addon is AddonNotSet:
            addon = try_to_get_addon()

        if isinstance(addon, Addon):
            addon_name = addon.meta.name
        else:
            addon_name = "NO ADDON"

        self._logger = logging.getLogger(f"{addon_name} | {type(self).__name__}")

        self._logger.setLevel(log_level)

        self._error_handler: Callable[
                                 [BaseException, dict[str, Any]], None
                             ] | None = None

        self._enabled = enabled

        self._executable: Union[FunctionType, None] = None

        self._included_managers: set[BaseManager] = set()

        self._addon = addon

    def __repr__(self):
        addon_name = self._addon.meta.name if self._addon else "NO ADDON"

        return f"{type(self).__name__}(addon={addon_name}, enabled={self._enabled})"

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

    def error_handler(self):
        def decorator(handler: Callable[[BaseException, dict[str, Any]], None]):
            self._error_handler = handler
            return handler

        return decorator

    def set_error_handler(
        self, handler: Callable[[BaseException, dict[str, Any]], None]
    ):
        self._error_handler = handler

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

        try:
            result = self._executable(*args, **kwargs)

            if inspect.iscoroutine(result):
                self._logger.debug(f"Executable returned the coroutine. Waiting it...")
                await result
        except SkipMe:
            for manager in self.get_included_managers():
                try:
                    result = await manager.execute(*args, **kwargs)
                    break
                except SkipMe:
                    pass
            else:
                raise SkipMe
        except (ContinuePropagation, StopPropagation):
            raise
        except BaseException as exc:
            if self._error_handler:
                self._error_handler(exc, dict(args=args, kwargs=kwargs, manager=self))
            else:
                if self.parent is not None:
                    raise

                self._logger.warning(
                    "Error occurred while executing manager."
                    "Set the error handler to see more details"
                )
            result = None
        finally:
            self._logger.debug(
                f"Manager executed. Took {(timeit.default_timer() - start) * 1000:2f}ms"
            )

        return result
