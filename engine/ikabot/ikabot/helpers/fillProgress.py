"""Bounded, nonblocking shared progress for one managed warehouse process."""
STAGES = ("initializing", "preparing", "checking_destination", "waiting_ships",
          "checking_source", "checking_current_city", "switching_city",
          "checking_guard", "verifying_token", "submitting", "verifying_cargo",
          "finished", "capacity_reached", "checking_transport_response",
          "invalid_transport_response", "transport_rejected",
          "transport_feedback_unconfirmed", "transport_source_mismatch")

def mark(session, stage, submitted=None, verified=None):
    progress = getattr(session, "_daedalus_fill_progress", None)
    if progress is None or getattr(session, "_daedalus_managed_fill", False) is not True:
        return
    if submitted is not None:
        progress[1] = submitted
    if verified is not None:
        progress[2] = verified
    progress[0] = STAGES.index(stage)

def snapshot(progress):
    return {"stage": STAGES[progress[0]], "submitted": progress[1],
            "verified": progress[2]}
