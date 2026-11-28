# Implementation log

Continue from this file. The application in `development_plan.md` is running.

## Run

From `backend`, with the existing virtual environment:

```
venv\Scripts\python.exe frontend_interface.py
```

Open http://127.0.0.1:8000

CLI:

```
venv\Scripts\python.exe main.py
```

`You:` is red, `Agent:` is green. `exit` quits. On exit, an untitled chat gets its name once, and user preferences are reviewed.

`uv` is installed in this venv. The first Yahoo request starts `uvx yfmcp==0.14.1`, which downloads that server into the uv cache.

## This round

- Chat markdown is rendered. The web page handles headings, lists, bold, italic, code, links, and tables. The terminal shows the same subset: bold is ANSI, tables are aligned columns. No extra frontend package.
- A chat title is generated only while the title is still `New chat`. Leaving that chat (switch or New chat) or closing the page runs it. The close response returns the title before preferences are reviewed, and the sidebar applies that title immediately. A chat that already has a title is not renamed.
- Yahoo Finance goes through the `yfmcp` MCP server (`uvx yfmcp==0.14.1`), which uses yfinance. `YahooTool` starts that process over stdio and gives the model the server's tools. On this Windows profile the CA file path contains a non-ASCII character, which curl rejects, so the child process gets `PYTHONUTF8=1` and a CA bundle path curl can open.
- User preferences live in `backend/instructions/instruction_references.md`. The file starts as "None yet." On the same close events as the title (leave a chat, refresh, close the tab, exit the CLI), the model may update that file. The instruction is strict: only a lasting preference about how to answer, such as language or tone. Anything else must come back as `UNCHANGED`, and a reply longer than 12 lines or 800 characters is discarded.
- The new Groq key works. A live turn called `yfinance_get_price_history` for AAPL and answered with the latest close.

## What exists

- `backend/main.py` starts the CLI only.
- `backend/cli_interface.py` is the terminal UI.
- `backend/frontend_interface.py` is the FastAPI app and the web entry point.
- `backend/agent.py` is the shared turn: save the message, load a skill, call the model, run tools, compact. `close_chat` names an untitled chat and reviews preferences.
- `backend/llm_interface.py`: `LLMInterface.answer` loops until the model stops calling tools. `GroqLLMInterface` is the Groq client. Model and client name live in `backend/config.py` (`openai/gpt-oss-120b`, `GROQ`).
- `backend/database_interface.py` reads and writes `Chat` and `Message` models. SQLite file is `backend/db/db.db`.
- `backend/instructions/system.md` is the system prompt. `instruction_references.md` is the preferences note. Skills are `instructions/skills/*.md`.
- Tools: `create_chart` (matplotlib, `backend/db/images`), `create_pdf_report` (fpdf2, `backend/db/reports`), Yahoo via `yfmcp`.
- `frontend/` is one page. `markdown.js` renders messages. No npm.

## Decisions that are still open

- `yfmcp==0.14.1` is the yfinance MCP whose documented install is `uvx`. If a different server was intended, change `_PACKAGE` in `backend/tools/yahoo_tool.py`.
- Remote skill download is still not implemented. Add a `.md` file under `backend/instructions/skills`.
- `backend/.env` is still tracked by git. `.gitignore` ignores `.env`, but that does not untrack a file that is already committed. Remove it from the index before the next commit so the new key is not pushed.

## Verified

- Title is written once. A named chat stays named across close.
- Preferences: an explicit style request is saved; `UNCHANGED`, and a long dump, are not.
- Terminal markdown, including a table.
- `yfmcp` listed 15 tools and returned AAPL history.
- Groq replied `pong`. A full agent turn used `yfinance_get_price_history` and returned the latest close.
- `GET /` references `markdown.js`, and that file is served.

## Not verified in a browser

No browser tool was available. The page source and the markdown parser's terminal twin were checked. Clicking a rendered table was not done.
