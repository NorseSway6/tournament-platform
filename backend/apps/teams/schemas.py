from ninja import Schema


class PersonSummary(Schema):
    id: int
    name: str


class CaptainSummary(Schema):
    id: int
    name: str

    @staticmethod
    def resolve_name(user) -> str:
        """Извлекает публичное отображаемое имя капитана."""
        return user.display_name or user.get_full_name() or user.username


class TournamentMembership(Schema):
    id: int
    slug: str
    name: str
    status: str


class TeamTournamentMembership(TournamentMembership):
    entry_status: str

    @staticmethod
    def resolve_id(entry) -> int:
        """Берёт ID турнира из заявки команды."""
        return entry.tournament_id

    @staticmethod
    def resolve_slug(entry) -> str:
        """Берёт slug турнира из заявки команды."""
        return entry.tournament.slug

    @staticmethod
    def resolve_name(entry) -> str:
        """Берёт название турнира из заявки команды."""
        return entry.tournament.name

    @staticmethod
    def resolve_status(entry) -> str:
        """Возвращает статус турнира, не подменяя его статусом заявки."""
        return entry.tournament.status

    @staticmethod
    def resolve_entry_status(entry) -> str:
        """Возвращает статус заявки команды на турнир."""
        return entry.status


class TeamOut(Schema):
    id: int
    name: str
    city: str
    captain: CaptainSummary
    tournaments: list[TeamTournamentMembership]

    @staticmethod
    def resolve_tournaments(team) -> list:
        """Использует отфильтрованные публичные заявки из selector."""
        return team.public_entries


class PlayerEntryOut(Schema):
    entry_id: int
    number: int
    status: str
    team: PersonSummary
    tournament: TournamentMembership

    @staticmethod
    def resolve_team(membership):
        """Возвращает команду, связанную с заявкой игрока."""
        return membership.entry.team

    @staticmethod
    def resolve_tournament(membership):
        """Возвращает турнир, связанный с заявкой игрока."""
        return membership.entry.tournament


class PlayerOut(Schema):
    id: int
    first_name: str
    last_name: str
    middle_name: str
    full_name: str
    entries: list[PlayerEntryOut]

    @staticmethod
    def resolve_full_name(player) -> str:
        """Собирает полное имя из публичных полей профиля игрока."""
        return " ".join(
            part
            for part in (player.last_name, player.first_name, player.middle_name)
            if part
        )

    @staticmethod
    def resolve_entries(player) -> list:
        """Возвращает только публичные активные составы игрока."""
        return player.public_memberships
