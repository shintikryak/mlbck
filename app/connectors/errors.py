class MailProviderError(Exception):
    pass


class MailProviderAuthError(MailProviderError):
    pass


class MailProviderConnectionError(MailProviderError):
    pass


class MailProviderTimeoutError(MailProviderError):
    pass


class MailProviderMailboxError(MailProviderError):
    pass


class MailProviderSendError(MailProviderError):
    pass