"""
PBL Guardian — Code Quality Checker
Runs Pylint/Flake8 on student code and reports quality score.
"""

import json
import os
import subprocess
import sys


def check_quality(source_dir: str, language: str = "python", min_score: float = 7.0) -> dict:
    """
    Run code quality analysis on the source directory.

    Args:
        source_dir: Path to the student's source code directory
        language: Programming language (currently supports 'python')
        min_score: Minimum quality score to pass (0-10)

    Returns:
        dict with quality evaluation results
    """
    if language.lower() != "python":
        return {
            "passed": True,
            "score": None,
            "issues": [],
            "detail": f"Quality check not configured for {language}",
            "status": "⚠️ Skipped",
            "status_emoji": "⚠️",
        }

    # Find all Python files
    py_files = []
    for root, _, files in os.walk(source_dir):
        # Skip hidden directories and __pycache__
        if any(part.startswith(".") or part == "__pycache__" for part in root.split(os.sep)):
            continue
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))

    if not py_files:
        return {
            "passed": True,
            "score": None,
            "issues": [],
            "detail": "No Python files found in src/",
            "status": "⚠️ No Code",
            "status_emoji": "⚠️",
        }

    # Run Pylint with JSON output
    try:
        result = subprocess.run(
            [
                sys.executable, "-m", "pylint",
                "--output-format=json",
                "--disable=C0114,C0115,C0116",  # Disable missing docstring warnings
                "--max-line-length=120",
                *py_files,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )

        # Pylint returns non-zero even for warnings, so we parse regardless
        pylint_output = result.stdout.strip()
        if pylint_output:
            issues_raw = json.loads(pylint_output)
        else:
            issues_raw = []

    except (subprocess.TimeoutExpired, FileNotFoundError, json.JSONDecodeError) as e:
        return {
            "passed": False,
            "score": 0,
            "issues": [{"message": f"Pylint failed to run: {str(e)}"}],
            "detail": "Pylint execution error",
            "status": "❌ Error",
            "status_emoji": "❌",
        }

    # Also run Pylint for the score
    try:
        score_result = subprocess.run(
            [
                sys.executable, "-m", "pylint",
                "--disable=C0114,C0115,C0116",
                "--max-line-length=120",
                "--score=y",
                *py_files,
            ],
            capture_output=True,
            text=True,
            timeout=120,
        )
        # Extract score from output like "Your code has been rated at 8.50/10"
        score = 0.0
        for line in score_result.stdout.split("\n"):
            if "rated at" in line:
                try:
                    score = float(line.split("rated at")[1].split("/")[0].strip())
                except (ValueError, IndexError):
                    score = 0.0
                break
    except Exception:
        score = 0.0

    # Extract top issues (limit to 5)
    top_issues = []
    for issue in issues_raw[:5]:
        top_issues.append({
            "file": os.path.basename(issue.get("path", "unknown")),
            "line": issue.get("line", 0),
            "type": issue.get("type", "unknown"),
            "message": issue.get("message", ""),
            "symbol": issue.get("symbol", ""),
        })

    passed = score >= min_score

    if passed:
        status = f"✅ Pylint: {score:.1f}/10"
        status_emoji = "✅"
    else:
        status = f"❌ Pylint: {score:.1f}/10 (min: {min_score})"
        status_emoji = "❌"

    return {
        "passed": passed,
        "score": round(score, 2),
        "issues": top_issues,
        "total_issues": len(issues_raw),
        "files_checked": len(py_files),
        "detail": f"Pylint: {score:.1f}/10 ({len(issues_raw)} issues in {len(py_files)} files)",
        "status": status,
        "status_emoji": status_emoji,
    }


if __name__ == "__main__":
    import sys as _sys
    src = _sys.argv[1] if len(_sys.argv) > 1 else "./src"
    result = check_quality(src)
    print(json.dumps(result, indent=2))
