import json
import typing
from dataclasses import dataclass, fields
from inspect import iscoroutinefunction

from RelativeAddonsSystem import Addon
from pyrogram import types, errors
from pyrogram.raw.base import Update
from pyrogram.raw.types import (
    UpdateReadChannelOutbox,
    UpdateReadHistoryOutbox,
    UpdateReadChannelDiscussionOutbox,
    PeerUser,
    PeerChat,
    UpdateReadChannelInbox,
    UpdateReadChannelDiscussionInbox,
    UpdateReadHistoryInbox,
)
from pyrogram.raw import types as raw_types
from magic_filter import F, MagicFilter

from .api_types import ExtendedClient, Account
from .base import BaseManager


class BeautyModel:
    def __str__(self):
        elements = {"_": self.__class__.__name__}
        # noinspection PyDataclass
        for field in fields(self):
            value = getattr(self, field.name)

            if isinstance(value, types.Object):
                value = json.loads(str(value))

            elif isinstance(value, Account):
                value = str(value)

            else:
                value = repr(value)

            elements[field.name] = value

        return json.dumps(elements, indent=4, ensure_ascii=False)


@dataclass()
class Event(BeautyModel):
    account: Account


@dataclass()
class MessageReadEvent(Event):
    chat: types.Chat
    max_id: int
    by_me: bool = False


@dataclass()
class NewMessageEvent(Event):
    message: types.Message


@dataclass()
class DeletedMessagesEvent(Event):
    messages: typing.List[int]
    chat: types.Chat


@dataclass()
class EditedMessageEvent(Event):
    message: types.Message


