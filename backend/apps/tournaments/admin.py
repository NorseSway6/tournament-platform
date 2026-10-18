from django.contrib import admin

from apps.teams.models import EntryPlayer, TournamentEntry
from apps.tournaments.models import Round, Stage, Tournament


class RoundInline(admin.TabularInline):
    model = Round
    extra = 0
    fields = ("ord", "name")


class StageInline(admin.TabularInline):
    model = Stage
    extra = 0
    fields = ("ord", "name", "kind")
    show_change_link = True


class TournamentEntryInline(admin.TabularInline):
    model = TournamentEntry
    extra = 0
    fields = ("team", "status")
    show_change_link = True


class EntryPlayerInline(admin.TabularInline):
    model = EntryPlayer
    extra = 0
    autocomplete_fields = ("player",)
    fields = ("player", "number", "status")


@admin.register(Tournament)
class TournamentAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "organization",
        "season",
        "status",
        "visibility",
        "starts_on",
        "ends_on",
    )
    list_filter = ("status", "visibility", "organization")
    search_fields = ("name", "slug", "season", "organization__name")
    prepopulated_fields = {"slug": ("name",)}
    autocomplete_fields = ("organization",)
    readonly_fields = ("created_at", "updated_at")
    date_hierarchy = "starts_on"
    inlines = (StageInline, TournamentEntryInline)
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "organization",
                    "name",
                    "slug",
                    "season",
                    "status",
                    "visibility",
                )
            },
        ),
        ("Schedule", {"fields": ("registration_deadline", "starts_on", "ends_on")}),
        ("Regulations", {"fields": ("regulation",)}),
        ("Dates", {"fields": ("created_at", "updated_at")}),
    )


@admin.register(Stage)
class StageAdmin(admin.ModelAdmin):
    list_display = ("name", "tournament", "ord", "kind")
    list_filter = ("kind", "tournament__organization")
    search_fields = ("name", "tournament__name", "tournament__slug")
    autocomplete_fields = ("tournament",)
    inlines = (RoundInline,)


@admin.register(Round)
class RoundAdmin(admin.ModelAdmin):
    list_display = ("__str__", "stage", "ord", "tournament_name")
    list_filter = ("stage__tournament",)
    search_fields = ("name", "stage__name", "stage__tournament__name")
    autocomplete_fields = ("stage",)

    @admin.display(description="Tournament", ordering="stage__tournament__name")
    def tournament_name(self, obj):
        """Показывает турнир раунда через связанный этап"""
        return obj.stage.tournament.name
