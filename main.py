from __future__ import annotations

import hashlib
import io
import re
import textwrap
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request


app = FastAPI(title="SolveChain Consultant", version="1.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

AUTH_COOKIE_NAME = "wc_auth"


class StartSessionRequest(BaseModel):
    pain_point: str = Field(min_length=1, max_length=1500)


class SessionAnswerRequest(BaseModel):
    session_id: str
    answer: str = Field(min_length=1, max_length=2000)


class GenerateRequest(BaseModel):
    session_id: str


class FeedbackRequest(BaseModel):
    session_id: str
    feedback: str = Field(min_length=1, max_length=3000)


class RegisterRequest(BaseModel):
    name: str = Field(min_length=2, max_length=80)
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


class LoginRequest(BaseModel):
    email: str = Field(min_length=5, max_length=254)
    password: str = Field(min_length=8, max_length=128)


@dataclass
class GeneratedVersion:
    version: int
    created_at: str
    summary: str
    feature_list: list[str]
    files: dict[str, str]


@dataclass
class SessionState:
    session_id: str
    user_email: str
    pain_point: str
    questions: list[str]
    answers: list[str] = field(default_factory=list)
    versions: list[GeneratedVersion] = field(default_factory=list)


SESSIONS: dict[str, SessionState] = {}
USERS: dict[str, dict[str, str]] = {}
AUTH_SESSIONS: dict[str, str] = {}
DEMO_USER_EMAIL = "demo@solvechain.app"
DEMO_USER_PASSWORD = "demo@solvechain.app"
DEMO_USER_NAME = "Demo User"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower()).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned[:48] or "generated-webapp"


def _title_case_slug(slug: str) -> str:
    return " ".join(piece.capitalize() for piece in slug.split("-") if piece)


def _is_valid_email(email: str) -> bool:
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def _hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


@app.on_event("startup")
async def seed_demo_user() -> None:
    if DEMO_USER_EMAIL not in USERS:
        USERS[DEMO_USER_EMAIL] = {
            "name": DEMO_USER_NAME,
            "email": DEMO_USER_EMAIL,
            "password_hash": _hash_password(DEMO_USER_PASSWORD),
            "created_at": _now_iso(),
        }


def _set_auth_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        key=AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        secure=False,
        samesite="lax",
        max_age=60 * 60 * 24 * 14,
    )


def _clear_auth_cookie(response: Response) -> None:
    response.delete_cookie(AUTH_COOKIE_NAME)


def _current_user(request: Request) -> dict[str, str] | None:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if not token:
        return None
    email = AUTH_SESSIONS.get(token)
    if not email:
        return None
    return USERS.get(email)


def _require_user(request: Request) -> dict[str, str]:
    user = _current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def _owned_session(session_id: str, user_email: str) -> SessionState:
    state = SESSIONS.get(session_id)
    if not state or state.user_email != user_email:
        raise HTTPException(status_code=404, detail="Session not found")
    return state


def _owned_version(state: SessionState, version: int) -> GeneratedVersion:
    match = next((item for item in state.versions if item.version == version), None)
    if not match:
        raise HTTPException(status_code=404, detail="Version not found")
    return match


