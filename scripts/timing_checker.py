"""
PBL Guardian — Commit Timing Checker
Evaluates whether a commit falls within milestone deadlines and class days.
"""

import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo


def check_timing(config: dict, commit_timestamp_iso: str) -> dict:
    """
    Check if the commit was made on time relative to milestones and class days.

    Args:
        config: The .pbl/config.json contents
        commit_timestamp_iso: ISO 8601 timestamp of the commit (UTC)

    Returns:
        dict with timing evaluation results
    """
    timezone = ZoneInfo(config.get("timezone", "Asia/Kolkata"))
    grace_hours = config.get("grace_period_hours", 2)
    class_days = [d.lower() for d in config.get("class_days", [])]
    milestones = config.get("milestones", [])

    # Parse commit timestamp and convert to team's timezone
    commit_utc = datetime.fromisoformat(commit_timestamp_iso.replace("Z", "+00:00"))
    commit_local = commit_utc.astimezone(timezone)
    commit_day = commit_local.strftime("%A").lower()

    # Check if commit is on a class day
    is_class_day = commit_day in class_days

    # Determine current milestone phase
    current_phase = None
    is_late = False
    is_within_milestone = False
    days_until_deadline = None
    milestone_deadline = None

    for i, milestone in enumerate(milestones):
        deadline = datetime.strptime(milestone["deadline"], "%Y-%m-%d")
        deadline = deadline.replace(tzinfo=timezone)
        deadline_with_grace = deadline + timedelta(hours=grace_hours)

        # Determine the start of the phase window
        if i == 0:
            phase_start = datetime.min.replace(tzinfo=timezone)
        else:
            prev_deadline = datetime.strptime(milestones[i - 1]["deadline"], "%Y-%m-%d")
            phase_start = prev_deadline.replace(tzinfo=timezone)

        # Check if commit falls in this phase
        if commit_local <= deadline_with_grace and (current_phase is None or commit_local > phase_start):
            current_phase = milestone["phase"]
            milestone_deadline = deadline
            days_until_deadline = (deadline.date() - commit_local.date()).days
            is_within_milestone = True

            if commit_local > deadline:
                if commit_local <= deadline_with_grace:
                    is_late = False  # Within grace period
                else:
                    is_late = True

    # If no phase matched, commit is after all deadlines
    if current_phase is None and milestones:
        current_phase = milestones[-1]["phase"]
        last_deadline = datetime.strptime(milestones[-1]["deadline"], "%Y-%m-%d")
        last_deadline = last_deadline.replace(tzinfo=timezone)
        milestone_deadline = last_deadline
        days_until_deadline = (last_deadline.date() - commit_local.date()).days
        is_late = True
        is_within_milestone = False

    # Determine status
    if is_late:
        status = "❌ Late"
        status_emoji = "❌"
    elif is_class_day:
        status = "✅ On Time (Class Day)"
        status_emoji = "✅"
    else:
        status = "✅ On Time"
        status_emoji = "✅"

    # Build result summary
    if days_until_deadline is not None and days_until_deadline >= 0:
        timing_detail = f"{current_phase} — {days_until_deadline} days before deadline"
    elif days_until_deadline is not None:
        timing_detail = f"{current_phase} — {abs(days_until_deadline)} days past deadline"
    else:
        timing_detail = current_phase or "No milestone configured"

    return {
        "passed": not is_late,
        "is_class_day": is_class_day,
        "is_within_milestone": is_within_milestone,
        "is_late": is_late,
        "current_phase": current_phase,
        "days_until_deadline": days_until_deadline,
        "commit_day": commit_local.strftime("%A"),
        "commit_local_time": commit_local.isoformat(),
        "status": status,
        "status_emoji": status_emoji,
        "detail": timing_detail,
    }


if __name__ == "__main__":
    # Quick test
    test_config = {
        "class_days": ["Monday", "Saturday"],
        "timezone": "Asia/Kolkata",
        "grace_period_hours": 2,
        "milestones": [
            {"phase": "Phase 1 - Setup", "deadline": "2026-03-01"},
            {"phase": "Phase 2 - Core", "deadline": "2026-03-15"},
        ],
    }
    result = check_timing(test_config, "2026-02-28T10:30:00+05:30")
    print(json.dumps(result, indent=2, default=str))
