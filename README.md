# AI Agents for Healthcare and Diagnostics — Hands-on Labs

Hands-on labs for a 2-day live-online course on **building safe AI agents for laboratory diagnostics, mass
spectrometry and laboratory research**, with **Google ADK** and **Gemini**. Each lab is one Google Colab notebook:
open it, follow the guide inside every task, build a real agent.

> All labs take place in the **Northbridge Clinical & Research Laboratory**, which is **fictional**. Every dataset is
> **synthetic or public**. No real patient data. Training material only — not for clinical use.

## Start here
1. Open **Lab 0** (button below), then **File → Save a copy in Drive**.
2. Follow the notebook: create your free Gemini API key, store it in Colab Secrets, run Setup, build your first agent.
3. Post your **Lab 0 status card** in the course chat.

## Labs
| Lab | Topic | Time | Open |
|---|---|---|---|
| 0 | Get ready: API key, first agent, Gemini tools | 15 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab00_Setup_Check.ipynb) |
| 1 | Spot the hallucination: the SOP assistant | 55 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab01_SOP_Assistant.ipynb) |
| 2 | QC agent for LC-MS/MS batches | 50 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab02_QC_Agent.ipynb) |
| 3 | Risk prediction agent with a guardrail in code | 35 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab03_Risk_Agent.ipynb) |
| 4 | Image triage with a human review queue | 60 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab04_Image_Triage.ipynb) |
| 5 | Interoperability agent: FHIR results and critical values | 1 h 30 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab05_FHIR_Agent.ipynb) |
| 6 | Hallucination hunt and the guardian agent | 1 h 50 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab06_Guardian_Agent.ipynb) |
| 7 | Research agent with verified citations | 1 h 15 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab07_Research_Agent.ipynb) |
| 8 | Capstone: design and pitch your laboratory agent | 2 h 15 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab08_Capstone.ipynb) |

## How every lab works
**Your task** (why it matters) · **Steps** (a short guide) · **Your cell** (replace every `___`, or fill the form) ·
**CHECK** (tells you what is right and exactly what to fix) · **Hint**, then **Solution** (folded).
Task labels: *In the notebook* · *In the Gemini app* (no code) · *Optional challenge*. Every lab ends with a status
card to post in the course chat.

## What is inside
- `notebooks/` — one notebook per lab (generated; do not edit by hand)
- `labkit/` — the tested helpers the labs use (setup checks, running agents, traces, tools of each lab, audit log)
- `data/` — course data: fictional SOPs and questions (Labs 1, 6), synthetic LC-MS/MS batches (Lab 2), a synthetic
  cardiovascular cohort and model (Lab 3), 200 PathMNIST tiles and a small CNN (Lab 4), synthetic FHIR patients
  (Lab 5), cached PubMed records (Labs 6–7)
- `figures/` — the diagrams used in the notebooks

## Data credits
- **PathMNIST** (Lab 4): Yang J. et al., *MedMNIST v2*, Scientific Data 2023, CC BY 4.0; derived from NCT-CRC-HE-100K
  (Kather J.N. et al.).
- **PubMed** records (Labs 6–7): courtesy of the U.S. National Library of Medicine, via NCBI E-utilities.
- Everything else is synthetic and was generated for this course.

Code: Apache-2.0. Built with [Google ADK](https://github.com/google/adk-python) and the Gemini API.
