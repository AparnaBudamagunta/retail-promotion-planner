# AI Retail Promotion Planner
### ET AI Hackathon 2026 · Team: Aparna

> **Type a promotion request in plain English. Get a complete, data-driven 10-section promotion plan in seconds.**

---

## 🔗 Live Demo

**[https://retail-promotion-planner-cssz2u8ukmvukjldfsyjaa.streamlit.app/](https://retail-promotion-planner-cssz2u8ukmvukjldfsyjaa.streamlit.app/)**

---

## ⚡ Quickest Way To Evaluate

**No setup needed.**

1. Click the live demo link above
2. Type any of the example prompts below
3. Wait 60-90 seconds for the full plan

That is it. No Databricks account. No API keys. No installation.

---

## What This Does

A retail category manager types a promotion request in natural language. The system returns a complete promotion plan with:

- **P&L simulation** — pessimistic, base and optimistic scenarios pre-calculated by PySpark
- **Product selection** — AI selects best 2-3 products based on net gain, stock status and goal alignment
- **Segment playbook** — differentiated offers per customer segment based on price sensitivity
- **Competitor context** — real-time gap analysis against DMart, BigBazaar, Amazon, Flipkart
- **Cannibalization risk** — quantified impact on non-promoted own products
- **Execution checklist** — phased action plan with dates tied to the event calendar

---

## Example Prompts To Try

```
DMart is undercutting us on Coca-Cola in India ahead of Diwali. 
Budget is 10,000 INR. Help me respond.
```

```
Build a promotion for FMCG in India for Diwali. 
Budget 15,000 INR. I need at least 40% margin.
```

```
I have too much Colgate stock in India. 
Help me move it before month end.
```

```
Our stationery sales in Germany are terrible. 
We are losing to every competitor. Fix this.
```

```
Build a promotion for electronics in USA for Black Friday.
```

> **Note:** This is a single-turn system. Include all context — product, geography, event, budget and goal — in one message for the most complete plan.

---

## Architecture

```
Manager (Plain English)
    ↓
Streamlit UI (Community Cloud)
    ↓ Databricks Jobs REST API
┌─────────────────────────────────────────────┐
│           Databricks Platform               │
│                                             │
│  ① Goal extraction  ←→  Groq qwen3.8b-27b  │
│         ↓                                   │
│  ② Data retrieval   ←→  6 Delta Lake tables │
│         ↓                                   │
│  ③ P&L simulation       PySpark · all SKUs  │
│         ↓                                   │
│  ④ AI decisions     ←→  Groq gpt-oss-20b    │
│         ↓                                   │
│  ⑤ Plan assembly        Python · 10 sections│
└─────────────────────────────────────────────┘
    ↓
10-Section Promotion Plan
```

**Key architectural principle: LLM = judge · PySpark = executor**
Every number in the plan comes from PySpark simulation. The LLM makes decisions — never calculations.

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| UI | Streamlit Community Cloud |
| Orchestration | Databricks Jobs REST API |
| Data platform | Databricks Free Edition |
| Storage | Delta Lake · Unity Catalog · DBFS |
| Computation | PySpark Serverless |
| LLM — Scope parsing | Groq qwen3.8b-27b |
| LLM — Decisions | Groq gpt-oss-20b |
| LLM framework | litellm |
| Language | Python 3.11 |

---

## Data

6 Delta Lake tables covering 3 geographies (India, USA, Germany) and 5 categories (beverages, FMCG, electronics, stationery, apparel):

| Table | Purpose |
|-------|---------|
| products | Master catalog with pricing and cost |
| inventory_status | Stock levels and days cover |
| competitor_prices | DMart, BigBazaar, Amazon, Flipkart, BestBuy, Kaufland |
| customer_segments | 5 segments × 3 geographies with price sensitivity |
| holiday_calendar | 28 promotional events 2026-2027 |
| benchmark_elasticity | Price elasticity and cannibalization rates by category |

---

## Repository Structure

```
retail-promotion-planner/
│
├── 01_data_setup.ipynb        # Creates all Delta Lake tables
├── 02_ai_engine.ipynb         # Full pipeline with all functions
├── 03_api_runner.ipynb        # Databricks job entry point
├── engine.py                  # Exported production engine
│
└── streamlit/
    └── app.py                 # Streamlit UI
```

---

## How to Run Locally

### Prerequisites
- Databricks workspace (Free Edition works)
- Groq API key (free at console.groq.com)
- Python 3.11+

### Setup

**1. Clone the repo**
```bash
git clone https://github.com/AparnaBudamagunta/retail-promotion-planner
cd retail-promotion-planner
```

**2. Set up Databricks secrets**
```python
# Run once in any Databricks notebook cell
import requests

WORKSPACE_URL = "https://your-workspace.azuredatabricks.net"
DATABRICKS_TOKEN = "your_pat_token"

headers = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

requests.post(
    f"{WORKSPACE_URL}/api/2.0/secrets/scopes/create",
    headers=headers,
    json={"scope": "my_scope"}
)

requests.post(
    f"{WORKSPACE_URL}/api/2.0/secrets/secrets/put",
    headers=headers,
    json={
        "scope": "my_scope",
        "key": "groq_api_key",
        "string_value": "your_groq_api_key_here"
    }
)
```
> Delete this cell immediately after running.

**3. Run data setup**

Upload `01_data_setup.ipynb` to Databricks and run all cells. This creates the 6 Delta Lake tables.

**4. Run engine setup**

Upload `02_ai_engine.ipynb` to Databricks and run all cells. This exports `engine.py`.

**5. Create Databricks job**

Create a job pointing to `03_api_runner.ipynb`. Note the Job ID.

**6. Configure Streamlit**

In `streamlit/app.py` update:
```python
DATABRICKS_HOST = "https://your-workspace.azuredatabricks.net"
DATABRICKS_TOKEN = "your_pat_token"
JOB_ID = your_job_id
```

**7. Run Streamlit**
```bash
cd streamlit
pip install streamlit requests
streamlit run app.py
```

---

## What Works

```
✅ Natural language promotion requests
✅ Multi-category support (beverages, FMCG, electronics, stationery, apparel)
✅ Multi-geography support (India INR, USA USD, Germany EUR)
✅ Goal inference from natural language
✅ Competitor-based discount calculation
✅ P&L simulation (pessimistic, base, optimistic)
✅ Segment-differentiated playbook
✅ Cannibalization risk quantification
✅ Honest clarification when product not in catalog
✅ Budget constraint handling
✅ Margin constraint handling
✅ Inventory-aware recommendations
```

## Known Limitations

```
⚠️ Single-turn only — no conversation memory
   Include all context in one message.

⚠️ Multi-geography in one request not supported
   Submit separate requests per geography.

⚠️ Brand-level filtering not implemented
   Use category or specific product name.

⚠️ Manager-specified discount not honoured
   System optimises discount from data.

⚠️ Synthetic data
   50 products across 3 geographies.
   Results improve with real historical data.
```

---

## Key Design Decisions

**Why PySpark for simulation, not LLM?**
LLMs have ~95-98% arithmetic accuracy. For financial promotion planning we need 100%. PySpark gives deterministic, auditable, repeatable calculations every time.

**Why only 2 LLM calls?**
One to parse manager intent. One to select products and make decisions. Everything else is deterministic code. This keeps cost predictable, latency low and results consistent.

**Why structured pipeline over autonomous agents?**
In early prototyping we built a LangChain-style tool registry where the LLM decided which data to fetch. Testing showed inconsistent results — the LLM sometimes skipped fetching critical data. We evolved to a structured pipeline where all data is always fetched in a fixed sequence. More reliable. More predictable. Easier to debug.

---

## Contact

**Aparna Budamagunta**
ET AI Hackathon 2026