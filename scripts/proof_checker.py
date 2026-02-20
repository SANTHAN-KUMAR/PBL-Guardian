"""
PBL Guardian — Proof of Progress Checker
Validates that students submitted screenshots or progress logs with their commits.
"""

import json
import os
import re
import subprocess


IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}
DOC_EXTENSIONS = {".md", ".txt", ".pdf", ".doc", ".docx"}


def check_proofs(proof_dir: str = "proofs", commit_sha: str = "HEAD") -> dict:
    """
    Check if the student submitted proof of progress in this commit.

    Args:
        proof_dir: Directory where proofs should be stored
        commit_sha: The commit SHA to check for new proofs

    Returns:
        dict with proof evaluation results
    """
    # Get files changed in this commit
    try:
        result = subprocess.run(
            ["git", "diff-tree", "--no-commit-id", "--name-only", "-r", commit_sha],
            capture_output=True,
            text=True,
            timeout=30,
        )
        changed_files = [f.strip() for f in result.stdout.strip().split("\n") if f.strip()]
    except Exception:
        changed_files = []

    # Filter for files in the proofs directory
    proof_files_in_commit = [
        f for f in changed_files
        if f.startswith(proof_dir.rstrip("/") + "/")
    ]

    # Also check what's in the proofs directory overall
    all_proofs = []
    if os.path.isdir(proof_dir):
        for root, _, files in os.walk(proof_dir):
            for f in files:
                if f == ".gitkeep":
                    continue
                filepath = os.path.join(root, f)
                ext = os.path.splitext(f)[1].lower()
                all_proofs.append({
                    "file": os.path.relpath(filepath, proof_dir),
                    "type": "screenshot" if ext in IMAGE_EXTENSIONS else "document" if ext in DOC_EXTENSIONS else "other",
                    "extension": ext,
                })

    # Categorize new proofs in this commit
    new_screenshots = []
    new_documents = []
    new_other = []

    for f in proof_files_in_commit:
        ext = os.path.splitext(f)[1].lower()
        basename = os.path.basename(f)
        if basename == ".gitkeep":
            continue
        if ext in IMAGE_EXTENSIONS:
            new_screenshots.append(f)
        elif ext in DOC_EXTENSIONS:
            new_documents.append(f)
        else:
            new_other.append(f)

    has_screenshots = len(new_screenshots) > 0
    has_progress_log = len(new_documents) > 0
    has_any_proof = has_screenshots or has_progress_log or len(new_other) > 0

    # Check if source code was also changed (proofs should accompany code changes)
    code_changed = any(
        not f.startswith(proof_dir.rstrip("/") + "/")
        and not f.startswith(".pbl/")
        and not f.startswith(".github/")
        and not f.startswith("scripts/")
        for f in changed_files
    )

    # Determine pass/fail
    # If code was changed but no proofs were added, flag it
    if code_changed and not has_any_proof:
        passed = False
        status = "❌ No proofs submitted with code changes"
        status_emoji = "❌"
    elif not code_changed:
        passed = True
        status = "⚠️ No code changes (proof not required)"
        status_emoji = "⚠️"
    else:
        passed = True
        parts = []
        if has_screenshots:
            parts.append(f"{len(new_screenshots)} screenshot{'s' if len(new_screenshots) > 1 else ''}")
        if has_progress_log:
            parts.append(f"{len(new_documents)} progress log{'s' if len(new_documents) > 1 else ''}")
        if new_other:
            parts.append(f"{len(new_other)} other file{'s' if len(new_other) > 1 else ''}")
        status = f"✅ {', '.join(parts)}"
        status_emoji = "✅"

    return {
        "passed": passed,
        "has_screenshots": has_screenshots,
        "has_progress_log": has_progress_log,
        "new_proofs": proof_files_in_commit,
        "new_screenshots_count": len(new_screenshots),
        "new_documents_count": len(new_documents),
        "total_proofs_in_repo": len(all_proofs),
        "code_changed": code_changed,
        "status": status,
        "status_emoji": status_emoji,
        "detail": re.sub(r"^[✅❌⚠️🚨\s]+", "", status),
    }


if __name__ == "__main__":
    import sys
    sha = sys.argv[1] if len(sys.argv) > 1 else "HEAD"
    result = check_proofs(commit_sha=sha)
    print(json.dumps(result, indent=2))
