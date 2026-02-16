"""
PBL Guardian — Main Evaluation Orchestrator

Runs all evaluation checks and generates a markdown report
that gets posted as a commit comment by the GitHub Action.
"""

import json
import os
import sys

# Add scripts directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from timing_checker import check_timing
from quality_checker import check_quality
from proof_checker import check_proofs
from contribution_checker import check_contributions
from plagiarism_checker import check_plagiarism


def load_config(config_path: str = ".pbl/config.json") -> dict:
    """Load the PBL configuration file."""
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️ Config file not found at {config_path}, using defaults")
        return {
            "team_id": "unknown",
            "team_name": "Unknown Team",
            "class_days": [],
            "timezone": "Asia/Kolkata",
            "grace_period_hours": 2,
            "milestones": [],
            "language": "python",
            "proof_directory": "proofs/",
            "min_quality_score": 7.0,
            "plagiarism_threshold": 30,
        }


def run_evaluation(
    config_path: str = ".pbl/config.json",
    commit_sha: str = None,
    commit_timestamp: str = None,
    commit_author: str = None,
    github_token: str = None,
    source_dir: str = "src",
    reference_dir: str = "references",
) -> dict:
    """
    Run all evaluation checks and return the combined report.

    Returns:
        dict with all evaluation results and a formatted markdown report
    """
    config = load_config(config_path)
    commit_sha = commit_sha or os.environ.get("GITHUB_SHA", "HEAD")
    commit_timestamp = commit_timestamp or os.environ.get("COMMIT_TIMESTAMP", "")
    commit_author = commit_author or os.environ.get("COMMIT_AUTHOR", "unknown")
    github_token = github_token or os.environ.get("GITHUB_TOKEN", "")

    results = {}

    # 1. Timing Check
    print("🔍 Running timing check...")
    if commit_timestamp:
        results["timing"] = check_timing(config, commit_timestamp)
    else:
        results["timing"] = {
            "passed": True,
            "status": "⚠️ No timestamp available",
            "status_emoji": "⚠️",
            "detail": "Commit timestamp not available",
            "is_class_day": False,
            "current_phase": "Unknown",
            "commit_day": "Unknown",
        }

    # 2. Code Quality Check
    print("🔍 Running code quality check...")
    results["quality"] = check_quality(
        source_dir=source_dir,
        language=config.get("language", "python"),
        min_score=config.get("min_quality_score", 7.0),
    )

    # 3. Proof of Progress Check
    print("🔍 Running proof check...")
    results["proofs"] = check_proofs(
        proof_dir=config.get("proof_directory", "proofs/"),
        commit_sha=commit_sha,
    )

    # 4. Contribution Equity Check
    print("🔍 Running contribution check...")
    results["contribution"] = check_contributions()

    # 5. Plagiarism Check (5 Layers)
    print("🔍 Running 5-layer plagiarism check...")
    results["plagiarism"] = check_plagiarism(
        source_dir=source_dir,
        reference_dir=reference_dir,
        config=config,
        github_token=github_token,
    )

    # Generate markdown report
    report = generate_markdown_report(results, config, commit_sha, commit_author)

    return {
        "results": results,
        "report": report,
        "all_passed": all(r.get("passed", True) for r in results.values()),
        "config": config,
    }


