from __future__ import annotations

from datetime import datetime, timezone


def pub_date(published: str) -> str:
    """Format an ISO published string as 'May 8 · 11h ago' for news article cards.

    Always shows the absolute date so users know exactly when it was published,
    plus a relative duration for quick scanning. Falls back to '–' for missing
    or unparseable dates so templates always get a safe value.

    Examples:
        30 minutes old  → "May 9 · 30m ago"
        11 hours old    → "May 8 · 11h ago"
        1 day old       → "May 8 · Yesterday"
        3 days old      → "May 6 · 3d ago"
        > 7 days, same year  → "Apr 30"
        > 7 days, prior year → "Apr 30, 2025"
        no date         → "–"
    """
    if not published:
        return "–"
    try:
        dt = datetime.fromisoformat(published.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        diff = now - dt
        total_hours = diff.total_seconds() / 3600

        # Absolute date label — always shown
        if dt.year == now.year:
            date_label = f"{dt.strftime('%b')} {dt.day}"
        else:
            date_label = f"{dt.strftime('%b')} {dt.day}, {dt.year}"

        # Relative duration — only shown for articles within the past week
        if total_hours < 1:
            mins = max(1, int(diff.total_seconds() / 60))
            rel = f"{mins}m ago"
        elif total_hours < 24:
            rel = f"{int(total_hours)}h ago"
        elif diff.days == 1:
            rel = "Yesterday"
        elif diff.days < 7:
            rel = f"{diff.days}d ago"
        else:
            return date_label  # old enough that the date alone is sufficient

        return f"{date_label} · {rel}"
    except Exception:
        return published[:10] if published else "–"
