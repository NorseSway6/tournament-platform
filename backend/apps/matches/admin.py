from django.contrib import admin

from apps.matches.models import (
    Match,
    MatchEvent,
    MatchLineup,
    MatchLineupPlayer,
    MatchOfficial,
    ProtocolCorrectionAudit,
    Venue,
)


class MatchLineupPlayerInline(admin.TabularInline):
    model = MatchLineupPlayer
    extra = 0
    autocomplete_fields = ("entry_player",)
    fields = ("entry_player", "number_snapshot", "is_starter", "role")


class MatchLineupInline(admin.TabularInline):
    model = MatchLineup
    extra = 0
    autocomplete_fields = ("entry",)
    fields = ("entry", "status", "reject_reason")
    show_change_link = True


class MatchEventInline(admin.TabularInline):
    model = MatchEvent
    extra = 0
    can_delete = False
    fields = (
        "id",
        "seq",
        "type",
        "entry",
        "player",
        "related_player",
        "period",
        "clock_ms",
        "minute",
        "second",
        "needs_review",
        "source",
        "created_at",
    )
    readonly_fields = fields
    show_change_link = True

    def has_add_permission(self, request, obj=None):
        """Запрещает вручную добавлять события через inline матча"""
        return False


@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tournament",
        "stage",
        "round",
        "home_entry",
        "away_entry",
        "scheduled_at",
        "status",
    )
    list_filter = ("status", "result_type", "tournament", "stage", "venue")
    search_fields = (
        "tournament__name",
        "home_entry__team__name",
        "away_entry__team__name",
        "venue__name",
    )
    autocomplete_fields = (
        "tournament",
        "stage",
        "round",
        "home_entry",
        "away_entry",
        "venue",
    )
    readonly_fields = ("scheduled_end",)
    date_hierarchy = "scheduled_at"
    list_select_related = (
        "tournament",
        "stage",
        "round",
        "home_entry__team",
        "away_entry__team",
        "venue",
    )
    inlines = (MatchLineupInline, MatchEventInline)


@admin.register(MatchLineup)
class MatchLineupAdmin(admin.ModelAdmin):
    list_display = ("id", "match", "entry", "status")
    list_filter = ("status", "match__tournament", "match__stage")
    search_fields = ("match__tournament__name", "entry__team__name")
    autocomplete_fields = ("match", "entry")
    inlines = (MatchLineupPlayerInline,)
    list_select_related = ("match", "entry", "entry__team")


@admin.register(MatchLineupPlayer)
class MatchLineupPlayerAdmin(admin.ModelAdmin):
    list_display = ("entry_player", "lineup", "number_snapshot", "is_starter", "role")
    list_filter = ("is_starter", "role", "lineup__status", "lineup__match__tournament")
    search_fields = (
        "entry_player__player__last_name",
        "entry_player__player__first_name",
        "lineup__match__tournament__name",
    )
    autocomplete_fields = ("lineup", "entry_player")
    list_select_related = ("lineup", "entry_player", "entry_player__player")


@admin.register(MatchEvent)
class MatchEventAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "match",
        "seq",
        "type",
        "entry",
        "player",
        "related_player",
        "device_id",
        "minute",
        "second",
        "period",
        "clock_ms",
        "needs_review",
        "source",
        "created_at",
    )
    list_filter = ("type", "match__tournament", "created_at")
    search_fields = (
        "match__id",
        "entry__team__name",
        "player__player__last_name",
        "player__player__first_name",
    )
    readonly_fields = (
        "id",
        "match",
        "seq",
        "client_seq",
        "type",
        "entry",
        "player",
        "minute",
        "second",
        "client_created_at",
        "created_at",
        "target_event",
    )
    list_select_related = ("match", "entry__team", "player__player")


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ("name", "organization", "address")
    list_filter = ("organization",)
    search_fields = ("name", "address", "organization__name")
    autocomplete_fields = ("organization",)


@admin.register(MatchOfficial)
class MatchOfficialAdmin(admin.ModelAdmin):
    list_display = ("match", "official", "role")
    list_filter = ("role", "match__tournament")
    search_fields = ("official__username", "official__display_name", "match__id")
    autocomplete_fields = ("match", "official")


@admin.register(ProtocolCorrectionAudit)
class ProtocolCorrectionAuditAdmin(admin.ModelAdmin):
    list_display = (
        "match",
        "target_event",
        "organization",
        "actor_reference",
        "created_at",
    )
    list_filter = ("organization", "created_at")
    search_fields = ("reason", "actor_reference", "match__id")
    readonly_fields = tuple(
        field.name for field in ProtocolCorrectionAudit._meta.fields
    )