def _build_version_ideas(
    session_id: str, version: int, version_obj: GeneratedVersion
) -> list[dict[str, str]]:
    base_titles = list(version_obj.feature_list)
    if len(base_titles) < 6:
        base_titles.extend(
            [
                "Workflow intake and triage",
                "Task orchestration and ownership",
                "Approval and escalation workflow",
                "Operational reporting cockpit",
            ]
        )

    blueprints = [
        {
            "team": "Operations + Team Leads",
            "timeline": "2-3 weeks",
            "impact": "Cuts cycle time on recurring work by 30-45%.",
            "confidence": "High confidence",
            "function": "Consolidates recurring requests in one queue with ownership, due dates, and escalation guards.",
            "rationale": "Multiple employees reported the same blocker pattern, so centralizing intake unlocks immediate throughput.",
        },
        {
            "team": "Support + Backoffice",
            "timeline": "3-4 weeks",
            "impact": "Reduces backlog spillover and missed SLAs.",
            "confidence": "Medium-high confidence",
            "function": "Routes incoming work by urgency and topic, then enforces SLA-aware ownership handoffs.",
            "rationale": "Pain points were repeated in several interviews and tied to customer-facing delays.",
        },
        {
            "team": "Finance Ops + Managers",
            "timeline": "4-5 weeks",
            "impact": "Improves approval speed and audit traceability.",
            "confidence": "Medium confidence",
            "function": "Adds decision checkpoints, approval states, and clear history for each requested action.",
            "rationale": "Teams described avoidable approval bottlenecks and unclear accountability for pending decisions.",
        },
        {
            "team": "People Ops + Department Leads",
            "timeline": "2-4 weeks",
            "impact": "Shortens onboarding and reduces repetitive follow-up.",
            "confidence": "High confidence",
            "function": "Turns onboarding/onboarding-like workflows into guided checklists with owner reminders.",
            "rationale": "Interview data shows repeated process gaps for new hires and cross-team setup work.",
        },
        {
            "team": "Project Office + Executives",
            "timeline": "3-5 weeks",
            "impact": "Gives a single live view of progress, risk, and blockers.",
            "confidence": "Medium-high confidence",
            "function": "Builds a control tower dashboard for project health, delays, and risk concentration.",
            "rationale": "Stakeholders asked for one source of truth instead of fragmented status reporting.",
        },
        {
            "team": "Sales Ops + RevOps",
            "timeline": "3-4 weeks",
            "impact": "Improves handoff quality and conversion consistency.",
            "confidence": "Medium confidence",
            "function": "Standardizes lead/opportunity transitions and enforces required context at each stage.",
            "rationale": "Several users reported dropped context between teams leading to rework and delays.",
        },
        {
            "team": "Compliance + Operations",
            "timeline": "4-6 weeks",
            "impact": "Lowers compliance risk and manual audit effort.",
            "confidence": "Medium confidence",
            "function": "Introduces policy checks and evidence capture directly in the operational workflow.",
            "rationale": "Teams flagged high-risk manual steps and weak traceability across process exceptions.",
        },
        {
            "team": "Knowledge Team + Practitioners",
            "timeline": "2-3 weeks",
            "impact": "Reduces repeated questions and context switching.",
            "confidence": "High confidence",
            "function": "Captures recurring operational decisions and links them to reusable playbooks.",
            "rationale": "Interview synthesis surfaced repeated confusion around process edge-cases and ownership.",
        },
    ]

    ideas: list[dict[str, str]] = []
    for idx, title in enumerate(base_titles[:8]):
        blueprint = blueprints[idx % len(blueprints)]
        importance = max(6, 9 - (idx % 4))  # 9..6
        feasibility = max(5, 8 - (idx % 4))  # 8..5
        importance_stars = "★" * max(1, round(importance / 2)) + "☆" * (
            5 - max(1, round(importance / 2))
        )
        feasibility_stars = "★" * max(1, round(feasibility / 2)) + "☆" * (
            5 - max(1, round(feasibility / 2))
        )
        low = 2800 + (idx * 1250)
        high = low + 3400 + (idx * 180)
        function = (
            f"{blueprint['function']} In this case, the core module centers on {title.lower()}."
        )
        rationale = blueprint["rationale"]
        ideas.append(
            {
                "id": str(idx),
                "title": title,
                "importance": f"{importance}/10",
                "feasibility": f"{feasibility}/10",
                "importance_stars": importance_stars,
                "feasibility_stars": feasibility_stars,
                "price": f"${low:,} - ${high:,}",
                "function": function,
                "rationale": rationale,
                "team": blueprint["team"],
                "timeline": blueprint["timeline"],
                "impact": blueprint["impact"],
                "confidence": blueprint["confidence"],
                "app_url": f"/preview/{session_id}/{version}/app/?idea={idx}",
            }
        )
    return ideas


def _extract_focus(pain_point: str, answers: list[str]) -> str:
    source = " ".join([pain_point, *answers]).lower()
    mapping = {
        "booking": "booking workflow",
        "appointment": "appointment scheduling",
        "ticket": "support ticket handling",
        "support": "support operations",
        "inventory": "inventory tracking",
        "invoice": "invoicing",
        "crm": "lead and client tracking",
        "onboard": "onboarding flow",
        "content": "content publishing",
        "event": "event coordination",
        "task": "task execution",
        "project": "project operations",
        "sales": "sales pipeline",
    }
    for key, value in mapping.items():
        if key in source:
            return value
    return "internal operations"


def _extract_features(
    pain_point: str, answers: list[str], feedback: str | None = None
) -> list[str]:
    text = " ".join([pain_point, *answers, feedback or ""]).lower()
    features: list[str] = []

    feature_map = {
        "auth": "Simple role-based login",
        "login": "Simple role-based login",
        "email": "Email-ready notification hooks",
        "notify": "Notification center",
        "dashboard": "Operational dashboard",
        "search": "Global search and filters",
        "analytics": "Basic analytics cards",
        "report": "CSV export/reporting endpoint",
        "mobile": "Mobile-friendly responsive UI",
        "approval": "Approval workflow states",
        "calendar": "Calendar-style planning view",
        "integration": "External integration placeholder",
        "api": "Documented API routes",
    }

    for token, feature in feature_map.items():
        if token in text and feature not in features:
            features.append(feature)

    base = [
        "Centralized data capture form",
        "List view with status tags",
        "Priority queue for urgent items",
        "Editable detail panel",
        "Health endpoint for monitoring",
    ]
    for item in base:
        if item not in features:
            features.append(item)

    return features[:8]


