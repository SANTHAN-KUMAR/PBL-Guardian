"""
PBL Guardian — 5-Layer Plagiarism Checker

Layer 1: Copydetect — compare against local reference corpus (20+ repos)
Layer 2: JPlag — peer-to-peer comparison (runs separately via weekly workflow)
Layer 3: GitHub Code Search API — search all public GitHub for matching snippets
Layer 4: AI Fingerprint Heuristics — detect AI-generated code patterns
Layer 5: Commit Behavior Analysis — detect code dumps and suspicious patterns
"""

import ast
import json
import os
import re
import subprocess
import sys
from datetime import datetime, timedelta


# =============================================================================
# LAYER 1: Copydetect — Local Corpus Comparison
# =============================================================================

def layer1_copydetect(source_dir: str, reference_dir: str, threshold: float = 0.3) -> dict:
    """
    Compare student code against reference repos using copydetect.

    Args:
        source_dir: Student's source code directory
        reference_dir: Directory containing cloned reference repos
        threshold: Similarity threshold (0-1) to flag

    Returns:
        dict with L1 results
    """
    if not os.path.isdir(reference_dir) or not os.listdir(reference_dir):
        return {
            "score": 0,
            "flagged_files": [],
            "passed": True,
            "detail": "No reference corpus available",
        }

    try:
        # Run copydetect
        result = subprocess.run(
            [
                sys.executable, "-m", "copydetect",
                "-t", source_dir,
                "-r", reference_dir,
                "--extensions", "py",
                "--display-t", str(threshold),
                "--out", "/tmp/pbl_copydetect_report.html",
            ],
            capture_output=True,
            text=True,
            timeout=180,
        )

        # Parse output for similarity scores
        output = result.stdout + result.stderr
        max_similarity = 0
        flagged = []

        # Copydetect prints similarity info to stdout
        for line in output.split("\n"):
            if "%" in line and ("similar" in line.lower() or "match" in line.lower()):
                try:
                    pct = float(re.search(r"(\d+\.?\d*)%", line).group(1))
                    max_similarity = max(max_similarity, pct)
                    if pct >= threshold * 100:
                        flagged.append({"detail": line.strip(), "score": pct})
                except (AttributeError, ValueError):
                    pass

        return {
            "score": max_similarity,
            "flagged_files": flagged[:5],
            "passed": max_similarity < threshold * 100,
            "detail": f"{max_similarity:.0f}% max similarity vs corpus",
        }

    except FileNotFoundError:
        return {
            "score": 0,
            "flagged_files": [],
            "passed": True,
            "detail": "copydetect not installed — skipped",
        }
    except Exception as e:
        return {
            "score": 0,
            "flagged_files": [],
            "passed": True,
            "detail": f"L1 error: {str(e)[:100]}",
        }


# =============================================================================
# LAYER 3: GitHub Code Search API — Internet-Scale Search
# =============================================================================

def _extract_unique_functions(source_dir: str, max_functions: int = 5) -> list:
    """Extract the most unique function signatures from Python files."""
    functions = []

    for root, _, files in os.walk(source_dir):
        rel_root = os.path.relpath(root, source_dir)
        if any(part.startswith(".") or part == "__pycache__" for part in rel_root.split(os.sep) if part != "."):
            continue
        for fname in files:
            if not fname.endswith(".py"):
                continue
            filepath = os.path.join(root, fname)
            try:
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    source = f.read()

                tree = ast.parse(source)
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        # Get the function body lines
                        start_line = node.lineno - 1
                        end_line = node.end_lineno if hasattr(node, "end_lineno") else start_line + 10
                        lines = source.split("\n")[start_line:end_line]

                        # Skip very short functions (likely trivial)
                        body_lines = [l for l in lines if l.strip() and not l.strip().startswith("#")]
                        if len(body_lines) < 4:
                            continue

                        # Take a 3-5 line snippet for searching
                        snippet_lines = body_lines[1:6]  # Skip the def line, take implementation
                        snippet = " ".join(l.strip() for l in snippet_lines)

                        functions.append({
                            "name": node.name,
                            "file": os.path.relpath(filepath, source_dir),
                            "snippet": snippet[:200],  # Limit length
                            "length": len(body_lines),
                        })

            except (SyntaxError, UnicodeDecodeError):
                continue

    # Sort by length (longer = more unique) and return top N
    functions.sort(key=lambda x: x["length"], reverse=True)
    return functions[:max_functions]


