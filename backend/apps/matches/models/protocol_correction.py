from django.db import models


class ProtocolCorrectionAudit(models.Model):
    """Stores the reason and immutable event links for an organizer correction."""

    match = models.ForeignKey(
        "matches.Match", on_delete=models.PROTECT, related_name="correction_audits"
    )
    target_event = models.ForeignKey(
        "matches.MatchEvent", on_delete=models.PROTECT, related_name="correction_audits"
    )
    void_event = models.OneToOneField(
        "matches.MatchEvent", on_delete=models.PROTECT, related_name="correction_audit_void"
    )
    replacement_event = models.OneToOneField(
        "matches.MatchEvent",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="correction_audit_replacement",
    )
    organization = models.ForeignKey(
        "organizations.Organization", on_delete=models.PROTECT, related_name="protocol_corrections"
    )
    actor_reference = models.CharField(max_length=100)
    reason = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at", "id"]

    def __str__(self) -> str:
        """Describes the corrected protocol event."""
        return f"Correction for event {self.target_event_id} in match {self.match_id}"
