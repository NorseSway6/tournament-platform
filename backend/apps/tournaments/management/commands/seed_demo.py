"""Заполняет БД небольшим набором демо-данных для фронтенда.

Запуск:  python manage.py seed_demo
Повторный запуск ничего не дублирует: если демо-лига уже есть, команда просто сообщит об этом.
Полный сброс: удалите базу (docker compose down -v) и запустите миграции заново.
"""

from datetime import timedelta
from uuid import uuid4

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from apps.identity_access.models import User
from apps.matches.models import (
    Match,
    MatchLineup,
    MatchLineupPlayer,
    MatchOfficial,
    Venue,
)
from apps.matches.schemas.events import MatchEventCreate
from apps.matches.services.protocol import (
    acquire_match_lease,
    append_match_event,
    confirm_match,
    release_match_lease,
)
from apps.organizations.models import Organization, OrganizationMember
from apps.teams.models import EntryPlayer, Player, Team, TournamentEntry
from apps.tournaments.models import Round, Stage, Tournament

PASSWORD = "demo12345"
ORG_SLUG = "demo-liga"

# (username, имя на экране, признак администратора платформы)
USERS = [
    ("demo_admin", "Админ Платформы", True),
    ("demo_org", "Олег Организатор", False),
    ("demo_ref", "Роман Судья", False),
    ("demo_cap1", "Капитан Спартака", False),
    ("demo_cap2", "Капитан Динамо", False),
    ("demo_cap3", "Капитан Торпедо", False),
    ("demo_cap4", "Капитан Локомотива", False),
    ("demo_fan", "Зритель Без Ролей", False),
]

# (название команды, username капитана)
TEAMS = [
    ("Спартак Демо", "demo_cap1"),
    ("Динамо Демо", "demo_cap2"),
    ("Торпедо Демо", "demo_cap3"),
    ("Локомотив Демо", "demo_cap4"),
]

FIRST_NAMES = ["Иван", "Пётр", "Сергей", "Андрей", "Дмитрий", "Максим", "Артём"]
LAST_NAMES = ["Иванов", "Петров", "Сидоров", "Смирнов", "Кузнецов", "Попов", "Волков"]


