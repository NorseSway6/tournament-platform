from ninja import Schema


class GroupSummary(Schema):
    """Краткие сведения о группе этапа."""

    id: int
    name: str
    ord: int


class EntryTeamOut(Schema):
    """Публичные сведения о команде в заявке."""

    id: int
    name: str
    city: str


class OrganizationSummary(Schema):
    """Краткие сведения об организации, проводящей турнир."""

    id: int
    name: str
    slug: str
    timezone: str


class EntryCaptainOut(Schema):
    """Публичное имя капитана команды-заявителя."""

    id: int
    name: str

    @staticmethod
    def resolve_name(user) -> str:
        return user.display_name or user.get_full_name() or user.username


class RoundSummary(Schema):
    """Краткие сведения о туре этапа."""

    id: int
    name: str
    ord: int
