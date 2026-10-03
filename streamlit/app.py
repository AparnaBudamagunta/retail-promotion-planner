import streamlit as st
import requests
import time

# ── CONFIG ────────────────────────────────────────────────────
DATABRICKS_URL   = st.secrets["DATABRICKS_URL"]
DATABRICKS_TOKEN = st.secrets["DATABRICKS_TOKEN"]
JOB_ID           = 28161186495029

HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type":  "application/json"
}

EXAMPLE_PROMPTS = [
    {
        "label": "🥤 Diwali Beverages",
        "prompt": "Build a promotion for beverages in India for Diwali. My marketing budget is 10000 INR.",
        "desc":   "Seasonal · India"
    },
    {
        "label": "🧴 FMCG Clearance",
        "prompt": "I need to clear my FMCG stock in India before year end.",
        "desc":   "Clearance · India"
    },
    {
        "label": "🖥️ Black Friday",
        "prompt": "Build a promotion for electronics in USA for Black Friday.",
        "desc":   "Peak event · USA"
    },
    {
        "label": "🧼 Brand Promotion",
        "prompt": "Build a promotion for Ariel in India for Diwali.",
        "desc":   "Single brand · India"
    }
]

# ── PAGE SETUP ─────────────────────────────────────────────────
st.set_page_config(
    page_title="AI Promotion Planner",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── STYLES ─────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background: #FFFFFF;
}

#MainMenu {visibility: hidden;}
footer {visibility: hidden;}
header {visibility: hidden;}

.stApp {
    background: #F8F8FA;
}

/* ── SIDEBAR ── */
[data-testid="stSidebar"] {
    background: #1A0033;
    border-right: 1px solid #2D0055;
}

[data-testid="stSidebar"] * {
    color: #E8E0F0 !important;
}

[data-testid="stSidebar"] .stButton button {
    background: #2D0055 !important;
    border: 1px solid #3D0070 !important;
    color: #E8E0F0 !important;
    border-radius: 8px !important;
    text-align: left !important;
    padding: 12px 14px !important;
    font-size: 13px !important;
    margin-bottom: 8px !important;
    transition: all 0.2s !important;
    line-height: 1.5 !important;
}

[data-testid="stSidebar"] .stButton button:hover {
    border-color: #A100FF !important;
    background: #3D0070 !important;
}