class Command(BaseCommand):
    help = "Создаёт демо-организацию, турнир, команды, матчи и пользователей для фронтенда."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Разрешить запуск при DEBUG=false (по умолчанию команда работает только в DEBUG).",
        )

    def handle(self, *args, **options):
        if not settings.DEBUG and not options["force"]:
            raise CommandError("seed_demo работает только при DJANGO_DEBUG=true (или с --force).")
        if Organization.objects.filter(slug=ORG_SLUG).exists():
            self.stdout.write("Демо-данные уже есть, ничего не делаю.")
            return

        with transaction.atomic():
            users = self._create_users()
            org = self._create_organization(users)
            tournament, entries, players = self._create_tournament(org, users)
            matches = self._create_matches(org, tournament, entries, users)
            self._play_matches(matches, entries, players, users["demo_ref"])

        self._print_summary(org, tournament, matches)

    # ---------- пользователи и организация ----------

    def _create_users(self):
        users = {}
        for username, display_name, is_admin in USERS:
            user = User.objects.create_user(
                username=username,
                email=f"{username}@example.com",
                password=PASSWORD,
                display_name=display_name,
            )
            if is_admin:
                user.is_platform_admin = True
                user.is_staff = True
                user.is_superuser = True
                user.save()
            users[username] = user
        return users

    def _create_organization(self, users):
        org = Organization.objects.create(
            slug=ORG_SLUG,
            name="Демо-лига",
            city="Москва",
            timezone="Europe/Moscow",
            description="Тестовая организация для разработки фронтенда",
        )
        OrganizationMember.objects.create(
            organization=org, user=users["demo_org"], role=OrganizationMember.Role.ORGANIZER
        )
        OrganizationMember.objects.create(
            organization=org, user=users["demo_ref"], role=OrganizationMember.Role.REFEREE
        )
        return org

    # ---------- турнир, команды, составы ----------

    def _create_tournament(self, org, users):
        today = timezone.localdate()
        tournament = Tournament.objects.create(
            organization=org,
            slug="demo-cup",
            name="Кубок Демо",
            season="2026",
            status=Tournament.Status.ONGOING,
            visibility=Tournament.Visibility.PUBLIC,
            starts_on=today - timedelta(days=14),
            ends_on=today + timedelta(days=30),
            regulation={
                "standings": {
                    "points_for_win": 3,
                    "points_for_draw": 1,
                    "points_for_loss": 0,
                    "tie_breakers": ["points", "goal_difference", "goals_for", "team_id"],
                }
            },
        )
        entries = []
        players = []  # players[i] — список записей EntryPlayer команды i
        for team_index, (team_name, captain_username) in enumerate(TEAMS):
            captain = users[captain_username]
            team = Team.objects.create(name=team_name, captain=captain, city="Москва")
            entry = TournamentEntry.objects.create(
                tournament=tournament, team=team, status=TournamentEntry.Status.ACCEPTED
            )
            entries.append(entry)
            team_players = []
            for number in range(1, 8):
                player = Player.objects.create(
                    first_name=FIRST_NAMES[number - 1],
                    last_name=f"{LAST_NAMES[(number + team_index) % 7]}",
                    created_by=captain,
                )
                team_players.append(
                    EntryPlayer.objects.create(
                        entry=entry, tournament=tournament, player=player, number=number
                    )
                )
            players.append(team_players)
        return tournament, entries, players

    # ---------- расписание ----------

    def _create_matches(self, org, tournament, entries, users):
        now = timezone.now()
        venue1 = Venue.objects.create(organization=org, name="Стадион «Центральный»")
        venue2 = Venue.objects.create(organization=org, name="Поле №2")
        stage = Stage.objects.create(
            tournament=tournament, ord=1, kind=Stage.Kind.LEAGUE, name="Чемпионат"
        )
        rounds = [
            Round.objects.create(stage=stage, ord=number, name=f"Тур {number}")
            for number in (1, 2, 3)
        ]
        a, b, c, d = entries  # Спартак, Динамо, Торпедо, Локомотив

        # (тур, хозяева, гости, площадка, смещение времени, статус до розыгрыша)
        plan = [
            (rounds[0], a, b, venue1, timedelta(days=-7), Match.Status.SCHEDULED),
            (rounds[0], c, d, venue2, timedelta(days=-7), Match.Status.SCHEDULED),
            (rounds[1], a, c, venue1, timedelta(days=-2), Match.Status.SCHEDULED),
            (rounds[1], b, d, venue2, timedelta(hours=-1), Match.Status.SCHEDULED),
            (rounds[2], a, d, venue1, timedelta(days=2), Match.Status.LINEUPS_OPEN),
            (rounds[2], b, c, venue2, timedelta(days=2, hours=2), Match.Status.SCHEDULED),
        ]
        matches = []
        for round_, home, away, venue, shift, status in plan:
            match = Match.objects.create(
                tournament=tournament,
                stage=stage,
                round=round_,
                home_entry=home,
                away_entry=away,
                venue=venue,
                scheduled_at=now + shift,
                status=status,
            )
            MatchOfficial.objects.create(
                match=match,
                official=users["demo_ref"],
                role=MatchOfficial.Role.REFEREE,
            )
            matches.append(match)
        return matches

    # ---------- розыгрыш матчей через те же сервисы, что и API ----------

    def _play_matches(self, matches, entries, players, referee):
        a, b, c, d = entries
        pa, pb, pc, pd = players
        m1, m2, m3, m4 = matches[:4]

        # матч 1: Спартак 2:1 Динамо (подтверждён)
        self._play(
            m1,
            referee,
            [
                ("goal", a, pa[5], 12),  # гол Спартака, 12-я минута
                ("yellow", b, pb[3], 25),
                ("goal", b, pb[6], 30),
                ("goal", a, pa[5], 65),
            ],
        )
        # матч 2: Торпедо 0:0 Локомотив (подтверждён)
        self._play(m2, referee, [("yellow", c, pc[2], 40)])
        # матч 3: Спартак 3:1 Торпедо (подтверждён)
        self._play(
            m3,
            referee,
            [
                ("goal", a, pa[5], 10),
                ("goal", c, pc[6], 33),
                ("goal", a, pa[5], 58),
                ("goal", a, pa[4], 80),
            ],
        )
        # матч 4: Динамо — Локомотив идёт прямо сейчас (счёт 1:0, не завершён)
        self._play(m4, referee, [("goal", b, pb[6], 15)], finish=False)

        # состав на матч 4 уже принят, чтобы судья видел заявки
        for entry, team_players in ((b, pb), (d, pd)):
            lineup = MatchLineup.objects.create(
                match=m4, entry=entry, status=MatchLineup.Status.ACCEPTED
            )
            for index, entry_player in enumerate(team_players[:5]):
                MatchLineupPlayer.objects.create(
                    lineup=lineup,
                    entry_player=entry_player,
                    number_snapshot=entry_player.number,
                    is_starter=True,
                    role=MatchLineupPlayer.Role.CAPTAIN if index == 0 else MatchLineupPlayer.Role.PLAYER,
                )

    def _play(self, match, referee, events, finish=True):
        """Берёт аренду, добавляет события и (если нужно) завершает и подтверждает матч."""
        lease = acquire_match_lease(match.id, referee.id)
        token = lease["lease_token"]
        device_id = uuid4()
        seq = 0

        def add(event_type, period, clock_min, entry=None, entry_player=None):
            nonlocal seq
            seq += 1
            payload = MatchEventCreate(
                lease_token=token,
                id=uuid4(),
                device_id=device_id,
                client_seq=seq,
                type=event_type,
                entry_id=entry.id if entry else None,
                entry_player_id=entry_player.id if entry_player else None,
                period=period,
                clock_ms=clock_min * 60_000,
            ).model_dump()
            append_match_event(match.id, referee.id, payload)

        add("period_start", "first_half", 0)
        for event_type, entry, entry_player, minute in events:
            period = "first_half" if minute <= 45 else "second_half"
            add(event_type, period, minute, entry, entry_player)
        if finish:
            add("finish", "second_half", 90)
            confirm_match(match.id, referee.id, token)
        release_match_lease(match.id, referee.id, token)

    # ---------- вывод ----------

    def _print_summary(self, org, tournament, matches):
        self.stdout.write(self.style.SUCCESS("Демо-данные созданы."))
        self.stdout.write(f"Пароль у всех пользователей: {PASSWORD}")
        for username, display_name, _ in USERS:
            self.stdout.write(f"  {username:<11} {display_name}")
        self.stdout.write(f"Организация id={org.id} slug={org.slug}")
        self.stdout.write(f"Турнир id={tournament.id} slug={tournament.slug}")
        labels = ["подтверждён", "подтверждён", "подтверждён", "идёт сейчас", "скоро", "скоро"]
        for match, label in zip(matches, labels, strict=True):
            self.stdout.write(f"  матч id={match.id} ({label})")
