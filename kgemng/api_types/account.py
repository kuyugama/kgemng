from pyrogram import Client, types


class ExtendedClient(Client):
    account: "Account"


class Account:

    _info: types.User | None
    _client: Client
    _manager: "AccountManager" = None

    def __init__(self, client: Client):
        self._client = client

    async def resolve_info(self) -> types.User:
        raise NotImplementedError()

    @property
    def info(self) -> types.User:
        raise NotImplementedError()

    @property
    def client(self) -> Client:
        raise NotImplementedError()

    @property
    def manager(self) -> "AccountManager":
        raise NotImplementedError()

    @manager.setter
    def manager(self, manager: "AccountManager"):
        raise NotImplementedError()

    def __str__(self):
        raise NotImplementedError()


class AccountManager:

    _accounts: list[Account]

    def __init__(self):
        raise NotImplementedError()

    def add_account(self, account: Account | Client):
        raise NotImplementedError()

    def pop_account(self, index: int) -> Account | None:
        raise NotImplementedError()

    def get_account(self, index: int):
        raise NotImplementedError()

    def get_accounts(self):
        raise NotImplementedError()

    def foreach(self, callback, *args, **kwargs):
        raise NotImplementedError()

    async def async_foreach(self, callback, *args, **kwargs):
        raise NotImplementedError()