/* ── HERO ── */
.hero {
    background: linear-gradient(135deg, #1A0033 0%, #4B0099 100%);
    border-radius: 12px;
    padding: 36px 40px;
    margin-bottom: 28px;
    color: white;
    position: relative;
    overflow: hidden;
}

.hero::after {
    content: '';
    position: absolute;
    top: -40px;
    right: -40px;
    width: 200px;
    height: 200px;
    background: rgba(161, 0, 255, 0.15);
    border-radius: 50%;
}

.hero-title {
    font-size: 30px;
    font-weight: 700;
    margin: 0 0 8px 0;
    letter-spacing: -0.5px;
    line-height: 1.2;
}

.hero-sub {
    font-size: 14px;
    color: rgba(255,255,255,0.7);
    margin: 0;
    font-weight: 300;
    max-width: 600px;
    line-height: 1.6;
}

.hero-pills {
    display: flex;
    gap: 8px;
    margin-top: 20px;
    flex-wrap: wrap;
}

.hero-pill {
    background: rgba(161, 0, 255, 0.3);
    border: 1px solid rgba(161, 0, 255, 0.5);
    color: rgba(255,255,255,0.9);
    font-size: 11px;
    font-weight: 500;
    padding: 4px 12px;
    border-radius: 20px;
}

/* ── USER MESSAGE ── */
.user-msg {
    background: #1A0033;
    color: #F0E8FF;
    border-radius: 10px;
    padding: 16px 20px;
    margin-bottom: 24px;
    font-size: 15px;
    border-left: 3px solid #A100FF;
}

.user-msg-label {
    font-size: 10px;
    font-weight: 700;
    color: #A100FF;
    letter-spacing: 1.5px;
    text-transform: uppercase;
    margin-bottom: 6px;
}

/* ── PLAN OUTPUT ── */
.plan-wrap {
    background: white;
    border-radius: 12px;
    padding: 28px 32px;
    border: 1px solid #EDE8F5;
    margin-bottom: 16px;
    box-shadow: 0 2px 8px rgba(161,0,255,0.05);
}

/* ── TABLES ── */
table {
    width: 100%;
    border-collapse: collapse;
    font-size: 13px;
}

th {
    background: #1A0033;
    color: white;
    font-weight: 600;
    padding: 10px 14px;
    text-align: left;
    font-size: 11px;
    letter-spacing: 0.5px;
}

td {
    padding: 10px 14px;
    border-bottom: 1px solid #F0ECF8;
    color: #2D2D2D;
}

tr:nth-child(even) td {
    background: #FAF8FF;
}

tr:last-child td {
    border-bottom: none;
}

/* ── SECTION HEADINGS inside plan ── */
h2 {
    color: #4B0099;
    font-size: 16px;
    font-weight: 700;
    border-bottom: 2px solid #A100FF;
    padding-bottom: 8px;
    margin-top: 28px;
    margin-bottom: 16px;
}

h3 {
    color: #1A0033;
    font-size: 14px;
    font-weight: 600;
    margin-top: 20px;
}

/* ── BOTTOM NOTE ── */
.bottom-note {
    background: #F5F0FF;
    border-left: 3px solid #A100FF;
    border-radius: 0 8px 8px 0;
    padding: 12px 18px;
    font-size: 13px;
    color: #4B0099;
    margin-top: 20px;
    line-height: 1.6;
}

/* ── DIVIDER ── */
.purple-divider {
    border: none;
    border-top: 1px solid #EDE8F5;
    margin: 24px 0;
}

/* ── FOOTER ── */
.footer {
    text-align: center;
    color: #9CA3AF;
    font-size: 11px;
    padding: 20px;
    margin-top: 8px;
    letter-spacing: 0.3px;
}

/* Status */
[data-testid="stStatusWidget"] {
    border-color: #A100FF !important;
}
</style>
""", unsafe_allow_html=True)


# ── SIDEBAR ────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("""
    <div style='padding:16px 0 24px 0;'>
        <div style='font-size:18px; font-weight:700;
                    color:#A100FF; margin-bottom:4px;'>
            Promotion Planner
        </div>
        <div style='font-size:12px; color:#9080B0;
                    line-height:1.5;'>
            AI-powered retail promotion decisions
            backed by live catalog data.
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.markdown("""
    <div style='font-size:10px; font-weight:700;
                color:#A100FF; letter-spacing:1.5px;
                text-transform:uppercase;
                margin-bottom:10px;'>
        Try an example
    </div>
    """, unsafe_allow_html=True)

    for ex in EXAMPLE_PROMPTS:
        if st.button(
            f"{ex['label']}\n{ex['desc']}",
            key=f"ex_{ex['label']}",
            use_container_width=True
        ):
            st.session_state["prefill"] = ex["prompt"]
            st.rerun()

    st.markdown("<div style='margin:20px 0; border-top:1px solid #2D0055;'></div>",
                unsafe_allow_html=True)

    st.markdown("""
    <div style='font-size:10px; font-weight:700;
                color:#A100FF; letter-spacing:1.5px;
                text-transform:uppercase;
                margin-bottom:12px;'>
        How it works
    </div>
    <div style='font-size:12px; line-height:2.2; color:#9080B0;'>
        <span style='color:#A100FF; font-weight:600;'>01</span>
        &nbsp; Describe your promotion<br>
        <span style='color:#A100FF; font-weight:600;'>02</span>
        &nbsp; AI reads your catalog<br>
        <span style='color:#A100FF; font-weight:600;'>03</span>
        &nbsp; Simulation runs P&amp;L<br>
        <span style='color:#A100FF; font-weight:600;'>04</span>
        &nbsp; Full plan delivered
    </div>
    """, unsafe_allow_html=True)

    st.markdown("<div style='margin:20px 0; border-top:1px solid #2D0055;'></div>",
                unsafe_allow_html=True)

    if st.button("Clear conversation",
                 use_container_width=True):
        st.session_state["messages"] = []
        st.session_state.pop("prefill", None)
        st.rerun()

    st.markdown("""
    <div style='font-size:11px; color:#4B3570;
                margin-top:24px; line-height:2;'>
        <span style='color:#7040A0;'>Powered by</span><br>
        Databricks Delta Lake<br>
        Groq AI<br>
        PySpark Simulation
    </div>
    """, unsafe_allow_html=True)


# ── MAIN ───────────────────────────────────────────────────────
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Hero
st.markdown("""
<div class='hero'>
    <div class='hero-title'>AI Retail Promotion Planner</div>
    <div class='hero-sub'>
        Describe any promotion in plain English.
        Get a complete data-driven plan in seconds —
        with P&amp;L simulation, segment playbook,
        competitor context and execution checklist.
    </div>
    <div class='hero-pills'>
        <span class='hero-pill'>P&amp;L Simulation</span>
        <span class='hero-pill'>Segment Playbook</span>
        <span class='hero-pill'>Competitor Context</span>
        <span class='hero-pill'>Execution Checklist</span>
        <span class='hero-pill'>Cannibalization Risk</span>
    </div>
</div>
""", unsafe_allow_html=True)

# History
for msg in st.session_state["messages"]:
    if msg["role"] == "user":
        st.markdown(f"""
        <div class='user-msg'>
            <div class='user-msg-label'>Your request</div>
            {msg['content']}
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(
            "<div class='plan-wrap'>",
            unsafe_allow_html=True
        )
        st.markdown(msg["content"])
        st.markdown("</div>", unsafe_allow_html=True)
        st.markdown(
            "<hr class='purple-divider'>",
            unsafe_allow_html=True
        )


# ── JOB RUNNER ─────────────────────────────────────────────────
# def run_job(prompt: str) -> str:
#     run_resp = requests.post(
#         f"{DATABRICKS_URL}/api/2.1/jobs/run-now",
#         headers=HEADERS,
#         json={
#             "job_id": JOB_ID,
#             "notebook_params": {"user_request": prompt}
#         }
#     )

#     if run_resp.status_code != 200:
#         return f"❌ Could not start job: {run_resp.text}"

#     run_id = run_resp.json()["run_id"]
#     max_wait = 360
#     elapsed  = 0

#     while elapsed < max_wait:
#         time.sleep(10)
#         elapsed += 10

#         status_resp = requests.get(
#             f"{DATABRICKS_URL}/api/2.1/jobs/runs/get",
#             headers=HEADERS,
#             params={"run_id": run_id}
#         )
#         status = status_resp.json()
#         state  = status["state"]["life_cycle_state"]

#         if state == "TERMINATED":
#             if status["state"]["result_state"] == "SUCCESS":
#                 tasks       = status.get("tasks", [])
#                 task_run_id = tasks[0]["run_id"] \
#                     if tasks else run_id
#                 out_resp = requests.get(
#                     f"{DATABRICKS_URL}/api/2.1/jobs/runs/get-output",
#                     headers=HEADERS,
#                     params={"run_id": task_run_id}
#                 )
#                 return out_resp.json().get(
#                     "notebook_output", {}
#                 ).get("result", "No output returned.")
#             else:
#                 return "❌ Job did not complete. Please try again."

#         elif state in ["INTERNAL_ERROR", "SKIPPED"]:
#             return "❌ An error occurred. Please try again."

#     return "⏱️ Request timed out. Please try again."


# ── CHAT INPUT ─────────────────────────────────────────────────
prefill = st.session_state.pop("prefill", "")
prompt  = st.chat_input(
    "Describe your promotion — product, region, event, budget..."
) or prefill

if prompt:
    st.markdown(f"""
    <div class='user-msg'>
        <div class='user-msg-label'>Your request</div>
        {prompt}
    </div>
    """, unsafe_allow_html=True)

    st.session_state["messages"].append({
        "role": "user", "content": prompt
    })

    with st.status(
        "Building your promotion plan...",
        expanded=True
    ) as status_box:
        
        # Submit job first
        st.write("📡 Submitting to Databricks...")
        
        run_resp = requests.post(
            f"{DATABRICKS_URL}/api/2.1/jobs/run-now",
            headers=HEADERS,
            json={
                "job_id": JOB_ID,
                "notebook_params": {"user_request": prompt}
            }
        )

        if run_resp.status_code != 200:
            st.error(f"Could not start job: {run_resp.text}")
            st.stop()

        run_id = run_resp.json()["run_id"]
        
        # Poll with meaningful status updates
        max_wait = 360
        elapsed  = 0
        plan     = None
        step_shown = {
            30:  "📦 Fetching your product catalog...",
            60:  "🧮 Running financial simulation...",
            90:  "🤖 AI making promotion decisions...",
            120: "📝 Assembling your plan...",
            150: "⏳ Almost there...",
            180: "⏳ Finalising...",
        }

        while elapsed < max_wait:
            time.sleep(10)
            elapsed += 10

            # Show progress message at key intervals
            if elapsed in step_shown:
                st.write(step_shown[elapsed])

            status_resp = requests.get(
                f"{DATABRICKS_URL}/api/2.1/jobs/runs/get",
                headers=HEADERS,
                params={"run_id": run_id}
            )
            status = status_resp.json()
            state  = status["state"]["life_cycle_state"]

            if state == "TERMINATED":
                if status["state"]["result_state"] == "SUCCESS":
                    tasks       = status.get("tasks", [])
                    task_run_id = tasks[0]["run_id"] \
                        if tasks else run_id
                    out_resp = requests.get(
                        f"{DATABRICKS_URL}/api/2.1/jobs/runs/get-output",
                        headers=HEADERS,
                        params={"run_id": task_run_id}
                    )
                    plan = out_resp.json().get(
                        "notebook_output", {}
                    ).get("result", "No output returned.")
                else:
                    plan = "❌ Job did not complete. Please try again."
                break

            elif state in ["INTERNAL_ERROR", "SKIPPED"]:
                plan = "❌ An error occurred. Please try again."
                break

        if not plan:
            plan = "⏱️ Request timed out. Please try again."

        st.write("✅ Plan ready.")
        status_box.update(
            label="Plan ready", state="complete"
        )
        
    st.markdown(
        "<div class='plan-wrap'>",
        unsafe_allow_html=True
    )
    st.markdown(plan)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown("""
    <div class='bottom-note'>
        This plan was generated using live Databricks 
        Delta Lake catalog data, PySpark financial 
        simulation, and Groq AI decision-making. 
        Every number is calculated — no templates, 
        no hardcoded rules.
    </div>
    """, unsafe_allow_html=True)

    st.session_state["messages"].append({
        "role": "assistant", "content": plan
    })

    st.markdown("""
    <div class='footer'>
        Databricks Delta Lake · Groq AI · 
        PySpark Simulation
    </div>
    """, unsafe_allow_html=True)