def generate_markdown_report(
    results: dict,
    config: dict,
    commit_sha: str,
    commit_author: str,
) -> str:
    """Generate a formatted markdown report for the bot comment."""

    timing = results.get("timing", {})
    quality = results.get("quality", {})
    proofs = results.get("proofs", {})
    contribution = results.get("contribution", {})
    plagiarism = results.get("plagiarism", {})
    plag_layers = plagiarism.get("layers", {})

    # Build the main table
    lines = [
        "## 🤖 PBL Guardian — Evaluation Report",
        "",
        "| Metric | Result | Status |",
        "|---|---|---|",
        f"| ⏰ Timing | {timing.get('detail', 'N/A')} | {timing.get('status_emoji', '⚠️')} |",
        f"| 📊 Code Quality | {quality.get('detail', 'N/A')} | {quality.get('status_emoji', '⚠️')} |",
        f"| 📸 Proofs | {proofs.get('detail', 'N/A')} | {proofs.get('status_emoji', '⚠️')} |",
        f"| 👥 Contribution | {contribution.get('detail', 'N/A')} | {contribution.get('status_emoji', '⚠️')} |",
    ]

    # Add plagiarism layers
    l1 = plag_layers.get("L1_copydetect", {})
    l3 = plag_layers.get("L3_github_search", {})
    l4 = plag_layers.get("L4_ai_detection", {})
    l5 = plag_layers.get("L5_commit_patterns", {})

    lines.append(f"| 🔍 Plagiarism (L1 Corpus) | {l1.get('detail', 'N/A')} | {l1.get('passed', True) and '✅' or '🚨'} |")
    lines.append(f"| 🔍 Plagiarism (L3 GitHub) | {l3.get('detail', 'N/A')} | {l3.get('passed', True) and '✅' or '🚨'} |")
    lines.append(f"| 🤖 AI Detection (L4) | {l4.get('detail', 'N/A')} | {l4.get('passed', True) and '✅' or '🚨'} |")
    lines.append(f"| 📈 Commit Patterns (L5) | {l5.get('detail', 'N/A')} | {l5.get('passed', True) and '✅' or '🚨'} |")

    # Metadata line
    lines.extend([
        "",
        f"**Commit by:** {commit_author} | "
        f"**Phase:** {timing.get('current_phase', 'N/A')} | "
        f"**Class Day:** {'✅ ' + timing.get('commit_day', '') if timing.get('is_class_day') else '—'}",
    ])

    # Expandable details for plagiarism
    plag_details = []
    if l1.get("flagged_files"):
        plag_details.append(f"**L1 Copydetect:** {l1['detail']}")
        for f in l1["flagged_files"][:3]:
            plag_details.append(f"  - {f.get('detail', str(f))}")

    if l3.get("flagged"):
        plag_details.append(f"**L3 GitHub Search:** {l3['detail']}")
        for f in l3["flagged"][:3]:
            plag_details.append(f"  - `{f['function']}` in {f['file']} → matches {f['top_match_repo']}")

    if l4.get("flags"):
        plag_details.append(f"**L4 AI Detection:** {l4['detail']}")
        for f in l4["flags"][:3]:
            plag_details.append(f"  - {f}")

    if l5.get("flags"):
        plag_details.append(f"**L5 Commit Patterns:** {l5['detail']}")
        for f in l5["flags"][:3]:
            plag_details.append(f"  - {f}")

    # Quality issues details
    quality_details = []
    if quality.get("issues"):
        quality_details.append("**Top Issues:**")
        for issue in quality["issues"][:5]:
            quality_details.append(
                f"  - `{issue.get('file', '?')}:{issue.get('line', '?')}` "
                f"[{issue.get('symbol', '')}] {issue.get('message', '')}"
            )

    # Contribution details
    contrib_details = []
    members = contribution.get("members", {})
    if members:
        contrib_details.append("| Member | Commits | Additions | % |")
        contrib_details.append("|---|---|---|---|")
        for name, data in sorted(members.items(), key=lambda x: x[1]["commits"], reverse=True):
            contrib_details.append(
                f"| {name} | {data['commits']} | +{data['additions']}/-{data['deletions']} | {data.get('commit_pct', 0)}% |"
            )

    if contribution.get("warnings"):
        for w in contribution["warnings"]:
            contrib_details.append(f"\n{w}")

    # Build expandable sections
    if plag_details or quality_details or contrib_details:
        lines.append("")

    if plag_details:
        lines.append("<details><summary>🔍 Plagiarism Details</summary>")
        lines.append("")
        lines.extend(plag_details)
        lines.append("")
        lines.append("</details>")

    if quality_details:
        lines.append("<details><summary>📊 Quality Details</summary>")
        lines.append("")
        lines.extend(quality_details)
        lines.append("")
        lines.append("</details>")

    if contrib_details:
        lines.append("<details><summary>👥 Contribution Details</summary>")
        lines.append("")
        lines.extend(contrib_details)
        lines.append("")
        lines.append("</details>")

    lines.append("")
    lines.append(f"---")
    lines.append(f"*PBL Guardian v1.0 | Team: {config.get('team_name', 'Unknown')} ({config.get('team_id', '?')})*")

    return "\n".join(lines)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="PBL Guardian Evaluation")
    parser.add_argument("--config", default=".pbl/config.json", help="Path to config file")
    parser.add_argument("--sha", default=None, help="Commit SHA")
    parser.add_argument("--timestamp", default=None, help="Commit timestamp (ISO 8601)")
    parser.add_argument("--author", default=None, help="Commit author")
    parser.add_argument("--source-dir", default="src", help="Source code directory")
    parser.add_argument("--reference-dir", default="references", help="Reference repos directory")
    parser.add_argument("--output", default=None, help="Output file for the report")
    args = parser.parse_args()

    result = run_evaluation(
        config_path=args.config,
        commit_sha=args.sha,
        commit_timestamp=args.timestamp,
        commit_author=args.author,
        github_token=os.environ.get("GITHUB_TOKEN"),
        source_dir=args.source_dir,
        reference_dir=args.reference_dir,
    )

    # Print the markdown report
    print(result["report"])

    # Save full JSON results
    if args.output:
        with open(args.output, "w") as f:
            json.dump(result["results"], f, indent=2, default=str)
        print(f"\n📝 Full results saved to {args.output}")

    # Also write report to a file for the GitHub Action to read
    report_file = os.environ.get("REPORT_FILE", "evaluation_report.md")
    with open(report_file, "w") as f:
        f.write(result["report"])
    print(f"📝 Markdown report saved to {report_file}")

    # Exit with appropriate code
    if not result["all_passed"]:
        print("\n❌ Some checks failed!")
        sys.exit(1)
    else:
        print("\n✅ All checks passed!")
        sys.exit(0)
