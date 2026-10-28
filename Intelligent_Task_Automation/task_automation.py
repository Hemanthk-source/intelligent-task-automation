#!/usr/bin/env python3
"""Intelligent Task Automation - a simple base project.

Features
  * Auto-categorises tasks from their text (keyword-based NLP)
  * Extracts due dates from natural phrases ("tomorrow", "in 3 days", 2026-11-05)
  * Scores priority from urgency keywords + deadline proximity
  * Recurring tasks (daily / weekly / monthly) re-schedule themselves
  * Runs automations: organise a folder, back up a folder

Usage
  python task_automation.py add "Pay electricity bill urgent tomorrow"
  python task_automation.py add "Weekly backup" --every weekly --action "backup|./docs|./backups"
  python task_automation.py add "Clean downloads in 2 days" --action "organize|./Downloads"
  python task_automation.py list
  python task_automation.py done 1
  python task_automation.py run          # executes automations that are due
  python task_automation.py organize ./Downloads
"""
import argparse
import datetime as dt
import json
import re
import shutil
from pathlib import Path

DB = Path("tasks.json")

CATEGORIES = {
    "work": ["meeting", "report", "client", "project", "email", "deadline", "presentation"],
    "finance": ["bill", "pay", "invoice", "tax", "rent", "budget", "bank"],
    "health": ["doctor", "gym", "medicine", "workout", "appointment", "checkup"],
    "study": ["exam", "assignment", "homework", "read", "course", "revise", "study"],
    "home": ["clean", "groceries", "repair", "laundry", "cook", "shopping"],
    "system": ["backup", "organize", "organise", "update", "cleanup", "download"],
}
URGENT_WORDS = {"urgent", "asap", "important", "critical", "immediately", "today"}
FILE_TYPES = {
    "Images": {".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg"},
    "Documents": {".pdf", ".doc", ".docx", ".txt", ".xlsx", ".pptx", ".csv"},
    "Videos": {".mp4", ".mkv", ".mov", ".avi"},
    "Audio": {".mp3", ".wav", ".flac"},
    "Archives": {".zip", ".rar", ".7z", ".tar", ".gz"},
    "Code": {".py", ".js", ".html", ".css", ".java", ".cpp"},
}


# ---------- storage ----------
def load():
    return json.loads(DB.read_text()) if DB.exists() else []


def save(tasks):
    DB.write_text(json.dumps(tasks, indent=2))


# ---------- "intelligence" ----------
def classify(text):
    words = set(re.findall(r"[a-z]+", text.lower()))
    scores = {c: len(words & set(kw)) for c, kw in CATEGORIES.items()}
    best = max(scores, key=scores.get)
    return best if scores[best] else "general"


def parse_due(text):
    today, t = dt.date.today(), text.lower()
    if m := re.search(r"\d{4}-\d{2}-\d{2}", t):
        return dt.date.fromisoformat(m.group())
    if m := re.search(r"in (\d+) days?", t):
        return today + dt.timedelta(days=int(m.group(1)))
    if "tomorrow" in t:
        return today + dt.timedelta(days=1)
    if "today" in t:
        return today
    if "next week" in t:
        return today + dt.timedelta(days=7)
    return None


def priority_score(task):
    score = 3 * len(URGENT_WORDS & set(re.findall(r"[a-z]+", task["title"].lower())))
    if task["due"]:
        days = (dt.date.fromisoformat(task["due"]) - dt.date.today()).days
        score += 10 if days < 0 else 8 if days <= 1 else 5 if days <= 3 else 2 if days <= 7 else 0
    return score


def level(score):
    return "HIGH" if score >= 8 else "MEDIUM" if score >= 4 else "LOW"