def _follow_up_questions(pain_point: str) -> list[str]:
    lowered = pain_point.lower()
    questions = [
        "Who are the primary users and what role do they play?",
        "What is the exact workflow today, and where does friction happen most often?",
        "What are the top 3 must-have actions the first version needs?",
        "How will you measure success 30 days after launch?",
        "Any constraints (security, integrations, deployment, or compliance)?",
    ]

    if any(token in lowered for token in ["booking", "appointment", "calendar"]):
        questions.insert(2, "Do you need conflict detection and rescheduling rules?")
    if any(token in lowered for token in ["support", "ticket", "issue"]):
        questions.insert(
            2, "How should ticket priority, ownership, and SLAs be handled?"
        )
    if any(token in lowered for token in ["sales", "lead", "crm"]):
        questions.insert(2, "Which stages should opportunities move through?")

    return questions[:6]


def _consultant_summary(
    state: SessionState, focus: str, features: list[str], version: int
) -> str:
    answer_blob = " ".join(state.answers).strip()
    excerpt = answer_blob[:200] + ("..." if len(answer_blob) > 200 else "")
    return (
        f"v{version} targets {focus}. Pain point: {state.pain_point[:180]}"
        f"{'...' if len(state.pain_point) > 180 else ''}. "
        f"Answers considered: {excerpt or 'n/a'}."
    )


