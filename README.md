# FastAPI Webapp Consultant

A FastAPI app that helps users create new FastAPI webapps through a guided workflow:

1. User describes a pain point.
2. Consultant app asks follow-up questions.
3. System generates a FastAPI webapp scaffold (version 1).
4. User gives feedback.
5. System generates a new FastAPI version.

Each generated version is downloadable as a ZIP project.

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open: http://127.0.0.1:8000