def layer3_github_search(source_dir: str, github_token: str = None) -> dict:
    """
    Search GitHub's public code for matching snippets from student code.

    Args:
        source_dir: Student's source code directory
        github_token: GitHub personal access token (from secrets)

    Returns:
        dict with L3 results
    """
    if not github_token:
        return {
            "matches_found": 0,
            "searched_functions": 0,
            "flagged": [],
            "passed": True,
            "detail": "GitHub token not configured — skipped",
        }

    try:
        import requests
    except ImportError:
        return {
            "matches_found": 0,
            "searched_functions": 0,
            "flagged": [],
            "passed": True,
            "detail": "requests library not available — skipped",
        }

    functions = _extract_unique_functions(source_dir)
    if not functions:
        return {
            "matches_found": 0,
            "searched_functions": 0,
            "flagged": [],
            "passed": True,
            "detail": "No substantial functions found to search",
        }

    headers = {
        "Authorization": f"token {github_token}",
        "Accept": "application/vnd.github.v3.text-match+json",
    }

    matches_found = 0
    flagged = []

    for func in functions[:3]:  # Search top 3 to stay within rate limits
        # Create a search query from the function's unique code
        # Use key identifiers from the snippet
        query_parts = func["snippet"].split()
        # Take meaningful tokens (skip common Python keywords)
        skip_tokens = {"self", "return", "if", "else", "for", "in", "def", "class",
                        "import", "from", "not", "and", "or", "True", "False", "None",
                        "=", "==", "!=", "(", ")", "[", "]", "{", "}", ":", ",", "."}
        meaningful = [t for t in query_parts if t not in skip_tokens and len(t) > 2]
        if len(meaningful) < 3:
            continue

        search_query = " ".join(meaningful[:8]) + " language:python"

        try:
            resp = requests.get(
                "https://api.github.com/search/code",
                params={"q": search_query},
                headers=headers,
                timeout=15,
            )

            if resp.status_code == 200:
                data = resp.json()
                total_count = data.get("total_count", 0)

                if total_count > 0:
                    matches_found += 1
                    top_match = data.get("items", [{}])[0] if data.get("items") else {}
                    flagged.append({
                        "function": func["name"],
                        "file": func["file"],
                        "github_matches": total_count,
                        "top_match_repo": top_match.get("repository", {}).get("full_name", "unknown"),
                        "top_match_file": top_match.get("path", "unknown"),
                    })
            elif resp.status_code == 403:
                # Rate limited
                break

        except Exception:
            continue

    total_searched = min(len(functions), 3)
    # Only flag if majority of searched functions have matches (reduces false positives)
    passed = matches_found < max(total_searched // 2 + 1, 2)

    return {
        "matches_found": matches_found,
        "searched_functions": total_searched,
        "flagged": flagged,
        "passed": passed,
        "detail": f"{matches_found}/{total_searched} functions matched on GitHub"
               + (" — likely copied" if not passed else ""),
    }


# =============================================================================
# LAYER 4: AI Fingerprint Heuristics
# =============================================================================

def layer4_ai_detection(source_dir: str) -> dict:
    """
    Detect patterns commonly found in AI-generated code.

    Heuristics:
    - Comment-to-code ratio (AI writes too many comments)
    - Docstring completeness (AI documents everything)
    - Variable naming uniformity (AI uses long descriptive names)
    - Error handling density (AI wraps everything in try/except)
    - Import style (AI uses textbook ordering)

    Returns:
        dict with AI detection results (score 0-1, higher = more likely AI)
    """
    scores = []
    flags = []

    total_code_lines = 0
    total_comment_lines = 0
    total_docstring_lines = 0
    total_functions = 0
    functions_with_docstrings = 0
    variable_names = []
    try_except_count = 0
    total_blocks = 0

    py_files = []
    for root, _, files in os.walk(source_dir):
        rel_root = os.path.relpath(root, source_dir)
        if any(part.startswith(".") or part == "__pycache__" for part in rel_root.split(os.sep) if part != "."):
            continue
        for f in files:
            if f.endswith(".py"):
                py_files.append(os.path.join(root, f))

    if not py_files:
        return {
            "ai_score": 0.0,
            "flags": [],
            "passed": True,
            "metrics": {},
            "status": "⚠️ No Python files to analyze",
            "status_emoji": "⚠️",
            "detail": "No Python files to analyze",
        }

    for filepath in py_files:
        try:
            with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                source = f.read()
                lines = source.split("\n")

            # Count comments and code lines
            for line in lines:
                stripped = line.strip()
                if not stripped:
                    continue
                if stripped.startswith("#"):
                    total_comment_lines += 1
                else:
                    total_code_lines += 1

            # Parse AST for deeper analysis
            try:
                tree = ast.parse(source)
            except SyntaxError:
                continue

            for node in ast.walk(tree):
                # Count functions and docstrings
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    total_functions += 1
                    # Check for docstring
                    if (node.body and isinstance(node.body[0], ast.Expr)
                            and isinstance(node.body[0].value, (ast.Constant, ast.Str))):
                        functions_with_docstrings += 1
                        # Count docstring lines
                        if isinstance(node.body[0].value, ast.Constant):
                            ds = str(node.body[0].value.value)
                        else:
                            ds = node.body[0].value.s
                        total_docstring_lines += len(ds.split("\n"))

                # Count try/except blocks
                if isinstance(node, ast.Try):
                    try_except_count += 1
                    total_blocks += 1
                elif isinstance(node, (ast.If, ast.For, ast.While)):
                    total_blocks += 1

                # Collect variable names
                if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                    variable_names.append(node.id)

        except Exception:
            continue

    # HEURISTIC 1: Comment-to-code ratio
    # AI code typically has >35% comment ratio
    if total_code_lines > 0:
        comment_ratio = total_comment_lines / (total_code_lines + total_comment_lines)
        if comment_ratio > 0.40:
            scores.append(0.8)
            flags.append(f"Very high comment ratio: {comment_ratio:.0%} (AI typical: >40%)")
        elif comment_ratio > 0.30:
            scores.append(0.4)
            flags.append(f"High comment ratio: {comment_ratio:.0%}")
        else:
            scores.append(0.1)

    # HEURISTIC 2: Docstring completeness
    # AI almost always adds docstrings to every function
    if total_functions > 2:
        docstring_ratio = functions_with_docstrings / total_functions
        if docstring_ratio > 0.90:
            scores.append(0.7)
            flags.append(f"Near-perfect docstring coverage: {docstring_ratio:.0%}")
        elif docstring_ratio > 0.70:
            scores.append(0.3)
        else:
            scores.append(0.1)

    # HEURISTIC 3: Variable naming uniformity
    # AI uses long, descriptive variable names consistently
    if variable_names:
        avg_name_length = sum(len(n) for n in variable_names) / len(variable_names)
        long_name_ratio = sum(1 for n in variable_names if len(n) > 15) / len(variable_names)
        snake_case_ratio = sum(1 for n in variable_names if "_" in n) / len(variable_names)

        # AI tends to have very uniform naming
        if avg_name_length > 12 and long_name_ratio > 0.3:
            scores.append(0.6)
            flags.append(f"Unusually long variable names: avg {avg_name_length:.1f} chars, "
                        f"{long_name_ratio:.0%} are >15 chars")
        else:
            scores.append(0.1)

    # HEURISTIC 4: Error handling density
    # AI wraps everything in try/except
    if total_blocks > 3:
        error_ratio = try_except_count / total_blocks
        if error_ratio > 0.5:
            scores.append(0.6)
            flags.append(f"High try/except density: {error_ratio:.0%} of blocks")
        else:
            scores.append(0.1)

    # Calculate final AI score (weighted average)
    ai_score = round(sum(scores) / len(scores), 2) if scores else 0.0

    # Determine status
    if ai_score >= 0.6:
        passed = False
        status_label = "Likely AI"
        status_emoji = "🚨"
    elif ai_score >= 0.4:
        passed = True
        status_label = "Suspicious"
        status_emoji = "⚠️"
    else:
        passed = True
        status_label = "Human"
        status_emoji = "✅"

    return {
        "ai_score": ai_score,
        "flags": flags,
        "passed": passed,
        "metrics": {
            "comment_ratio": round(total_comment_lines / max(total_code_lines + total_comment_lines, 1), 2),
            "docstring_ratio": round(functions_with_docstrings / max(total_functions, 1), 2),
            "avg_var_name_length": round(sum(len(n) for n in variable_names) / max(len(variable_names), 1), 1),
            "try_except_ratio": round(try_except_count / max(total_blocks, 1), 2),
        },
        "status": f"{status_emoji} AI Score: {ai_score} ({status_label})",
        "status_emoji": status_emoji,
        "detail": f"AI Score: {ai_score} ({status_label})"
                  + (f" — {', '.join(flags[:2])}" if flags else ""),
    }


# =============================================================================
# LAYER 5: Commit Behavior Analysis
# =============================================================================

def layer5_commit_patterns(max_dump_lines: int = 200) -> dict:
    """
    Analyze git commit patterns for suspicious behavior.

    Detects:
    - Code dumps (large single commits)
    - Last-minute rush (most code in final 48 hours)
    - Inconsistent skill levels
    - Copy-paste velocity

    Returns:
        dict with commit pattern analysis results
    """
    try:
        # Get commit history with stats
        # Use ASCII Unit Separator (\x1f) instead of pipe — commit messages can contain pipes
        SEP = "\x1f"
        result = subprocess.run(
            ["git", "log", "--all", "--no-merges",
             f"--format=%H{SEP}%aN{SEP}%aI{SEP}%s", "--numstat"],
            capture_output=True,
            text=True,
            timeout=30,
        )
    except Exception:
        return {
            "passed": True,
            "flags": [],
            "detail": "Git log unavailable",
            "status": "⚠️ Unavailable",
            "status_emoji": "⚠️",
        }

    commits = []
    current_commit = None
    SEP = "\x1f"

    for line in result.stdout.strip().split("\n"):
        line = line.strip()
        if not line:
            continue

        if SEP in line:
            # New commit header (unit separator is never in user content)
            parts = line.split(SEP, 3)
            if len(parts) == 4:
                if current_commit:
                    commits.append(current_commit)
                current_commit = {
                    "sha": parts[0],
                    "author": parts[1],
                    "date": parts[2],
                    "message": parts[3],
                    "additions": 0,
                    "deletions": 0,
                }
        elif current_commit and "\t" in line:
            tab_parts = line.split("\t")
            if len(tab_parts) == 3:
                try:
                    added = int(tab_parts[0]) if tab_parts[0] != "-" else 0
                    deleted = int(tab_parts[1]) if tab_parts[1] != "-" else 0
                    current_commit["additions"] += added
                    current_commit["deletions"] += deleted
                except ValueError:
                    pass

    if current_commit:
        commits.append(current_commit)

    if not commits:
        return {
            "passed": True,
            "flags": [],
            "detail": "No commits to analyze",
            "status": "⚠️ No commits",
            "status_emoji": "⚠️",
        }

    flags = []

    # CHECK 1: Code dumps — any single commit with >200 lines added
    for commit in commits:
        if commit["additions"] > max_dump_lines:
            flags.append(
                f"🚨 Code dump: {commit['author']} added {commit['additions']} lines "
                f"in one commit ({commit['sha'][:7]})"
            )

    # CHECK 2: Last-minute rush — >60% of code in final 25% of project timeline
    commit_dates = []
    for c in commits:
        try:
            dt = datetime.fromisoformat(c["date"])
            commit_dates.append((dt, c["additions"]))
        except (ValueError, TypeError):
            pass

    if len(commit_dates) > 3:
        commit_dates.sort(key=lambda x: x[0])
        total_span = (commit_dates[-1][0] - commit_dates[0][0]).total_seconds()
        if total_span > 0:
            cutoff_time = commit_dates[0][0] + timedelta(seconds=total_span * 0.75)
            total_additions = sum(a for _, a in commit_dates)
            late_additions = sum(a for dt, a in commit_dates if dt >= cutoff_time)

            if total_additions > 0:
                late_ratio = late_additions / total_additions
                if late_ratio > 0.60:
                    flags.append(
                        f"⚠️ Rush detected: {late_ratio:.0%} of code added in final 25% of timeline"
                    )

    # CHECK 3: Commit frequency — healthy projects have gradual development
    if len(commits) > 0:
        avg_additions = sum(c["additions"] for c in commits) / len(commits)
        if avg_additions > 150 and len(commits) < 5:
            flags.append(
                f"⚠️ Low commit frequency: {len(commits)} commits with avg {avg_additions:.0f} lines each"
            )

    # Determine overall status
    critical_flags = [f for f in flags if "🚨" in f]
    warning_flags = [f for f in flags if "⚠️" in f]

    if critical_flags:
        passed = False
        status_emoji = "🚨"
        label = "Suspicious"
    elif warning_flags:
        passed = True
        status_emoji = "⚠️"
        label = "Needs Review"
    else:
        passed = True
        status_emoji = "✅"
        label = "Healthy"

    return {
        "passed": passed,
        "flags": flags,
        "total_commits": len(commits),
        "avg_additions_per_commit": round(sum(c["additions"] for c in commits) / max(len(commits), 1), 1),
        "status": f"{status_emoji} {label}",
        "status_emoji": status_emoji,
        "detail": f"{label} — {len(commits)} commits, "
                  f"avg {sum(c['additions'] for c in commits) / max(len(commits), 1):.0f} lines/commit"
                  + (f" | {len(flags)} flag(s)" if flags else ""),
    }


# =============================================================================
# MAIN AGGREGATOR — Runs all 5 layers
# =============================================================================

def check_plagiarism(
    source_dir: str = "src",
    reference_dir: str = "references",
    config: dict = None,
    github_token: str = None,
) -> dict:
    """
    Run the complete 5-layer plagiarism defense.

    Args:
        source_dir: Student's source code directory
        reference_dir: Directory with cloned reference repos
        config: The .pbl/config.json contents
        github_token: GitHub token for Code Search API

    Returns:
        dict with aggregated plagiarism results from all 5 layers
    """
    config = config or {}
    threshold = config.get("plagiarism_threshold", 30) / 100

    results = {}

    # Layer 1: Copydetect vs reference corpus
    results["L1_copydetect"] = layer1_copydetect(source_dir, reference_dir, threshold)

    # Layer 2: JPlag (runs via separate weekly workflow — just note it here)
    results["L2_jplag"] = {
        "detail": "Runs via weekly scheduled workflow",
        "passed": True,
    }

    # Layer 3: GitHub Code Search
    results["L3_github_search"] = layer3_github_search(source_dir, github_token)

    # Layer 4: AI Detection Heuristics
    results["L4_ai_detection"] = layer4_ai_detection(source_dir)

    # Layer 5: Commit Behavior Analysis
    results["L5_commit_patterns"] = layer5_commit_patterns()

    # Aggregate results
    all_passed = all(r.get("passed", True) for r in results.values())
    critical_layers = [k for k, v in results.items() if not v.get("passed", True)]

    if all_passed:
        overall_status = "✅ All layers clear"
        overall_emoji = "✅"
    else:
        overall_status = f"🚨 Flagged by: {', '.join(critical_layers)}"
        overall_emoji = "🚨"

    return {
        "passed": all_passed,
        "layers": results,
        "critical_layers": critical_layers,
        "status": overall_status,
        "status_emoji": overall_emoji,
        "detail": overall_status,
    }


if __name__ == "__main__":
    result = check_plagiarism(
        source_dir="src",
        reference_dir="references",
        github_token=os.environ.get("GITHUB_TOKEN"),
    )
    print(json.dumps(result, indent=2, default=str))