def _build_generated_fastapi_files(
    app_slug: str,
    app_title: str,
    summary: str,
    features: list[str],
    mock_variant: str = "ops",
    mock_subtitle: str = "Interactive mockup generated from interview synthesis.",
) -> dict[str, str]:
    feature_bullets = "\n".join(f"- {item}" for item in features)
    cards_json = ",\n".join(
        textwrap.indent(
            textwrap.dedent(
                f"""{{
    id: \"card-{idx + 1}\",
    title: \"{item}\",
    status: \"Active\",
    owner: \"Ops\"
}}"""
            ).strip(),
            "    ",
        )
        for idx, item in enumerate(features[:5])
    )

    main_py = (
        textwrap.dedent(
            f"""
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from fastapi.staticfiles import StaticFiles
        from fastapi.templating import Jinja2Templates

        app = FastAPI(title=\"{app_title}\", version=\"0.1.0\")

        app.mount(\"/static\", StaticFiles(directory=\"static\"), name=\"static\")
        templates = Jinja2Templates(directory=\"templates\")


        @app.get(\"/\")
        async def index(request: Request):
            return templates.TemplateResponse(\"index.html\", {{\"request\": request}})


        @app.get(\"/api/health\")
        async def health():
            return JSONResponse({{\"ok\": True, \"service\": \"{app_slug}\"}})


        @app.get(\"/api/cards\")
        async def cards():
            return JSONResponse(
                [
        {cards_json}
                ]
            )
        """
        ).strip()
        + "\n"
    )

    html = (
        textwrap.dedent(
            f"""
        <!doctype html>
        <html lang=\"en\">
        <head>
          <meta charset=\"utf-8\" />
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
          <title>{app_title}</title>
          <link rel=\"stylesheet\" href=\"./static/styles.css\" />
        </head>
        <body class=\"mock-{mock_variant}\">
          <header class=\"banner\">SolveChain Prototype</header>
          <main class=\"shell\">
            <section class=\"top\">
              <div>
                <h1 id=\"app-title\">{app_title}</h1>
                <p class=\"sub\">{mock_subtitle}</p>
              </div>
              <div class=\"kpi-grid\">
                <article class=\"kpi\"><span>Open items</span><strong id=\"kpi-open\">0</strong></article>
                <article class=\"kpi\"><span>At risk</span><strong id=\"kpi-risk\">0</strong></article>
                <article class=\"kpi\"><span>Healthy</span><strong id=\"kpi-healthy\">0</strong></article>
              </div>
            </section>

            <section class=\"workspace\">
              <article class=\"panel\">
                <h2>New Request</h2>
                <form id=\"entry-form\" class=\"stack\">
                  <input id=\"entry-title\" placeholder=\"What needs to be solved?\" required />
                  <div class=\"row\">
                    <input id=\"entry-owner\" placeholder=\"Owner\" required />
                    <select id=\"entry-priority\">
                      <option>P1</option>
                      <option selected>P2</option>
                      <option>P3</option>
                    </select>
                  </div>
                  <button type=\"submit\">Add to queue</button>
                </form>
              </article>

              <article class=\"panel\">
                <h2>Live Queue</h2>
                <div id=\"cards\" class=\"cards\"></div>
              </article>
            </section>
          </main>
          <script src=\"./static/app.js\"></script>
        </body>
        </html>
        """
        ).strip()
        + "\n"
    )

    css = (
        textwrap.dedent(
            """
        :root {
          --bg: #f4f7fb;
          --panel: #ffffff;
          --line: #dfe7f4;
          --text: #1f2a37;
          --brand: #0f766e;
        }

        * { box-sizing: border-box; }
        body {
          margin: 0;
          font-family: "Avenir Next", "Segoe UI", sans-serif;
          color: var(--text);
          background: radial-gradient(circle at 0 0, #d7f3ef, transparent 45%), var(--bg);
        }

        body.mock-support {
          --brand: #1d4ed8;
          background: radial-gradient(circle at 0 0, #dbeafe, transparent 45%), var(--bg);
        }

        body.mock-approval {
          --brand: #b45309;
          background: radial-gradient(circle at 0 0, #ffedd5, transparent 45%), var(--bg);
        }

        body.mock-onboarding {
          --brand: #0f766e;
          background: radial-gradient(circle at 0 0, #ccfbf1, transparent 45%), var(--bg);
        }

        body.mock-insights {
          --brand: #0f4c81;
          background: radial-gradient(circle at 0 0, #e0ecff, transparent 45%), var(--bg);
        }

        .banner {
          position: fixed;
          top: 0;
          left: 0;
          right: 0;
          z-index: 10;
          min-height: 64px;
          display: flex;
          align-items: center;
          padding: .8rem 1rem;
          color: #fff;
          font-weight: 800;
          font-size: 1.05rem;
          background: linear-gradient(90deg, #071427, var(--brand));
        }

        .shell {
          max-width: 1120px;
          margin: 5.2rem auto 2rem;
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 16px;
          padding: 1.25rem;
          box-shadow: 0 20px 60px rgba(15, 23, 42, 0.08);
        }

        h1, h2 { margin: 0 0 .75rem; }
        p { margin: 0 0 1rem; line-height: 1.4; }
        .sub { color: #4b5563; margin: 0; }

        .top {
          display: grid;
          grid-template-columns: 1.2fr 1fr;
          gap: .85rem;
          align-items: start;
          margin-bottom: 1rem;
        }

        .kpi-grid {
          display: grid;
          grid-template-columns: repeat(3, minmax(0, 1fr));
          gap: .6rem;
        }

        .kpi {
          border: 1px solid var(--line);
          border-radius: 12px;
          background: #fff;
          padding: .55rem .65rem;
        }

        .kpi span {
          display: block;
          font-size: .78rem;
          color: #64748b;
        }

        .kpi strong {
          font-size: 1.2rem;
          color: var(--brand);
        }

        .workspace {
          display: grid;
          grid-template-columns: 340px 1fr;
          gap: .8rem;
        }

        .panel {
          border: 1px solid var(--line);
          border-radius: 12px;
          background: #fff;
          padding: .75rem;
          box-shadow: 0 10px 28px rgba(15, 23, 42, 0.05);
        }

        .stack {
          display: grid;
          gap: .55rem;
        }

        .row {
          display: grid;
          grid-template-columns: 1fr 98px;
          gap: .5rem;
        }

        input, select, button {
          font: inherit;
        }

        input, select {
          width: 100%;
          border: 1px solid var(--line);
          border-radius: 8px;
          padding: .58rem .62rem;
          background: #fff;
        }

        button {
          border: 0;
          border-radius: 9px;
          padding: .6rem .8rem;
          color: white;
          cursor: pointer;
          font-weight: 700;
          background: linear-gradient(130deg, var(--brand), #0f766e);
        }

        .cards {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
          gap: .75rem;
        }

        .card {
          border: 1px solid var(--line);
          border-radius: 12px;
          padding: .75rem;
          background: #fff;
        }

        .status {
          display: inline-flex;
          align-items: center;
          border-radius: 999px;
          padding: .15rem .5rem;
          font-size: .75rem;
          font-weight: 700;
          margin-bottom: .45rem;
        }

        .status.healthy,
        .status.ready {
          background: #dcfce7;
          color: #166534;
        }

        .status.in-progress,
        .status.monitoring {
          background: #dbeafe;
          color: #1e40af;
        }

        .status.at-risk {
          background: #fee2e2;
          color: #991b1b;
        }

        .meta-grid {
          margin-top: .4rem;
          display: grid;
          grid-template-columns: 1fr 1fr;
          gap: .3rem .5rem;
        }

        .muted {
          color: #4b5563;
          font-size: .9rem;
        }

        @media (max-width: 980px) {
          .top,
          .workspace {
            grid-template-columns: 1fr;
          }
        }
        """
        ).strip()
        + "\n"
    )

    js = (
        textwrap.dedent(
            """
        function updateKpis(cards) {
          const open = cards.length;
          const risk = cards.filter(card => String(card.status || '').toLowerCase() === 'at risk').length;
          const healthy = cards.filter(card => ['healthy', 'ready', 'in progress'].includes(String(card.status || '').toLowerCase())).length;

          document.getElementById('kpi-open').textContent = String(open);
          document.getElementById('kpi-risk').textContent = String(risk);
          document.getElementById('kpi-healthy').textContent = String(healthy);
        }

        function renderCards(cards) {
          const host = document.getElementById('cards');

          const statusClass = (status) =>
            String(status || '')
              .toLowerCase()
              .replace(/\\s+/g, '-');

          host.innerHTML = cards.map(card => `
            <article class="card">
              <span class="status ${statusClass(card.status)}">${card.status || 'Active'}</span>
              <strong>${card.title}</strong>
              <div class="meta-grid">
                <p class="muted">Owner: ${card.owner || 'Team'}</p>
                <p class="muted">Priority: ${card.priority || 'P2'}</p>
                <p class="muted">SLA: ${card.sla || 'n/a'}</p>
                <p class="muted">ID: ${card.id}</p>
              </div>
            </article>
          `).join('');

          updateKpis(cards);
        }

        async function run() {
          const res = await fetch('./api/cards' + window.location.search);
          const cards = await res.json();
          renderCards(cards);

          const form = document.getElementById('entry-form');
          const titleInput = document.getElementById('entry-title');
          const ownerInput = document.getElementById('entry-owner');
          const priorityInput = document.getElementById('entry-priority');

          form.addEventListener('submit', (event) => {
            event.preventDefault();
            const title = titleInput.value.trim();
            const owner = ownerInput.value.trim();
            const priority = priorityInput.value.trim();
            if (!title || !owner) return;

            const item = {
              id: `local-${Date.now()}`,
              title,
              status: 'In progress',
              owner,
              priority,
              sla: priority === 'P1' ? '4h' : priority === 'P2' ? '24h' : 'Weekly',
            };
            cards.unshift(item);
            renderCards(cards);
            form.reset();
          });
        }

        run().catch(err => {
          console.error(err);
        });
        """
        ).strip()
        + "\n"
    )

    readme = (
        textwrap.dedent(
            f"""
        # {app_title}

        Generated by SolveChain Consultant.

        ## Summary
        {summary}

        ## Included Features
        {feature_bullets}

        ## Run
        ```bash
        pip install -r requirements.txt
        uvicorn main:app --reload
        ```
        """
        ).strip()
        + "\n"
    )

    requirements = "fastapi==0.115.14\nuvicorn==0.30.6\njinja2==3.1.4\n\n"

    return {
        "main.py": main_py,
        "templates/index.html": html,
        "static/styles.css": css,
        "static/app.js": js,
        "README.md": readme,
        "requirements.txt": requirements,
    }


