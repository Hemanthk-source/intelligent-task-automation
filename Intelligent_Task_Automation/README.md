# Intelligent Task Automation

A simple Python command-line project that auto-categorises tasks, scores their priority,
schedules recurring tasks, and runs automations (organise a folder, back up a folder).

## Requirements
Python 3.8+ (no external packages needed)

## Usage
```bash
python task_automation.py add "Pay electricity bill urgent tomorrow"
python task_automation.py add "Weekly backup" --every weekly --action "backup|./docs|./backups"
python task_automation.py add "Clean downloads in 2 days" --action "organize|./Downloads"
python task_automation.py list
python task_automation.py run
python task_automation.py done 1
python task_automation.py organize ./Downloads
```

## How it works
- classify(): keyword-based category detection
- parse_due(): extracts dates such as "tomorrow", "in 3 days", 2026-11-05
- priority_score(): urgency words + deadline proximity -> HIGH / MEDIUM / LOW
- run: executes due tasks that have an action attached
- Tasks are stored in tasks.json
