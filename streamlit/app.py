import streamlit as st
import requests
import time
import json

# ── CONFIG ────────────────────────────────────────
DATABRICKS_URL = st.secrets["DATABRICKS_URL"]
DATABRICKS_TOKEN = st.secrets["DATABRICKS_TOKEN"]
JOB_ID = 28161186495029

HEADERS = {
    "Authorization": f"Bearer {DATABRICKS_TOKEN}",
    "Content-Type": "application/json"
}

# ── PAGE CONFIG ───────────────────────────────────
st.set_page_config(
    page_title="AI Retail Promotion Planner",
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 AI Retail Promotion Planner")
st.caption("Powered by Databricks + Groq AI")

# ── CHAT HISTORY ──────────────────────────────────
if "messages" not in st.session_state:
    st.session_state.messages = []

# Display chat history
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# ── CHAT INPUT ────────────────────────────────────
if prompt := st.chat_input(
    "Describe your promotion... e.g. 'Build a promotion for beverages in India for Diwali. Budget 10000 INR'"
):
    # Show user message
    st.session_state.messages.append({
        "role": "user",
        "content": prompt
    })
    with st.chat_message("user"):
        st.markdown(prompt)

    # Call Databricks Job
    with st.chat_message("assistant"):
        with st.spinner("Building your promotion plan..."):

            # Submit job run
            run_response = requests.post(
                f"{DATABRICKS_URL}/api/2.1/jobs/run-now",
                headers=HEADERS,
                json={
                    "job_id": JOB_ID,
                    "notebook_params": {
                        "user_request": prompt
                    }
                }
            )

            if run_response.status_code != 200:
                st.error(f"Failed to start job: {run_response.text}")
                st.stop()

            run_id = run_response.json()["run_id"]

            # Poll for completion
            max_wait = 300  # 5 minutes
            elapsed = 0
            plan = None

            while elapsed < max_wait:
                time.sleep(10)
                elapsed += 10

                status_response = requests.get(
                    f"{DATABRICKS_URL}/api/2.1/jobs/runs/get",
                    headers=HEADERS,
                    params={"run_id": run_id}
                )

                status = status_response.json()
                life_cycle = status["state"]["life_cycle_state"]

                if life_cycle == "TERMINATED":
                    result_state = status["state"]["result_state"]
                    if result_state == "SUCCESS":
                        # Get task run ID first
                        tasks = status.get("tasks", [])
                        if tasks:
                            task_run_id = tasks[0]["run_id"]
                        else:
                            task_run_id = run_id

                        # Get output using task run ID
                        output_response = requests.get(
                            f"{DATABRICKS_URL}/api/2.1/jobs/runs/get-output",
                            headers=HEADERS,
                            params={"run_id": task_run_id}
                        )
                        output_data = output_response.json()
                        plan = (
                            output_data.get("notebook_output", {}).get("result")
                            or "No output returned"
                        )
                    else:
                        plan = "❌ Job failed. Please try again."
                    break

                elif life_cycle in ["INTERNAL_ERROR", "SKIPPED"]:
                    plan = "❌ Job error. Please try again."
                    break

            if not plan:
                plan = "⏱️ Timed out. Please try again."

        st.markdown(plan)
        st.session_state.messages.append({
            "role": "assistant",
            "content": plan
        })