def _next_version(state: SessionState, feedback: str | None = None) -> GeneratedVersion:
    version = len(state.versions) + 1
    focus = _extract_focus(state.pain_point, state.answers)
    features = _extract_features(state.pain_point, state.answers, feedback)

    if feedback:
        features = [f"Feedback-adjusted: {feedback[:72]}"] + [
            item for item in features if not item.startswith("Feedback-adjusted:")
        ]
        features = features[:8]

    app_slug = _slugify(f"{focus}-{state.session_id[:8]}-v{version}")
    app_title = f"{focus.title()} Workspace v{version}"
    summary = _consultant_summary(state, focus, features, version)
    files = _build_generated_fastapi_files(app_slug, app_title, summary, features)

    generated = GeneratedVersion(
        version=version,
        created_at=_now_iso(),
        summary=summary,
        feature_list=features,
        files=files,
    )
    state.versions.append(generated)
    return generated


def _pack_version_as_zip(version_obj: GeneratedVersion) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path, content in version_obj.files.items():
            zf.writestr(path, content)
    buffer.seek(0)
    return buffer.getvalue()


def _mock_variant_for_title(title: str) -> tuple[str, str]:
    lowered = title.lower()
    if any(token in lowered for token in ["support", "ticket", "triage"]):
        return "support", "Support-focused workspace with SLA-aware triage and routing."
    if any(token in lowered for token in ["approval", "compliance", "escalation"]):
        return (
            "approval",
            "Decision workflow view with escalation and approval accountability.",
        )
    if any(token in lowered for token in ["onboarding", "onboard", "setup"]):
        return (
            "onboarding",
            "Guided onboarding workflow with ownership and completion tracking.",
        )
    return "insights", "Operational workspace with live queue and performance indicators."


