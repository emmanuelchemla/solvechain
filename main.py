from __future__ import annotations

import io
import re
import textwrap
import uuid
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from starlette.requests import Request


app = FastAPI(title="Webapp Consultant", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


class StartSessionRequest(BaseModel):
    pain_point: str = Field(min_length=10, max_length=1500)


class SessionAnswerRequest(BaseModel):
    session_id: str
    answer: str = Field(min_length=1, max_length=2000)


class GenerateRequest(BaseModel):
    session_id: str


class FeedbackRequest(BaseModel):
    session_id: str
    feedback: str = Field(min_length=3, max_length=3000)


class DownloadRequest(BaseModel):
    session_id: str
    version: int


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
    pain_point: str
    questions: list[str]
    answers: list[str] = field(default_factory=list)
    versions: list[GeneratedVersion] = field(default_factory=list)


SESSIONS: dict[str, SessionState] = {}


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _slugify(text: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9\s-]", "", text.lower()).strip()
    cleaned = re.sub(r"\s+", "-", cleaned)
    return cleaned[:48] or "generated-webapp"


def _title_case_slug(slug: str) -> str:
    return " ".join(piece.capitalize() for piece in slug.split("-") if piece)


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


def _extract_features(pain_point: str, answers: list[str], feedback: str | None = None) -> list[str]:
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
        questions.insert(2, "How should ticket priority, ownership, and SLAs be handled?")
    if any(token in lowered for token in ["sales", "lead", "crm"]):
        questions.insert(2, "Which stages should opportunities move through?")

    return questions[:6]


def _consultant_summary(state: SessionState, focus: str, features: list[str], version: int) -> str:
    answer_blob = " ".join(state.answers).strip()
    excerpt = answer_blob[:200] + ("..." if len(answer_blob) > 200 else "")
    return (
        f"v{version} targets {focus}. Pain point: {state.pain_point[:180]}"
        f"{'...' if len(state.pain_point) > 180 else ''}. "
        f"Answers considered: {excerpt or 'n/a'}."
    )


def _build_generated_fastapi_files(app_slug: str, app_title: str, summary: str, features: list[str]) -> dict[str, str]:
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

    main_py = textwrap.dedent(
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
    ).strip() + "\n"

    html = textwrap.dedent(
        f"""
        <!doctype html>
        <html lang=\"en\">
        <head>
          <meta charset=\"utf-8\" />
          <meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
          <title>{app_title}</title>
          <link rel=\"stylesheet\" href=\"/static/styles.css\" />
        </head>
        <body>
          <main class=\"shell\">
            <header>
              <h1>{app_title}</h1>
              <p>{summary}</p>
            </header>
            <section>
              <h2>Feature Stack</h2>
              <ul>
                {''.join(f'<li>{feature}</li>' for feature in features)}
              </ul>
            </section>
            <section>
              <h2>Live Queue</h2>
              <div id=\"cards\" class=\"cards\"></div>
            </section>
          </main>
          <script src=\"/static/app.js\"></script>
        </body>
        </html>
        """
    ).strip() + "\n"

    css = textwrap.dedent(
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

        .shell {
          max-width: 980px;
          margin: 2rem auto;
          background: var(--panel);
          border: 1px solid var(--line);
          border-radius: 16px;
          padding: 1.25rem;
          box-shadow: 0 20px 60px rgba(15, 23, 42, 0.08);
        }

        h1, h2 { margin: 0 0 .75rem; }
        p { margin: 0 0 1rem; line-height: 1.4; }

        .cards {
          display: grid;
          grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
          gap: .75rem;
        }

        .card {
          border: 1px solid var(--line);
          border-radius: 12px;
          padding: .75rem;
          background: #fff;
        }

        .muted {
          color: #4b5563;
          font-size: .9rem;
        }
        """
    ).strip() + "\n"

    js = textwrap.dedent(
        """
        async function run() {
          const res = await fetch('/api/cards');
          const cards = await res.json();
          const host = document.getElementById('cards');

          host.innerHTML = cards.map(card => `
            <article class="card">
              <strong>${card.title}</strong>
              <p class="muted">Status: ${card.status}</p>
              <p class="muted">Owner: ${card.owner}</p>
            </article>
          `).join('');
        }

        run().catch(err => {
          console.error(err);
        });
        """
    ).strip() + "\n"

    readme = textwrap.dedent(
        f"""
        # {app_title}

        Generated by the Webapp Consultant.

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
    ).strip() + "\n"

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
        features = [
            f"Feedback-adjusted: {feedback[:72]}"
        ] + [item for item in features if not item.startswith("Feedback-adjusted:")]
        features = features[:8]

    app_slug = _slugify(f"{focus}-{state.session_id[:8]}-v{version}")
    app_title = _title_case_slug(app_slug)
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


@app.get("/", response_class=HTMLResponse)
async def index(request: Request) -> HTMLResponse:
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/api/session/start")
async def start_session(payload: StartSessionRequest) -> dict[str, Any]:
    session_id = str(uuid.uuid4())
    questions = _follow_up_questions(payload.pain_point)
    state = SessionState(session_id=session_id, pain_point=payload.pain_point, questions=questions)
    SESSIONS[session_id] = state

    return {
        "session_id": session_id,
        "question_index": 0,
        "question": questions[0],
        "remaining": len(questions) - 1,
    }


@app.post("/api/session/answer")
async def answer_question(payload: SessionAnswerRequest) -> dict[str, Any]:
    state = SESSIONS.get(payload.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

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
async def generate_version(payload: GenerateRequest) -> dict[str, Any]:
    state = SESSIONS.get(payload.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    if len(state.answers) < len(state.questions):
        raise HTTPException(status_code=400, detail="Please complete discovery questions first")

    version_obj = _next_version(state)
    return {
        "version": version_obj.version,
        "created_at": version_obj.created_at,
        "summary": version_obj.summary,
        "features": version_obj.feature_list,
        "files": sorted(version_obj.files.keys()),
        "download": f"/api/version/download?session_id={state.session_id}&version={version_obj.version}",
    }


@app.post("/api/feedback")
async def feedback_loop(payload: FeedbackRequest) -> dict[str, Any]:
    state = SESSIONS.get(payload.session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    if not state.versions:
        raise HTTPException(status_code=400, detail="Generate a version before feedback")

    version_obj = _next_version(state, feedback=payload.feedback)
    return {
        "version": version_obj.version,
        "created_at": version_obj.created_at,
        "summary": version_obj.summary,
        "features": version_obj.feature_list,
        "files": sorted(version_obj.files.keys()),
        "download": f"/api/version/download?session_id={state.session_id}&version={version_obj.version}",
    }


@app.get("/api/session/{session_id}")
async def session_status(session_id: str) -> dict[str, Any]:
    state = SESSIONS.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

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
            }
            for version in state.versions
        ],
    }


@app.get("/api/version/download")
async def download_version(session_id: str, version: int) -> StreamingResponse:
    state = SESSIONS.get(session_id)
    if not state:
        raise HTTPException(status_code=404, detail="Session not found")

    match = next((item for item in state.versions if item.version == version), None)
    if not match:
        raise HTTPException(status_code=404, detail="Version not found")

    archive = _pack_version_as_zip(match)
    filename = f"generated-fastapi-v{version}.zip"

    return StreamingResponse(
        io.BytesIO(archive),
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
