# 🤖 PBL Guardian

An automated, bias-free evaluation system for Project-Based Learning (PBL) that uses GitHub Actions to continuously assess student projects on every push.

## What It Does

Every time a student pushes code, PBL Guardian automatically evaluates their commit across **5 dimensions** and posts a detailed report as a commit comment:

| Check | What's Evaluated |
|---|---|
| ⏰ **Timing** | Commit vs. milestone deadlines + class day detection |
| 📊 **Code Quality** | Pylint score (0-10) + top issues |
| 📸 **Proofs** | Screenshots & progress logs in `proofs/` |
| 👥 **Contribution** | Gini coefficient for team equity |
| 🔍 **Plagiarism** | 5-layer defense (corpus, peer, GitHub search, AI detection, commit forensics) |

### 5-Layer Plagiarism Defense

| Layer | Tool | What It Catches |
|---|---|---|
| **L1** | Copydetect | Copies from your existing repos/past projects |
| **L2** | JPlag | Student-to-student copying (weekly scan) |
| **L3** | GitHub Code Search API | Code from any public GitHub repo |
| **L4** | Custom Heuristics | AI-generated code (ChatGPT, Copilot, Claude) |
| **L5** | Git Forensics | Code dumps, midnight rush, skill inconsistencies |

## Architecture

```
┌─────────────────────────────────────────────────────┐
│  YOUR ACCOUNT: pbl-guardian repo                    │
│  ├── scripts/          (all evaluation logic)       │
│  ├── .github/workflows/                             │
│  │   └── weekly_plagiarism.yml (scheduled JPlag)    │
│  └── sample-student-repo/    (template to copy)     │
└────────────────────┬────────────────────────────────┘
                     │  student workflow downloads
                     │  scripts via curl on each push
    ┌────────────────┼────────────────────┐
    ▼                ▼                    ▼
┌──────────┐  ┌──────────┐        ┌──────────┐
│ Student  │  │ Student  │  ...   │ Student  │
│ Repo 1   │  │ Repo 2   │        │ Repo 8   │
│          │  │          │        │          │
│ 2 files: │  │ 2 files: │        │ 2 files: │
│ workflow │  │ workflow │        │ workflow │
│ config   │  │ config   │        │ config   │
└──────────┘  └──────────┘        └──────────┘
```

Each student repo only needs **2 files**:
1. `.github/workflows/evaluate.yml` — downloads and runs the latest PBL Guardian scripts
2. `.pbl/config.json` — team-specific configuration

> **How it works:** The student workflow uses `curl` to download the latest scripts from your central PBL-Guardian repo on every push. This means any bug fixes or improvements you make to the central repo **automatically apply** to all student repos on their next push — no manual updates needed.

## Quick Setup

### Step 1: Push this repo to your GitHub account

```bash
cd pbl-guardian
git init
git add .
git commit -m "Initial PBL Guardian setup"
git remote add origin https://github.com/YOUR-USERNAME/pbl-guardian.git
git push -u origin main
```

### Step 2: Set up each student repo

Copy the contents of `sample-student-repo/` into each student's repo:

```bash
# In a student's repo:
cp -r /path/to/pbl-guardian/sample-student-repo/.github .
cp -r /path/to/pbl-guardian/sample-student-repo/.pbl .
cp -r /path/to/pbl-guardian/sample-student-repo/proofs .
mkdir -p src
```

### Step 3: Edit the student workflow

In each student repo's `.github/workflows/evaluate.yml`, replace `YOUR-GITHUB-USERNAME` with your actual GitHub username (the `PBL_GUARDIAN_REPO` env variable).

### Step 4: Edit the team config

In each student repo's `.pbl/config.json`:
- Set the `team_id` and `team_name`
- Set the correct `class_days`
- Update `milestones` with actual deadlines
- Add your `reference_repos` (your 20+ existing repos for plagiarism comparison)

### Step 5 (Optional): Set up weekly peer check

In the `pbl-guardian` repo settings, add a repository secret:
- **Name**: `STUDENT_REPOS`
- **Value**: `["org/team1-project", "org/team2-project", ...]`

This enables the weekly JPlag peer-to-peer comparison.

### Step 6 (Optional): Set up GitHub Code Search (L3)

