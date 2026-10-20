from django.contrib import admin

from apps.teams.models import EntryPlayer, Player, Team, TournamentEntry


class TeamEntryInline(admin.TabularInline):
    model = TournamentEntry
    extra = 0
    fields = ("tournament", "status")
    show_change_link = True


class EntryPlayerInline(admin.TabularInline):
    model = EntryPlayer
    extra = 0
    autocomplete_fields = ("player",)
    fields = ("player", "number", "status")


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ("name", "captain", "city", "created_at")
    list_filter = ("city",)
    search_fields = ("name", "city", "captain__username", "captain__display_name")
    autocomplete_fields = ("captain",)
    readonly_fields = ("created_at", "updated_at")
    inlines = (TeamEntryInline,)


@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ("last_name", "first_name", "middle_name", "birth_date", "user")
    search_fields = ("last_name", "first_name", "middle_name", "user__username", "user__phone")
    autocomplete_fields = ("user",)
    list_select_related = ("user",)


@admin.register(TournamentEntry)
class TournamentEntryAdmin(admin.ModelAdmin):
    list_display = ("team", "tournament", "status", "submitted_at", "decision_comment")
    list_filter = ("status", "tournament__organization", "tournament")
    search_fields = ("team__name", "tournament__name")
    autocomplete_fields = ("team", "tournament")
    inlines = (EntryPlayerInline,)
    list_select_related = ("team", "tournament")


@admin.register(EntryPlayer)
class EntryPlayerAdmin(admin.ModelAdmin):
    list_display = ("player", "entry", "number", "status")
    list_filter = ("status", "entry__tournament")
    search_fields = ("player__last_name", "player__first_name", "entry__team__name", "entry__tournament__name")
    autocomplete_fields = ("entry", "player")
    list_select_related = ("player", "entry", "entry__team", "entry__tournament")