def _runtime_preview_files(
    state: SessionState,
    version_obj: GeneratedVersion,
    app_title_override: str | None = None,
    mock_variant: str = "ops",
    mock_subtitle: str = "Interactive mockup generated from interview synthesis.",
) -> dict[str, str]:
    focus = _extract_focus(state.pain_point, state.answers)
    app_slug = _slugify(f"{focus}-{state.session_id[:8]}-v{version_obj.version}")
    app_title = app_title_override or f"{focus.title()} Workspace v{version_obj.version}"
    return _build_generated_fastapi_files(
        app_slug,
        app_title,
        version_obj.summary,
        version_obj.feature_list,
        mock_variant=mock_variant,
        mock_subtitle=mock_subtitle,
    )


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    user = _current_user(request)
    return templates.TemplateResponse("index.html", {"request": request, "user": user})


@app.get("/consultant", response_class=HTMLResponse)
async def consultant(request: Request) -> HTMLResponse:
    user = _current_user(request)
    if not user:
        return RedirectResponse(url="/#auth", status_code=303)
    return templates.TemplateResponse(
        "consultant.html", {"request": request, "user": user}
    )


@app.get("/preview/{session_id}/{version}", response_class=HTMLResponse)
async def preview_workspace(
    request: Request, session_id: str, version: int
) -> HTMLResponse:
    user = _current_user(request)
    if not user:
        return RedirectResponse(url="/#auth", status_code=303)

    state = _owned_session(session_id, user["email"])
    match = _owned_version(state, version)
    ideas = _build_version_ideas(session_id, version, match)
    default_app_url = ideas[0]["app_url"] if ideas else f"/preview/{session_id}/{version}/app/"
    return templates.TemplateResponse(
        "preview.html",
        {
            "request": request,
            "session_id": session_id,
            "version": version,
            "summary": match.summary,
            "features": match.feature_list,
            "app_url": default_app_url,
            "ideas": ideas,
        },
    )


@app.get("/preview/{session_id}/{version}/app/", response_class=HTMLResponse)
async def preview_app_index(
    request: Request, session_id: str, version: int
) -> HTMLResponse:
    user = _require_user(request)
    state = _owned_session(session_id, user["email"])
    match = _owned_version(state, version)

    idea_idx_raw = request.query_params.get("idea", "0")
    try:
        idea_idx = max(0, int(idea_idx_raw))
    except ValueError:
        idea_idx = 0

    ideas = _build_version_ideas(session_id, version, match)
    selected = ideas[min(idea_idx, len(ideas) - 1)] if ideas else None
    selected_title = selected["title"] if selected else f"Workspace v{version}"
    mock_variant, mock_subtitle = _mock_variant_for_title(selected_title)

    runtime_files = _runtime_preview_files(
        state,
        match,
        app_title_override=selected_title,
        mock_variant=mock_variant,
        mock_subtitle=mock_subtitle,
    )
    html = runtime_files.get("templates/index.html")
    if not html:
        html = match.files.get("templates/index.html")
    if not html:
        raise HTTPException(status_code=404, detail="Generated app index missing")
    return HTMLResponse(content=html)


@app.get("/preview/{session_id}/{version}/app/static/{asset_path:path}")
async def preview_app_static(
    request: Request, session_id: str, version: int, asset_path: str
) -> Response:
    user = _require_user(request)
    state = _owned_session(session_id, user["email"])
    match = _owned_version(state, version)
    key = f"static/{asset_path}"
    runtime_files = _runtime_preview_files(state, match)
    content = runtime_files.get(key)
    if content is None:
        content = match.files.get(key)
    if content is None:
        raise HTTPException(status_code=404, detail="Generated static asset not found")

    media_type = "text/plain"
    if asset_path.endswith(".css"):
        media_type = "text/css"
    elif asset_path.endswith(".js"):
        media_type = "application/javascript"
    elif asset_path.endswith(".html"):
        media_type = "text/html"
    return Response(content=content, media_type=media_type)


