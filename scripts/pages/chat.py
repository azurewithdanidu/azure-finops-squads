"""Chat with the finops-orchestrator hosted agent, using the signed-in user's own Entra token.

Hosted agents need a real user identity on the call, so a managed identity cannot be used here.
App Service Easy Auth (token store on) passes the user's access token in X-MS-TOKEN-AAD-ACCESS-TOKEN.
"""
import os
import subprocess

import requests
import streamlit as st

ENDPOINT = os.environ.get("FINOPS_AGENT_ENDPOINT", "").strip()
TIMEOUT_S = 600

st.set_page_config(page_title="finops-squad chat", page_icon="💬", layout="wide")
st.title("💬 Chat with the FinOps orchestrator")
st.caption(
    "Runs the hosted `finops-orchestrator` agent as you. Agents are read-only on Azure; "
    "remediation is PR-only and needs your explicit approval."
)


def _user_token() -> str | None:
    token = st.context.headers.get("X-MS-TOKEN-AAD-ACCESS-TOKEN")
    if token:
        return token
    if not os.environ.get("WEBSITE_SITE_NAME"):  # local dev: developer sign-in
        try:
            return subprocess.run(
                ["az", "account", "get-access-token", "--resource", "https://ai.azure.com", "--query", "accessToken", "-o", "tsv"],
                capture_output=True, text=True, check=True, shell=os.name == "nt",
            ).stdout.strip() or None
        except Exception:
            return None
    return None


def _ask(prompt: str, token: str, previous_id: str | None) -> tuple[str, str | None]:
    body = {"input": prompt, "stream": False}
    if previous_id:
        body["previous_response_id"] = previous_id
    r = requests.post(ENDPOINT, json=body, headers={"Authorization": f"Bearer {token}"}, timeout=TIMEOUT_S)
    if r.status_code in (401, 403):
        raise PermissionError("Your sign-in token was rejected by Foundry. Sign out and in again, or check your Foundry User role.")
    r.raise_for_status()
    data = r.json()
    text = "\n\n".join(
        part.get("text", "")
        for item in data.get("output", []) if item.get("type") == "message"
        for part in item.get("content", []) if part.get("type") == "output_text"
    )
    return text or "(no text returned)", data.get("id")


if not ENDPOINT:
    st.error("FINOPS_AGENT_ENDPOINT is not configured.")
    st.stop()

token = _user_token()
if not token:
    st.warning("No Foundry access token on this session. Sign out (/.auth/logout) and sign in again, accepting the consent prompt.")
    st.stop()

if "chat" not in st.session_state:
    st.session_state.chat, st.session_state.prev = [], None

if st.sidebar.button("New conversation"):
    st.session_state.chat, st.session_state.prev = [], None
    st.rerun()

for m in st.session_state.chat:
    with st.chat_message(m["role"]):
        st.markdown(m["content"])

if prompt := st.chat_input("e.g. Audit tagging coverage for subscription 40668c14-…"):
    st.session_state.chat.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)
    with st.chat_message("assistant"):
        with st.spinner("The orchestrator is working — full audits can take a few minutes…"):
            try:
                reply, st.session_state.prev = _ask(prompt, token, st.session_state.prev)
            except PermissionError as exc:
                reply = f"⚠️ {exc}"
            except Exception as exc:
                reply = f"⚠️ Request failed: {type(exc).__name__}"
        st.markdown(reply)
    st.session_state.chat.append({"role": "assistant", "content": reply})
