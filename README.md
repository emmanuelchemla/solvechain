# ForgeFlow - FastAPI Webapp Consultant

This project includes:

1. A startup-style marketing website (`/`) with pitch, testimonials, process, packages, and company/about sections.
2. Register/Login experience for access control.
3. A protected consultant app (`/consultant`) that helps users create FastAPI webapps through:
   - pain-point input
   - follow-up discovery questions
   - generated app version 1
   - iterative feedback loop to generate new versions
4. ZIP download for each generated FastAPI version.

## Run

```bash
source ~/.venvs/autoapp/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Notes

- Auth is intentionally lightweight and in-memory (for demo use).
- Generated app artifacts are also in-memory per running process.
