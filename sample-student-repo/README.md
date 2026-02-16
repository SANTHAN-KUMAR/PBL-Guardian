# Student Project — [Your Project Name]

> This project is evaluated by **PBL Guardian** 🤖 — an automated evaluation system that checks your code on every push.

## 📁 Project Structure

```
your-repo/
├── .github/workflows/
│   └── evaluate.yml          ← Triggers PBL Guardian (DO NOT MODIFY)
├── .pbl/
│   └── config.json           ← Your team configuration (DO NOT MODIFY)
├── src/                      ← PUT YOUR PROJECT CODE HERE
│   └── main.py
├── proofs/                   ← PUT YOUR PROGRESS SCREENSHOTS HERE
│   ├── day1_progress.png
│   └── day1_notes.md
└── README.md                 ← This file
```

## 🤖 How Evaluation Works

Every time you push code, a bot will automatically comment on your commit with an evaluation report. The bot checks:

| Check | What it evaluates | How to pass |
|---|---|---|
| ⏰ **Timing** | Is your commit within the milestone deadline? | Push code before deadline + grace period |
| 📊 **Code Quality** | Does your code follow best practices? | Keep Pylint score ≥ 7.0/10 |
| 📸 **Proofs** | Did you upload progress screenshots? | Add screenshots to `proofs/` folder |
| 👥 **Contribution** | Is the team contributing equally? | Everyone should have ≥ 10% of commits |
| 🔍 **Plagiarism** | Is the code original? | Write your own code, don't copy-paste |

## ⚠️ Important Rules

1. **Put all your code in the `src/` directory** — only files here are evaluated
2. **Upload screenshots to `proofs/`** with each commit that changes code
3. **Commit regularly** — don't dump everything at the end
4. **Do NOT modify** `.github/workflows/` or `.pbl/config.json`
5. **Write your own code** — AI-generated and copied code will be flagged

## 📅 Milestones

Check your `.pbl/config.json` for your team's specific deadlines.