@app.get("/preview/{session_id}/{version}/app/api/cards")
async def preview_app_cards(
    request: Request, session_id: str, version: int
) -> list[dict[str, str]]:
    user = _require_user(request)
    state = _owned_session(session_id, user["email"])
    match = _owned_version(state, version)

    idea_idx_raw = request.query_params.get("idea", "0")
    try:
        idea_idx = max(0, int(idea_idx_raw))
    except ValueError:
        idea_idx = 0

    ideas = _build_version_ideas(session_id, version, match)
    selected = ideas[min(idea_idx, len(ideas) - 1)] if ideas else None
    selected_title = selected["title"] if selected else "Core workflow"
    selected_team = selected["team"] if selected else "Operations"
    idea_text = selected_title.lower()

    if any(token in idea_text for token in ["approval", "escalation", "compliance"]):
        cards = [
            {
                "id": "card-1",
                "title": "Pending approvals older than 48h",
                "status": "At risk",
                "owner": "Finance Lead",
                "priority": "P1",
                "sla": "8h",
            },
            {
                "id": "card-2",
                "title": "Escalation queue for blocked requests",
                "status": "In progress",
                "owner": "Ops Manager",
                "priority": "P1",
                "sla": "4h",
            },
            {
                "id": "card-3",
                "title": "Audit trail completeness",
                "status": "Healthy",
                "owner": "Compliance",
                "priority": "P2",
                "sla": "24h",
            },
            {
                "id": "card-4",
                "title": "Decision latency by approver",
                "status": "Monitoring",
                "owner": "Analytics",
                "priority": "P3",
                "sla": "Daily",
            },
        ]
    elif any(token in idea_text for token in ["support", "ticket", "triage"]):
        cards = [
            {
                "id": "card-1",
                "title": "Urgent ticket triage lane",
                "status": "In progress",
                "owner": "Support Manager",
                "priority": "P1",
                "sla": "2h",
            },
            {
                "id": "card-2",
                "title": "Reassignment due to missing context",
                "status": "At risk",
                "owner": "Backoffice",
                "priority": "P2",
                "sla": "6h",
            },
            {
                "id": "card-3",
                "title": "First-response compliance",
                "status": "Healthy",
                "owner": "QA",
                "priority": "P2",
                "sla": "95% target",
            },
            {
                "id": "card-4",
                "title": "Automation candidate cluster",
                "status": "Ready",
                "owner": "Product Ops",
                "priority": "P3",
                "sla": "Weekly",
            },
        ]
    elif any(token in idea_text for token in ["onboarding", "onboard"]):
        cards = [
            {
                "id": "card-1",
                "title": "New-hire setup checklist",
                "status": "In progress",
                "owner": "People Ops",
                "priority": "P1",
                "sla": "Day 1",
            },
            {
                "id": "card-2",
                "title": "Access provisioning blockers",
                "status": "At risk",
                "owner": "IT Ops",
                "priority": "P1",
                "sla": "4h",
            },
            {
                "id": "card-3",
                "title": "Manager intro completion",
                "status": "Healthy",
                "owner": "Department Leads",
                "priority": "P2",
                "sla": "Week 1",
            },
            {
                "id": "card-4",
                "title": "Training milestone completion",
                "status": "Monitoring",
                "owner": "Enablement",
                "priority": "P3",
                "sla": "Week 2",
            },
        ]
    else:
        cards = [
            {
                "id": "card-1",
                "title": selected_title,
                "status": "In progress",
                "owner": selected_team,
                "priority": "P1",
                "sla": "Same day",
            },
            {
                "id": "card-2",
                "title": "High-friction workflow cluster",
                "status": "At risk",
                "owner": "Ops Excellence",
                "priority": "P1",
                "sla": "24h",
            },
            {
                "id": "card-3",
                "title": "Cross-team handoff quality",
                "status": "Monitoring",
                "owner": "Program Manager",
                "priority": "P2",
                "sla": "Weekly",
            },
            {
                "id": "card-4",
                "title": "Automation rollout candidates",
                "status": "Ready",
                "owner": "Platform Team",
                "priority": "P2",
                "sla": "Next sprint",
            },
        ]
    return cards


@app.post("/api/auth/register")
async def register(payload: RegisterRequest, response: Response) -> dict[str, Any]:
    email = payload.email.lower().strip()
    if not _is_valid_email(email):
        raise HTTPException(status_code=422, detail="Invalid email")
    if email in USERS:
        raise HTTPException(status_code=409, detail="Account already exists")

    USERS[email] = {
        "name": payload.name.strip(),
        "email": email,
        "password_hash": _hash_password(payload.password),
        "created_at": _now_iso(),
    }
    token = str(uuid.uuid4())
    AUTH_SESSIONS[token] = email
    _set_auth_cookie(response, token)

    return {"ok": True, "name": USERS[email]["name"], "email": email}