> **Note:** The default `GITHUB_TOKEN` in GitHub Actions has limited code search abilities. For Layer 3 (GitHub Code Search) to work reliably, create a **Personal Access Token** with `read:packages` scope and add it as a secret named `GITHUB_TOKEN_SEARCH` in each student repo.

## Running & Testing Locally

### Prerequisites

```bash
# Python 3.11+
python --version

# Install dependencies
pip install -r scripts/requirements.txt
pip install pytest
```

### Run the evaluation manually

You can run the full evaluation pipeline locally against any project directory:

```bash
# From inside a student repo (or this repo for testing):
python scripts/evaluate.py \
  --config .pbl/config.json \
  --sha HEAD \
  --timestamp "$(git show -s --format=%aI HEAD)" \
  --author "$(git log -1 --format=%aN)" \
  --source-dir src \
  --reference-dir references \
  --output results.json
```

### Run individual checkers

```bash
# Timing check
python scripts/timing_checker.py

# Code quality check
python scripts/quality_checker.py src/

# Proof check
python scripts/proof_checker.py HEAD

# Contribution check
python scripts/contribution_checker.py

# Plagiarism check (all 5 layers)
python scripts/plagiarism_checker.py
```

### Run unit tests

```bash
# Run all tests
python -m pytest tests/ -v

# Run a specific test class
python -m pytest tests/test_checkers.py::TestTimingChecker -v

# Run with coverage
python -m pytest tests/ -v --cov=scripts
```

### Test with the sample student repo

```bash
# Create a test directory
mkdir /tmp/test-student && cd /tmp/test-student
git init

# Copy sample template
cp -r /path/to/pbl-guardian/sample-student-repo/* .
cp -r /path/to/pbl-guardian/sample-student-repo/.* .

# Add some sample code
echo 'print("hello world")' > src/main.py

# Commit and test
git add . && git commit -m "initial commit"

# Run evaluation
python /path/to/pbl-guardian/scripts/evaluate.py \
  --config .pbl/config.json \
  --sha HEAD \
  --timestamp "$(git show -s --format=%aI HEAD)" \
  --author "$(git log -1 --format=%aN)" \
  --source-dir src
```

## Configuration Reference

```json
{
  "team_id": "Team-1",
  "team_name": "ML Mavericks",
  "class_days": ["Monday", "Saturday"],
  "timezone": "Asia/Kolkata",
  "grace_period_hours": 2,
  "milestones": [
    {"phase": "Phase 1", "deadline": "2026-03-01"},
    {"phase": "Phase 2", "deadline": "2026-03-15"}
  ],
  "language": "python",
  "proof_directory": "proofs/",
  "min_quality_score": 7.0,
  "plagiarism_threshold": 30,
  "reference_repos": ["user/repo1", "user/repo2"]
}
```

| Field | Description |
|---|---|
| `team_id` | Unique team identifier |
| `class_days` | Days of the week when the team has classes |
| `timezone` | Team's timezone for deadline calculations |
| `grace_period_hours` | Hours of grace after a milestone deadline |
| `milestones` | List of phase deadlines |
| `language` | Programming language (affects linter choice) |
| `min_quality_score` | Minimum Pylint score to pass (0-10) |
| `plagiarism_threshold` | Max similarity % before flagging |
| `reference_repos` | Your repos to check plagiarism against |

## Bot Comment Example

When a student pushes code, they'll see a comment like this on their commit:

```
## 🤖 PBL Guardian — Evaluation Report

| Metric | Result | Status |
|---|---|---|
| ⏰ Timing | Phase 2 — 3 days before deadline | ✅ |
| 📊 Code Quality | Pylint: 8.2/10 (4 issues in 3 files) | ✅ |
| 📸 Proofs | 2 screenshots, 1 progress log | ✅ |
| 👥 Contribution | Gini: 0.15 (Balanced) | ✅ |
| 🔍 Plagiarism (L1) | 8% max similarity vs corpus | ✅ |
| 🔍 Plagiarism (L3) | 0/3 functions matched on GitHub | ✅ |
| 🤖 AI Detection (L4) | AI Score: 0.12 (Human) | ✅ |
| 📈 Commit Patterns (L5) | Healthy — 12 commits | ✅ |
```
