import copy
import logging
import typing
from dataclasses import dataclass
from inspect import iscoroutinefunction

from named_locks import AsyncNamedLock
from RelativeAddonsSystem import Addon
from pyrogram import types

from .api_types import ExtendedClient
from .base import BaseManager, AddonNotSet, SkipMe


@dataclass
class Command:
    body: tuple[str]
    prefixes: tuple[str]

    description: str | None
    arguments: tuple[str]

    callback: typing.Callable
    filters: tuple = ()
    owner_only: bool = True

    iscoro: bool = False
    enabled: bool = True


@dataclass
class MatchedCommand:
    command: Command
    arguments: list[list[str]]


@dataclass
class CommandExecutionProcess:
    chat_id: int
    command: Command


class CommandManager(BaseManager):
    _parent: type["CommandManager"] | None = None

    def __init__(
        self, addon: Addon | None = AddonNotSet, enabled: bool = True, log_level: int = logging.WARNING
    ):
        super().__init__(addon, enabled, log_level)
        self._registered_commands: list[Command] = []

        self._command_executes: list[CommandExecutionProcess] = []

        self.executable = self.feed_message

        self._command_call_statistic = []

        self._lock = AsyncNamedLock()

    def get_registered_commands(self):
        return self._registered_commands.copy()

    def on_command(
        self,
        body: str | tuple[str],
        *filters,
        prefixes: str | tuple = ".",
        description: str = None,
        arguments: tuple = (),
        enabled: bool = True,
        owner_only: bool = True,
    ):
        def decorator(callback):

            self.register_command(
                callback,
                body,
                *filters,
                prefixes=prefixes,
                description=description,
                arguments=arguments,
                enabled=enabled,
                owner_only=owner_only,
            )

            return callback

        return decorator

    def register_command(
        self,
        callback,
        body: str | tuple[str],
        *filters,
        prefixes: str | tuple = ".",
        description: str = None,
        arguments: tuple = (),
        enabled: bool = True,
        owner_only: bool = True,
    ) -> int | None:
        if not isinstance(prefixes, tuple) and not isinstance(prefixes, str):
            raise ValueError(
                "Cannot operate on {type} as prefixes".format(type=str(type(prefixes)))
            )

        if isinstance(body, str):
            body = (body,)

        if not isinstance(body, (str, tuple)):
            raise ValueError(
                "Cannot operate on {type} as command".format(type=str(type(body)))
            )

        if not isinstance(description, str) and description is not None:
            raise ValueError(
                "Cannot operate on {type} as description".format(
                    type=str(type(description))
                )
            )

        if not isinstance(arguments, tuple):
            raise ValueError(
                "Cannot operate on {type} as arguments".format(
                    type=str(type(arguments))
                )
            )

        if not isinstance(enabled, bool):
            raise ValueError(
                "Cannot operate on {type} as enable status of command".format(
                    type=str(type(arguments))
                )
            )

        body = tuple(map(str.lower, body))

        if not isinstance(prefixes, tuple):
            prefixes = tuple(prefixes)

        for registered_command in self._registered_commands:
            if (
                registered_command.body == body
                and registered_command.prefixes == prefixes
            ):

                if (
                    description == registered_command.description or description is None
                ) and (arguments == registered_command.arguments or len(arguments) < 1):
                    return

                if (
                    registered_command.description != description
                    and description is not None
                ):
                    registered_command.description = description

                if registered_command.arguments != arguments and len(arguments) > 0:
                    registered_command.arguments = arguments

                return

        command = Command(
            callback=callback,
            body=body,
            prefixes=prefixes,
            description=description,
            arguments=arguments,
            filters=filters,
            iscoro=iscoroutinefunction(callback),
            enabled=enabled,
            owner_only=owner_only,
        )

        self._registered_commands.append(
            command
        )

        return self._registered_commands.index(command)

    def describe_command(self, command: str, description: str, arguments: tuple):
        if not isinstance(command, str):
            raise ValueError(
                "Cannot operate with {type} as command".format(type=str(type(command)))
            )

        if not isinstance(description, str):
            raise ValueError(
                "Cannot operate with {type} as description".format(
                    type=str(type(description))
                )
            )

        if not isinstance(arguments, tuple):
            raise ValueError(
                "Cannot operate with {type} as arguments".format(
                    type=str(type(arguments))
                )
            )

        command = command.lower()

        for command_object in self._registered_commands:
            if command_object.body == command:
                command_object.description = description
                command_object.arguments = arguments
                break
        else:
            raise ValueError("Command {body} not found".format(body=command))

    def remove_command(self, index: int):
        try:
            del self._registered_commands[index]
            return True
        except KeyError:
            return False

    def match_command(self, text: str) -> Command | None:
        for command in self._registered_commands:
            if not command.enabled:
                continue

            for body in command.body:
                if body not in text:
                    continue
                for prefix in command.prefixes:
                    if not text.startswith(prefix):
                        continue

                    text_without_prefix = text[len(prefix):]

                    if not text_without_prefix.startswith(body):
                        continue

                    text_without_body = text_without_prefix[len(body):]

                    if len(text_without_body) == 0 or text_without_body[0] in ("\n", " "):
                        return command

    def check_execution(self, command: Command, chat_id: int):
        for executes in self._command_executes:
            if chat_id == executes.chat_id and command is executes.command:
                return True

    def add_execution(self, record):
        self._command_executes.append(record)

    def execution_cleanup(self, remove_record):
        for record in self._command_executes.copy():
            if remove_record is record:
                self._command_executes.remove(record)
                break

    def add_call_of_command(self, command: Command):
        if self.parent:
            self.parent.add_call_of_command(command)

        for record in self.get_statistic():
            if record["command"] == command:
                record["call_count"] += 1
                return

        self._command_call_statistic.append({"command": command, "call_count": 1})

    def get_statistic(self):
        return self._command_call_statistic

    def get_total_call_count(self):
        return sum(map(lambda rec: rec["call_count"], self.get_statistic()))

    async def feed_message(self, client: ExtendedClient, message: types.Message):
        command = self.match_command(message.text)

        if not command:
            raise SkipMe

        owner_only_fail = command.owner_only and (
                message.from_user
                and message.from_user.id != client.account.info.id
                or not message.outgoing
        )

        if (
                self.check_execution(command, message.chat.id) and not owner_only_fail
        ) or owner_only_fail:
            raise SkipMe

        key = f"{message.chat.id}:C:{id(command)}"

        async with self._lock.lock(key):

            process = CommandExecutionProcess(chat_id=message.chat.id, command=command)
            self.add_execution(process)

            for filter_ in command.filters:
                if not await filter_(client, message):
                    self.execution_cleanup(process)
                    raise SkipMe

            arguments = []
            if len(message.text.split()) > 1:
                arguments = [
                    line.split()
                    for line in message.text.split(maxsplit=1)[1].splitlines()
                ]

            message.matched_command = MatchedCommand(command, arguments)

            message.command_manager = self

            message.arguments = arguments

            try:
                if command.iscoro:
                    await command.callback(client, message)
                else:
                    command.callback(client, message)
            finally:
                self.execution_cleanup(process)

            self.add_call_of_command(command)

            return command