@app.post("/api/auth/login")
async def login(payload: LoginRequest, response: Response) -> dict[str, Any]:
    email = payload.email.lower().strip()
    if not _is_valid_email(email):
        raise HTTPException(status_code=422, detail="Invalid email")
    user = USERS.get(email)
    if not user or user["password_hash"] != _hash_password(payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = str(uuid.uuid4())
    AUTH_SESSIONS[token] = email
    _set_auth_cookie(response, token)

    return {"ok": True, "name": user["name"], "email": user["email"]}


@app.post("/api/auth/logout")
async def logout(request: Request, response: Response) -> dict[str, bool]:
    token = request.cookies.get(AUTH_COOKIE_NAME)
    if token:
        AUTH_SESSIONS.pop(token, None)
    _clear_auth_cookie(response)
    return {"ok": True}


@app.get("/api/auth/me")
async def auth_me(request: Request) -> dict[str, Any]:
    user = _current_user(request)
    if not user:
        return {"authenticated": False}
    return {
        "authenticated": True,
        "name": user["name"],
        "email": user["email"],
    }


@app.post("/api/session/start")
async def start_session(
    payload: StartSessionRequest, request: Request
) -> dict[str, Any]:
    user = _require_user(request)
    session_id = str(uuid.uuid4())
    questions = _follow_up_questions(payload.pain_point)
    state = SessionState(
        session_id=session_id,
        user_email=user["email"],
        pain_point=payload.pain_point,
        questions=questions,
    )
    SESSIONS[session_id] = state

    return {
        "session_id": session_id,
        "question_index": 0,
        "question": questions[0],
        "remaining": len(questions) - 1,
    }


@app.post("/api/session/answer")
async def answer_question(
    payload: SessionAnswerRequest, request: Request
) -> dict[str, Any]:
    user = _require_user(request)
    state = _owned_session(payload.session_id, user["email"])

    if len(state.answers) >= len(state.questions):
        return {
            "done": True,
            "message": "Discovery complete. Generate your first app version.",
        }

    state.answers.append(payload.answer)
    next_index = len(state.answers)

    if next_index >= len(state.questions):
        return {
            "done": True,
            "message": "Discovery complete. Generate your first app version.",
        }

    return {
        "done": False,
        "question_index": next_index,
        "question": state.questions[next_index],
        "remaining": len(state.questions) - (next_index + 1),
    }


@app.post("/api/generate")
async def generate_version(
    payload: GenerateRequest, request: Request
) -> dict[str, Any]:
    user = _require_user(request)
    state = _owned_session(payload.session_id, user["email"])

    if len(state.answers) < len(state.questions):
        raise HTTPException(
            status_code=400, detail="Please complete discovery questions first"
        )

    version_obj = _next_version(state)
    return {
        "version": version_obj.version,
        "created_at": version_obj.created_at,
        "summary": version_obj.summary,
        "features": version_obj.feature_list,
        "files": sorted(version_obj.files.keys()),
        "preview_url": f"/preview/{state.session_id}/{version_obj.version}",
        "next_step": "Open the live preview, test it, then submit feedback to generate the next version.",
    }


@app.post("/api/feedback")
async def feedback_loop(payload: FeedbackRequest, request: Request) -> dict[str, Any]:
    user = _require_user(request)
    state = _owned_session(payload.session_id, user["email"])

    if not state.versions:
        raise HTTPException(
            status_code=400, detail="Generate a version before feedback"
        )

    version_obj = _next_version(state, feedback=payload.feedback)
    return {
        "version": version_obj.version,
        "created_at": version_obj.created_at,
        "summary": version_obj.summary,
        "features": version_obj.feature_list,
        "files": sorted(version_obj.files.keys()),
        "preview_url": f"/preview/{state.session_id}/{version_obj.version}",
        "next_step": "Open the live preview, test it, then submit feedback to generate the next version.",
    }


@app.get("/api/session/{session_id}")
async def session_status(session_id: str, request: Request) -> dict[str, Any]:
    user = _require_user(request)
    state = _owned_session(session_id, user["email"])

    return {
        "session_id": state.session_id,
        "pain_point": state.pain_point,
        "questions": state.questions,
        "answers": state.answers,
        "versions": [
            {
                "version": version.version,
                "created_at": version.created_at,
                "summary": version.summary,
                "features": version.feature_list,
                "preview_url": f"/preview/{state.session_id}/{version.version}",
            }
            for version in state.versions
        ],
    }


@app.get("/api/version/download")
async def download_version(
    session_id: str, version: int, request: Request
) -> StreamingResponse:
    user = _require_user(request)
    state = _owned_session(session_id, user["email"])
    match = _owned_version(state, version)

    archive = _pack_version_as_zip(match)
    filename = f"generated-fastapi-v{version}.zip"

    return StreamingResponse(
        io.BytesIO(archive),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
