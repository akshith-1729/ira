"""Run one PDF or id through the API and print the result. Manual check, not a test."""

import sys
import time
from pathlib import Path

import httpx

API = "http://127.0.0.1:8000"

sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def main(target: str) -> int:
    client = httpx.Client(timeout=120.0)
    path = Path(target)
    if path.exists():
        with path.open("rb") as handle:
            response = client.post(
                f"{API}/papers/upload",
                files={"file": (path.name, handle, "application/pdf")},
            )
    else:
        response = client.post(f"{API}/papers/lookup", json={"openalex_id": target})
    response.raise_for_status()
    job_id = response.json()["job_id"]
    print("job", job_id, flush=True)

    last = None
    for _ in range(180):
        time.sleep(5)
        job = client.get(f"{API}/jobs/{job_id}").json()
        if job["progress"] != last:
            last = job["progress"]
            print(" ", job["status"], job["progress"], flush=True)
        if job["status"] in {"done", "error"}:
            break
    if job["status"] != "done":
        print("FAILED:", job.get("error"))
        return 1

    paper = client.get(f"{API}/papers/{job['paper_id']}").json()
    print("\nTITLE:", paper["title"])
    print("\nSUMMARY:\n", paper["summary"])
    print("\nCONTRIBUTIONS:")
    for item in paper["contributions"]:
        print(" -", item)
    print("\nTOPICS:", [topic["name"] for topic in paper["topics"]])
    print("KEYWORDS:", paper["keywords"])
    print("\nGAPS:")
    for gap in paper["gaps"]:
        print(" -", gap["statement"])
        print("   direction:", gap["direction"])
        for claim in gap["claims"]:
            print("   claim:", claim["text"], "->", claim["section"])
    print("\nVENUES:", [venue["name"] for venue in paper["recommended_venues"]])
    print("SIMILAR:", [row["paper"]["title"] for row in paper["recommended_papers"]])
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1]))