class EventManager(BaseManager):
    def __init__(self, addon: Addon | None = None, enabled: bool = False):
        super().__init__(addon, enabled)
        self.executable = self.feed_event
        self._event_handlers = []

    def on_message(self, filter_: MagicFilter = F, by_me: bool = False):
        def decorator(callback: typing.Callable):
            self.register_message_handler(callback=callback, filter_=filter_, by_me=by_me)
            return callback

        return decorator

    def register_message_handler(self, callback: typing.Callable, filter_: MagicFilter = F, by_me: bool = False):

        self.register_event_handler(
            NewMessageEvent,
            callback,
            filter_=filter_,
            by_me=by_me
        )

    def on_messages_read(
        self, chat_id: int = None, chat_type: str = None, by_me: bool = True
    ):
        def decorator(callback: typing.Callable):
            self.register_messages_read_handler(
                callback=callback, chat_id=chat_id, chat_type=chat_type, by_me=by_me
            )
            return callback

        return decorator

    def register_messages_read_handler(
        self,
        callback: typing.Callable,
        chat_id=None,
        chat_type=None,
        by_me: bool = True,
    ):
        filter_ = F.chat.id == chat_id & F.chat.type == chat_type

        if not chat_id:
            filter_ = F.chat.type == chat_type
        elif not chat_type:
            filter_ = F.chat.id == chat_id
        elif not chat_type and not chat_id:
            filter_ = F

        self.register_event_handler(
            MessageReadEvent,
            callback=callback,
            filter_=filter_,
            by_me=by_me
        )

    def on_event(
            self,
            event: type[Event],
            filter_: MagicFilter = F,
            by_me: bool = True
    ):
        def decorator(callback):
            self.register_event_handler(
                event=event,
                filter_=filter_,
                callback=callback,
                by_me=by_me
            )
            return callback

        return decorator

    def register_event_handler(
            self,
            event: type[Event],
            callback: typing.Callable,
            filter_: MagicFilter = F,
            by_me: bool = True
    ):
        if not iscoroutinefunction(callback):
            raise ValueError("This userbot doesn't supports the synchronous pyrogram handlers")

        self._event_handlers.append(
            {
                "event_type": event,
                "filter": filter_,
                "callback": callback,
                "by_me": by_me
            }
        )

    # noinspection PyProtectedMember
    @staticmethod
    async def resolve_event(
        client: ExtendedClient,
        raw_event: Update,
        users: dict[int, types.User],
        chats: dict[int, types.Chat],
    ):
        account = client.account

        if isinstance(
            raw_event,
            (
                raw_types.UpdateReadChannelOutbox,
                raw_types.UpdateReadHistoryOutbox,
                raw_types.UpdateReadChannelDiscussionOutbox,
                raw_types.UpdateReadChannelInbox,
                raw_types.UpdateReadChannelDiscussionInbox,
                raw_types.UpdateReadHistoryInbox,
            ),
        ):
            by_me = False
            if isinstance(
                raw_event,
                (
                    raw_types.UpdateReadHistoryInbox,
                    raw_types.UpdateReadChannelInbox,
                    raw_types.UpdateReadChannelDiscussionInbox,
                    raw_types.UpdateReadChannelDiscussionOutbox,
                ),
            ):
                by_me = True

            chat = None
            if isinstance(
                raw_event,
                (
                    raw_types.UpdateReadChannelOutbox,
                    raw_types.UpdateReadChannelInbox,
                    raw_types.UpdateReadChannelDiscussionInbox,
                    raw_types.UpdateReadChannelDiscussionOutbox,
                ),
            ):
                peer_id = raw_event.channel_id
                peer = users.get(peer_id) or chats.get(peer_id)

                if isinstance(
                        raw_event,
                        (
                                raw_types.UpdateReadChannelDiscussionInbox,
                                raw_types.UpdateReadChannelDiscussionOutbox
                        )
                ):
                    try:
                        chat = (await client.get_discussion_message("-100" + str(peer_id), raw_event.top_msg_id)).chat
                    except errors.PeerIdInvalid:
                        return

                elif not peer:
                    try:
                        chat = await client.get_chat(int("-100" + str(peer_id)))
                    except errors.PeerIdInvalid:
                        return

                else:
                    # noinspection PyTypeChecker
                    chat = types.Chat._parse_channel_chat(client, peer)

            elif isinstance(raw_event.peer, PeerUser):
                peer_id = raw_event.peer.user_id
                peer = users.get(peer_id) or chats.get(peer_id)

                if not peer:
                    chat = await client.get_chat(peer_id)
                else:
                    chat = types.Chat._parse_user_chat(client, peer)

            elif isinstance(raw_event.peer, PeerChat):
                peer_id = raw_event.peer.chat_id
                peer = users.get(peer_id) or chats.get(peer_id)

                if not peer:
                    chat = await client.get_chat(peer_id)
                else:
                    chat = types.Chat._parse_chat_chat(client, peer)

            return MessageReadEvent(
                chat=chat,
                max_id=getattr(raw_event, "max_id", getattr(raw_event, "read_max_id", None)),
                account=account,
                by_me=by_me,
            )

        elif isinstance(
                raw_event,
                (
                        raw_types.UpdateNewMessage,
                        raw_types.UpdateNewChannelMessage
                )
        ):
            message: types.Message = await types.Message._parse(
                client, raw_event.message, users, chats
            )

            return NewMessageEvent(account=account, message=message)

        elif isinstance(
                raw_event,
                (
                        raw_types.UpdateDeleteChannelMessages,
                        raw_types.UpdateDeleteMessages
                )
        ):

            chat = None

            if isinstance(
                    raw_event,
                    raw_types.UpdateDeleteChannelMessages
            ):
                try:
                    chat = await client.get_chat(f"-100{raw_event.channel_id}")
                except errors.PeerIdInvalid:
                    return

            return DeletedMessagesEvent(messages=raw_event.messages, chat=chat, account=account)

        elif isinstance(
                raw_event,
                (
                        raw_types.UpdateEditMessage,
                        raw_types.UpdateEditChannelMessage
                )
        ):
            message: types.Message = await types.Message._parse(
                client, raw_event.message, users, chats
            )

            return EditedMessageEvent(account=account, message=message)

    async def feed_event(
        self,
        client: ExtendedClient,
        raw_event: Update,
        users: dict[int, types.User],
        chats: dict[int, types.Chat],
    ):
        event = await self.resolve_event(
            client=client, raw_event=raw_event, users=users, chats=chats
        )

        for handler in self._event_handlers:
            event_type = handler.get("event_type")
            if not isinstance(event, event_type):
                continue

            filter_: MagicFilter = handler.get("filter")
            by_me: bool = handler.get("by_me")
            callback: typing.Callable = handler.get("callback")

            if not filter_.resolve(event):
                continue

            if isinstance(event, NewMessageEvent):
                if (
                        event.message.sender_chat is not None or
                        event.message.from_user.id != (await client.account.info).id
                ) and by_me:
                    continue

            elif isinstance(
                event,
                    (
                        UpdateReadHistoryInbox,
                        UpdateReadChannelInbox,
                        UpdateReadChannelDiscussionInbox,
                    )
            ) and by_me:
                continue
            elif isinstance(
                event,
                    (
                        UpdateReadHistoryOutbox,
                        UpdateReadChannelOutbox,
                        UpdateReadChannelDiscussionOutbox,
                    )
            ) and not by_me:
                continue

            await callback(event)

        for manager in self.get_included_managers():
            await manager.execute(
                client, raw_event, users, chats
            )
