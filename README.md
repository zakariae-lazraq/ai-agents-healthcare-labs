# AI Agents for Healthcare and Diagnostics: Hands-on Labs

Nine hands-on labs for a 2-day course. In each lab you build a small **AI agent**: a program that uses Gemini
(Google's AI) and can act for a laboratory: look something up, run a calculation, prepare a report.
Everything runs in **Google Colab**, in your browser. Nothing to install.

**The one idea behind every lab:** AI can be wrong. So the **tools calculate**, the **agent proposes**, and a
**human decides**.

> All labs take place in the **Northbridge Clinical & Research Laboratory**, which is **fictional**. Every dataset is
> **synthetic or public**. No real patient data. Training material only, not for clinical use.

## What you need
- A Google account and the Chrome browser.
- A free Gemini API key: [aistudio.google.com/apikey](https://aistudio.google.com/apikey) → **Create API key** → copy it.

## Start here (10 minutes, once)
1. Click **Open in Colab** for **Lab 0** in the table below.
2. In Colab: **File → Save a copy in Drive**, so your work is kept.
3. Add your key: click the **key icon** in the left bar → **Add new secret** → name it `GOOGLE_API_KEY` →
   paste your key → switch **Notebook access** on. Never paste the key into a cell.
4. Run the cells from top to bottom with the **▶** button. The **Setup** cell must end with every line **OK**.
5. At the end of the lab, a **status card** appears. Post it in the course chat.

For every next lab: open it from the table, save a copy, and switch **Notebook access** on for your key
(the key is already saved).

## Labs
| Lab | What you build | Time | Open |
|---|---|---|---|
| 0 | Get ready: your key, your first agent, the Gemini tools | 15 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab00_Setup_Check.ipynb) |
| 1 | An assistant for lab procedures (SOPs), and why it must use the documents | 55 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab01_SOP_Assistant.ipynb) |
| 2 | A quality-control agent for LC-MS/MS batches | 50 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab02_QC_Agent.ipynb) |
| 3 | A risk agent with a safety rule written in code | 35 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab03_Risk_Agent.ipynb) |
| 4 | Image triage: unsure cases go to a human | 60 min | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab04_Image_Triage.ipynb) |
| 5 | Reading hospital results (HL7, FHIR): critical values go to a human | 1 h 30 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab05_FHIR_Agent.ipynb) |
| 6 | Find the AI's mistakes, then build a guardian agent that checks answers | 1 h 50 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab06_Guardian_Agent.ipynb) |
| 7 | A research agent: every claim cites a real PubMed article | 1 h 15 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab07_Research_Agent.ipynb) |
| 8 | Capstone: design, build and pitch your own lab agent, in a team | 2 h 15 | [![Open In Colab](https://colab.research.google.com/assets/colab-badge.svg)](https://colab.research.google.com/github/zakariae-lazraq/ai-agents-healthcare-labs/blob/main/notebooks/Lab08_Capstone.ipynb) |

## How every lab works
Each task has the same five parts:
1. **Your task:** what to do and why it matters.
2. **Steps:** a short guide.
3. **Your cell:** replace every `___` or fill in the form, then run it.
4. **CHECK:** run it. It tells you what is right and exactly what to fix.
5. **Hint**, then **Solution:** folded. Open them only if you are stuck.

Tasks marked *In the Gemini app* are done at [gemini.google.com](https://gemini.google.com), with no code.
Tasks marked *Optional challenge* are for those who finish early.

## If something goes wrong
| You see | Do this |
|---|---|
| A Setup line starts with **FIX** and mentions the API key | Key icon: check the name is `GOOGLE_API_KEY` and **Notebook access** is on. Run Setup again. |
| A message about **quota** or **busy** | The free limit was reached. Wait one minute and run the cell again. |
| A message ending with **"… first"** | A cell above was not run. Run it, then this one. |
| `NameError: … is not defined` | Colab restarted. Click the cell, then **Runtime → Run before**. |
| Still stuck | Copy the message and send it to the trainer. |

## What is inside
- `notebooks/`: one notebook per lab
- `labkit/`: the tested helper code the labs use
- `data/`: the course data: fictional procedures, synthetic lab batches, patients and images, cached PubMed records
- `figures/`: the diagrams used in the notebooks

## Data credits
- **PathMNIST** (Lab 4): Yang J. et al., *MedMNIST v2*, Scientific Data 2023, CC BY 4.0; derived from NCT-CRC-HE-100K
  (Kather J.N. et al.).
- **PubMed** records (Labs 6–7): courtesy of the U.S. National Library of Medicine, via NCBI E-utilities.
- Everything else is synthetic and was generated for this course.

Code: Apache-2.0. Built with [Google ADK](https://github.com/google/adk-python) and the Gemini API.
