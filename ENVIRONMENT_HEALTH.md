# JARVIS Environment Health Report

**Audit Date:** September 29, 2026  
**Host Platform:** Windows 11 Home Single Language (Build 26200)  
**Host Architecture:** AMD64 / x86_64  

---

## 1. Executive Status Matrix

| Component | Detected Specification | Classification | Notes / Impact |
| :--- | :--- | :---: | :--- |
| **Operating System** | Windows 11 Home Single Language 10.0.26200 | **READY** | Supported Windows NT host. |
| **Python Core** | Python 3.13.2 (`C:\Users\LOHITH\python\python.exe`) | **READY** | Standard 64-bit Python interpreter. |
| **Node.js** | v24.11.0 | **READY** | Node runtime installed. |
| **npm** | 11.6.1 | **READY** | Package manager available. |
| **Git** | 2.54.0.windows.1 | **READY** | Command line Git fully functional. |
| **Docker CLI** | 29.0.1, build eedd969 | **READY** | Docker client executable available. |
| **Docker Daemon** | Offline / Service pipe closed | **BLOCKED** | Pipe `//./pipe/dockerDesktopLinuxEngine` unreachable. |
| **Playwright Library** | 1.63.0 | **READY** | Python binding installed. |
| **Playwright Chromium**| `...\ms-playwright\chromium-1243\chrome.exe` | **READY** | Headless Chromium binary exists and can be launched. |
| **Backend Core Web** | FastAPI 0.125.0, Uvicorn 0.42.0, Pydantic 2.13.4 | **READY** | Web server foundation intact. |
| **Backend LLM Libs** | `groq`, `litellm` | **MISSING** | **Fatal startup blocker:** `app.main` fails on `import groq`. |
| **Backend Graph Libs**| `langgraph`, `langchain_core`, `langchain_groq`| **MISSING** | Legacy graph execution unavailable. |
| **Backend Utilities** | `psutil`, `docker` | **MISSING** | `psutil` missing (terminal falls back to taskkill); `docker` missing. |
| **Frontend Deps** | `frontend/node_modules` | **MISSING** | Next.js 14 packages not installed. |
| **Client Deps** | `client/node_modules` | **MISSING** | React 18 packages not installed (`client/dist` exists). |
| **Server Auth Deps** | `server/node_modules` | **MISSING** | Express auth gateway packages not installed. |
| **LLM Credentials** | `GROQ_API_KEY`, `OPENAI_API_KEY`, etc. | **MISCONFIGURED**| No keys defined in environment or `.env`. |
| **LLM Workers Pool** | `backend/data/workers.json` | **MISCONFIGURED**| File contains `[]` (empty worker pool). |
| **Ollama Local LLM** | `http://localhost:11434` | **BLOCKED** | Local daemon offline / not running. |
| **GitHub Token** | `GITHUB_TOKEN` | **BLOCKED** | Token unset; GitHub API rate-limited to unauthenticated tier. |
| **Hindsight Memory** | `HINDSIGHT_URL` | **NOT REQUIRED** | Falls back to local JSON store in `backend/data/hindsight_mock/`. |
| **Database** | MySQL / `DATABASE_URL` | **NOT REQUIRED** | Server has in-memory fallback driver. |

---

## 2. Detailed Dependency Inspection

### 2.1 Backend Python Environment (`backend/requirements.txt`)

| Package Requirement | Installed Version | Status | Failure Impact |
| :--- | :--- | :---: | :--- |
| `fastapi>=0.111.0` | 0.125.0 | **READY** | None |
| `uvicorn>=0.30.1` | 0.42.0 | **READY** | None |
| `pydantic>=2.9.0` | 2.13.4 | **READY** | None |
| `python-dotenv>=1.0.1` | 1.2.2 | **READY** | None |
| `PyYAML>=6.0.1` | 6.0.3 | **READY** | None |
| `playwright>=1.40.0` | 1.63.0 | **READY** | None |
| `pillow>=10.0.0` | 12.1.1 | **READY** | None |
| `starlette>=0.37.2` | 0.50.0 | **READY** | None |
| `httpx>=0.27.0` | 0.28.1 | **READY** | None |
| `groq` | *None* | **MISSING** | **Fatal startup error**: `from groq import Groq` in `app/llm/router.py` crashes FastAPI import. |
| `litellm` | *None* | **MISSING** | **Runtime error**: Required by `call_litellm()` in `app/llm/router.py`. |
| `langgraph>=0.1.1` | *None* | **MISSING** | Breaks `app/graph/workflow.py` if legacy agent is invoked. |
| `langchain-core` | *None* | **MISSING** | Breaks `app/graph/` nodes. |
| `langchain-groq` | *None* | **MISSING** | Breaks legacy graph Groq calls. |
| `docker>=7.1.0` | *None* | **MISSING** | Breaks `app/sandbox/docker_env.py`. |
| `psutil>=5.9.0` | *None* | **MISSING** | Graceful fallback implemented via Windows `taskkill /F /T`. |

### 2.2 JavaScript / TypeScript Runtime Environment

| Subproject | Directory | `node_modules` Present? | Scripts Defined | Status |
| :--- | :--- | :---: | :--- | :---: |
| **Next.js HUD Frontend** | `frontend/` | **NO** | `dev`, `build`, `start` | **MISSING** |
| **React Public Client** | `client/` | **NO** | `dev`, `build`, `preview` (`dist/` present) | **MISSING** |
| **Express Auth Server** | `server/` | **NO** | `dev`, `build`, `start`, `test` | **MISSING** |

### 2.3 Ports & Networking

| Port | Service | Expected State | Actual State | Conflict? |
| :--- | :--- | :--- | :--- | :---: |
| `8005` | FastAPI Backend (`start.bat`) | Listening | Unbound / Closed | None |
| `8006` | FastAPI Backend (`main.py` default) | Listening | Unbound / Closed | None |
| `3000` | Next.js Frontend | Listening | Unbound / Closed | None |
| `4000` | Express Auth Server | Listening | Unbound / Closed | None |
| `5173` | Vite React Client | Listening | Unbound / Closed | None |
| `11434` | Ollama Daemon | Optional Local OSS | Unbound / Offline | None |

---

## 3. Environment Health Verdict

**Overall Environment Health: PARTIAL / BLOCKED**

1. **Host Foundations (OS, Node, Python, Git, Playwright Browser): READY**
2. **Package Ecosystem: BLOCKED**
   - The Python runtime lacks critical dependencies (`groq`, `litellm`, `langgraph`, `docker`, `psutil`).
   - The Node.js applications lack `node_modules` entirely.
3. **External Services & Credentials: BLOCKED / MISCONFIGURED**
   - No LLM API keys (`GROQ_API_KEY`, etc.) are configured.
   - Docker daemon is offline.
   - Ollama is offline.
   - GitHub credentials are not present.
