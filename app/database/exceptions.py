class ConversationNotFound(Exception):
    """Error for when the conversation supplied could not be found in the database."""
    pass

class AccountNotFound(Exception):
    pass

class RequestAlreadyOutgoing(Exception):
    pass

class NotFound(Exception):
    pass

class NoPermission(Exception):
    pass