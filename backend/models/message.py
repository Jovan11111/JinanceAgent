class Message:
    """One line in a chat. type is user, agent, or notice."""

    def __init__(self, chat_id, type, content, created_at=None, id=None, attachments=None):
        self.id = id
        self.chat_id = chat_id
        self.type = type
        self.content = content
        self.created_at = created_at
        self.attachments = list(attachments or [])
