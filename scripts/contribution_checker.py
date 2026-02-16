"""
PBL Guardian — Contribution Equity Checker
Analyzes git logs to measure team member contribution fairness using Gini coefficient.
"""

import json
import os
import subprocess


def _parse_git_shortlog() -> dict:
    """Parse git shortlog to get commit counts per author."""
    try:
        result = subprocess.run(
            ["git", "shortlog", "-sn", "--all", "--no-merges"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        members = {}
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            parts = line.split("\t", 1)
            if len(parts) == 2:
                count = int(parts[0].strip())
                name = parts[1].strip()
                members[name] = {"commits": count, "additions": 0, "deletions": 0}
        return members
    except Exception:
        return {}


def _parse_git_numstat(members: dict) -> dict:
    """Parse git log numstat to get lines added/deleted per author."""
    try:
        result = subprocess.run(
            ["git", "log", "--all", "--no-merges", "--format=%aN", "--numstat"],
            capture_output=True,
            text=True,
            timeout=60,
        )
        current_author = None
        for line in result.stdout.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            # Lines with tab-separated numbers are numstat lines
            parts = line.split("\t")
            if len(parts) == 3:
                try:
                    added = int(parts[0]) if parts[0] != "-" else 0
                    deleted = int(parts[1]) if parts[1] != "-" else 0
                    if current_author and current_author in members:
                        members[current_author]["additions"] += added
                        members[current_author]["deletions"] += deleted
                except ValueError:
                    pass
            else:
                # This line is an author name
                current_author = line
                if current_author not in members:
                    members[current_author] = {"commits": 0, "additions": 0, "deletions": 0}
        return members
    except Exception:
        return members


def _calculate_gini(values: list) -> float:
    """
    Calculate the Gini coefficient for a list of values.
    0 = perfect equality, 1 = total inequality.
    """
    if not values or sum(values) == 0:
        return 0.0

    n = len(values)
    if n == 1:
        return 0.0

    sorted_values = sorted(values)
    cumulative = 0
    total = sum(sorted_values)

    for i, v in enumerate(sorted_values):
        cumulative += v

    # Gini formula
    numerator = 0
    for i, xi in enumerate(sorted_values):
        for j, xj in enumerate(sorted_values):
            numerator += abs(xi - xj)

    denominator = 2 * n * total
    if denominator == 0:
        return 0.0

    return numerator / denominator


def check_contributions(min_contribution_pct: float = 10.0) -> dict:
    """
    Analyze team contribution equity from git history.

    Args:
        min_contribution_pct: Minimum percentage of commits a member should have

    Returns:
        dict with contribution evaluation results
    """
    # Parse git data
    members = _parse_git_shortlog()
    members = _parse_git_numstat(members)

    if not members:
        return {
            "passed": True,
            "members": {},
            "gini_coefficient": 0.0,
            "warnings": ["No git history found"],
            "status": "⚠️ No history",
            "status_emoji": "⚠️",
            "detail": "No git history available",
        }

    total_commits = sum(m["commits"] for m in members.values())
    total_additions = sum(m["additions"] for m in members.values())

    # Calculate percentages
    for name, data in members.items():
        if total_commits > 0:
            data["commit_pct"] = round((data["commits"] / total_commits) * 100, 1)
        else:
            data["commit_pct"] = 0.0
        if total_additions > 0:
            data["addition_pct"] = round((data["additions"] / total_additions) * 100, 1)
        else:
            data["addition_pct"] = 0.0

    # Calculate Gini coefficient on commits
    commit_counts = [m["commits"] for m in members.values()]
    gini = round(_calculate_gini(commit_counts), 3)

    # Generate warnings
    warnings = []
    for name, data in members.items():
        if data["commit_pct"] < min_contribution_pct and total_commits > 5:
            warnings.append(
                f"⚠️ {name} has only {data['commit_pct']}% of commits "
                f"({data['commits']}/{total_commits})"
            )

    # Check for single-person dominance
    max_pct = max(m["commit_pct"] for m in members.values()) if members else 0
    if max_pct > 70 and len(members) > 1:
        dominant = max(members.items(), key=lambda x: x[1]["commits"])
        warnings.append(
            f"🚨 {dominant[0]} dominates with {dominant[1]['commit_pct']}% of all commits"
        )

    # Determine pass/fail
    if gini > 0.5 and len(members) > 1:
        passed = False
        equity_label = "Unbalanced"
    elif warnings:
        passed = True  # Warnings don't fail, but are noted
        equity_label = "Needs Attention"
    else:
        passed = True
        equity_label = "Balanced"

    if gini <= 0.2:
        status_emoji = "✅"
    elif gini <= 0.4:
        status_emoji = "⚠️"
    else:
        status_emoji = "❌"

    return {
        "passed": passed,
        "members": members,
        "gini_coefficient": gini,
        "total_commits": total_commits,
        "total_additions": total_additions,
        "warnings": warnings,
        "equity_label": equity_label,
        "status": f"{status_emoji} Gini: {gini} ({equity_label})",
        "status_emoji": status_emoji,
        "detail": f"Gini: {gini} ({equity_label}) — {len(members)} contributors, {total_commits} commits",
    }


if __name__ == "__main__":
    result = check_contributions()
    print(json.dumps(result, indent=2))
