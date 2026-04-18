# SolveChain - Discovery to Action

A consultant app to discover needs and build solutions:

- chat (web based or integrated in communication tools) about operations, pain-points, needs
- aggregation of the different users responses
- instant live app propositions with ratings
- immediate previews of app versions
- iterative feedback loop

## Run

```bash
pip install -r requirements.txt
uvicorn main:app --reload
```

Open `http://127.0.0.1:8000`.

## Notes

- Auth is intentionally lightweight and in-memory (for demo use).
- Generated app artifacts are also in-memory per running process.