# ---------- automations ----------
def organize(folder):
    folder, moved = Path(folder), 0
    if not folder.is_dir():
        print(f"  ! Folder not found: {folder}")
        return
    for f in folder.iterdir():
        if f.is_file():
            kind = next((k for k, ext in FILE_TYPES.items() if f.suffix.lower() in ext), "Others")
            dest = folder / kind
            dest.mkdir(exist_ok=True)
            shutil.move(str(f), str(dest / f.name))
            moved += 1
    print(f"  Organised {moved} file(s) in {folder}")


def backup(src, dst):
    src = Path(src)
    if not src.is_dir():
        print(f"  ! Source not found: {src}")
        return
    target = Path(dst) / f"{src.name}_{dt.datetime.now():%Y%m%d_%H%M%S}"
    shutil.copytree(src, target)
    print(f"  Backup created: {target}")


def run_action(action):
    kind, *args = action.split("|")
    if kind == "organize" and args:
        organize(args[0])
    elif kind == "backup" and len(args) == 2:
        backup(*args)
    else:
        print(f"  ! Unknown action: {action}")


# ---------- commands ----------
def next_due(due, every):
    base = dt.date.fromisoformat(due) if due else dt.date.today()
    step = {"daily": 1, "weekly": 7, "monthly": 30}[every]
    return (base + dt.timedelta(days=step)).isoformat()


def cmd_add(a):
    tasks = load()
    due = parse_due(a.title)
    if a.every and not due:
        due = dt.date.today()
    task = {
        "id": max((t["id"] for t in tasks), default=0) + 1,
        "title": a.title,
        "category": classify(a.title),
        "due": due.isoformat() if due else None,
        "every": a.every,
        "action": a.action,
        "done": False,
    }
    tasks.append(task)
    save(tasks)
    print(f"Added #{task['id']} [{task['category']}] due={task['due']} "
          f"priority={level(priority_score(task))}")


def cmd_list(_):
    pending = [t for t in load() if not t["done"]]
    if not pending:
        return print("No pending tasks.")
    print(f"{'ID':<4}{'PRIORITY':<10}{'CATEGORY':<10}{'DUE':<12}TITLE")
    for t in sorted(pending, key=priority_score, reverse=True):
        print(f"{t['id']:<4}{level(priority_score(t)):<10}{t['category']:<10}"
              f"{t['due'] or '-':<12}{t['title']}")


def finish(tasks, t):
    t["done"] = True
    if t["every"]:  # recurring: schedule the next occurrence
        tasks.append({**t, "id": max(x["id"] for x in tasks) + 1,
                      "due": next_due(t["due"], t["every"]), "done": False})


def cmd_done(a):
    tasks = load()
    for t in tasks:
        if t["id"] == a.id and not t["done"]:
            finish(tasks, t)
            save(tasks)
            return print(f"Completed #{a.id}")
    print("Task not found or already done.")


def cmd_run(_):
    tasks, today, ran = load(), dt.date.today(), 0
    for t in list(tasks):
        if t["done"] or not t["action"] or not t["due"]:
            continue
        if dt.date.fromisoformat(t["due"]) <= today:
            print(f"Running #{t['id']}: {t['title']}")
            run_action(t["action"])
            finish(tasks, t)
            ran += 1
    save(tasks)
    print(f"{ran} automation(s) executed.")


def main():
    p = argparse.ArgumentParser(description="Intelligent Task Automation")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("add", help="add a task")
    s.add_argument("title")
    s.add_argument("--every", choices=["daily", "weekly", "monthly"])
    s.add_argument("--action", help='e.g. "organize|./Downloads" or "backup|./src|./dst"')
    s.set_defaults(fn=cmd_add)

    sub.add_parser("list", help="list pending tasks by priority").set_defaults(fn=cmd_list)

    s = sub.add_parser("done", help="mark a task done")
    s.add_argument("id", type=int)
    s.set_defaults(fn=cmd_done)

    sub.add_parser("run", help="execute due automations").set_defaults(fn=cmd_run)

    s = sub.add_parser("organize", help="organise a folder by file type")
    s.add_argument("folder")
    s.set_defaults(fn=lambda a: organize(a.folder))

    args = p.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
