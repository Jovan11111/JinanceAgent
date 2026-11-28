class Chat:
    """One saved conversation."""

    def __init__(
        self,
        title="New chat",
        id=None,
        created_at=None,
        updated_at=None,
        summary=None,
        summary_until_id=None,
        active_skill=None,
    ):
        self.id = id
        self.title = title
        self.created_at = created_at
        self.updated_at = updated_at
        self.summary = summary
        self.summary_until_id = summary_until_id
        self.active_skill = active_skill
