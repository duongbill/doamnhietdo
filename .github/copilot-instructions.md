## Repo snapshot

This repository contains a single Streamlit app: `fe.py`. It reads sensor feeds from ThingSpeak, computes a Discomfort Index (DI), and uses the Google Gemini (Generative Language) API to produce short climate-control suggestions. The app is intended to run interactively (UI + sidebar chatbot) and polls ThingSpeak in a tight loop every 5s.

## What an AI coding agent should know first

- Entrypoint: `fe.py` — small, self-contained Streamlit app (no packages beyond the imports).
- Primary external integrations:
  - ThingSpeak REST API: `THING_SPEAK_URL` (defined in `fe.py`) — app fetches latest 20 records.
  - Google Gemini generative API: `GEMINI_API_URL` + `GEMINI_API_KEY` constant in `fe.py` (replace with a real key).
- Runtime behavior: `fe.py` runs an infinite loop (while True) that fetches and processes new data every 5 seconds and updates Streamlit placeholders. This pattern blocks normal Streamlit reactivity if not carefully managed.

## Goals for the agent when editing or extending

- Keep Streamlit semantics intact: use `st.session_state` for persistent state across interactions (this project already stores `messages` and `latest_climate_data`).
- Avoid changing the polling cadence or loop structure without adding explicit controls — the current implementation expects a continuously running script (blocking loop + time.sleep).
- Do not commit API keys. When adding config support, prefer environment variables or a `.env` loader and document expected env names (e.g., GEMINI_API_KEY, THINGSPEAK_READ_KEY).

## Specific patterns and examples to follow

- Chat history shape: `st.session_state['messages']` is a list of objects {"role": "user"|"model", "parts": [{"text": "..."}]}. Keep the same shape when appending messages (see `with st.sidebar` block).
- Climate data shape: processed DataFrame columns are renamed to Vietnamese labels: `'Thời gian'`, `'Độ ẩm (%)'`, `'Nhiệt độ (°C)'`, `'Trạng thái Bơm'`. Many UI references use these exact names — changing them requires updating UI code and `process_data`.
- DI calculation: `calculate_discomfort_index(temp, hum_percent)` returns DI used for coloring and AI prompts. Tests or refactors should preserve numeric precision and None-safe handling.

## Common developer workflows (how to run / debug / test)

- Install dependencies (local environment): ensure Python has streamlit, requests, pandas, pytz installed. Example (Windows PowerShell):

```powershell
python -m pip install -r requirements.txt  # if you create one
# or manually
python -m pip install streamlit requests pandas pytz
```

- Run the app locally:

```powershell
streamlit run fe.py
```

- Troubleshooting network/API issues:
  - ThingSpeak: check channel id and read key constants in `fe.py`.
  - Gemini: the app currently posts JSON to `GEMINI_API_URL` with `?key=GEMINI_API_KEY` — ensure the key is supplied via environment variable or replaced in-file for local testing.

## Safe change guidance (do this, not that)

- Do: Replace hard-coded keys with environment-based configuration (os.getenv) and document env var names.
- Do: If you remove or rename DataFrame columns, update all downstream UI references and the `st.line_chart` input.
- Don't: Convert the top-level infinite while loop into a CPU-intensive tight loop. If you need periodic updates, prefer Streamlit's `st.experimental_singleton`, `st.experimental_memo`, or `st_autorefresh` (or convert to callback-based scheduling).
- Don't: Ship real API keys or secrets in commits.

## Files to inspect for common edits

- `fe.py` — primary file. Everything is here: UI, data fetching, AI calls, and session state.

## Example small tasks an agent can do right away

- Add environment variable config: read `GEMINI_API_KEY` and `READ_API_KEY` via `os.getenv` and fall back to current constants.
- Add a short README with run instructions if repo is missing one.
- Extract Gemini calls into a small helper module (e.g., `ai.py`) preserving payload shape and response parsing.

## When to ask for human help

- If you need production Gemini credentials or intention to change polling behavior (e.g., run this as a web service or background worker), ask for intended deployment environment.
- If you plan to internationalize labels or change timestamp timezone handling, ask which locale/format to prefer.

---

Please review these instructions and tell me which areas you want me to expand (examples, env var names, or a README addition). After confirmation I'll commit the file and run a quick verification that it exists in the workspace.
