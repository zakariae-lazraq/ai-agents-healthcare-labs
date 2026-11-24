# AI Agents for Healthcare and Diagnostics — Hands-on Labs

Hands-on labs for a 2-day live-online course on **building safe AI agents for laboratory
diagnostics, mass spectrometry and lab research**, with **Google ADK** and **Gemini**.
Each lab is one Google Colab notebook: open it, follow the guide inside every step, build a real agent.

> All labs take place in the **Northbridge Clinical & Research Laboratory**, which is **fictional**.
> Every dataset is **synthetic or public**. No real patient data. Training material only — not for clinical use.

## Start here

1. Open **Lab 0** below (button), then **File → Save a copy in Drive**.
2. Follow the notebook: create your free Gemini API key, run Setup, build your first agent.
3. Post the green **"Lab 0 complete ✅"** card in the course chat.

## Labs

| Lab | Topic | Time | Open |
|---|---|---|---|
| 0 | Get ready: API key, first agent, Gemini tools | 15 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/eliem08/ai-agents-healthcare-labs/blob/main/notebooks/Lab00_Setup_Check.ipynb) |
| 1 | Spot the hallucination: the SOP assistant | 55 min | coming |
| 2 | QC agent for LC-MS/MS batches | 50 min | coming |
| 3 | Risk prediction agent with explanations | 35 min | coming |
| 4 | Image triage agent with human review queue | 60 min | coming |
| 5 | Interoperability agent: FHIR results and critical values | 1 h 30 | coming |
| 6 | Hallucination hunt and the guardian agent | 1 h 50 | coming |
| 7 | Research agent with verified citations | 1 h 15 | coming |
| 8 | Capstone: design and pitch your lab agent | 2 h 15 | coming |

## How every lab works

📝 **Your task** · 🧭 **Mini-guide** · ✍️ **Your cell** (replace every `___`) · ✅ **Check** · 💡 **Hint / solution**
🟢 Gemini app (no code) · 🔵 notebook · 🟣 optional challenge

## What's inside

- `notebooks/` — one notebook per lab
- `labkit/` — small helpers (API key check, running an agent, trace cards, task checks)
- `data/` — synthetic course data

Code: Apache-2.0. Built with [Google ADK](https://github.com/google/adk-python) and the Gemini API.
