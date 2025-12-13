import json
import os
from typing import Any


def _prompt_choice(title: str, options: list[str], allow_back: bool = True) -> int:
    """Return selected index, or -1 for back."""
    while True:
        print(f"\n{title}")
        print("-" * len(title))
        for i, opt in enumerate(options, start=1):
            print(f"{i}. {opt}")
        if allow_back:
            print("0. Back")

        raw = input("Select: ").strip()
        if allow_back and raw == "0":
            return -1
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(options):
                return idx
        print("Invalid choice.")


def _load_index(path: str) -> dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _format_job_line(job: dict[str, Any]) -> str:
    title = job.get("title") or "(no title)"
    company = job.get("company") or "(no company)"
    return f"{title} — {company}"


def browse_requirements_index(index_path: str) -> None:
    index = _load_index(index_path)
    term_index: dict[str, dict[str, list[int]]] = index.get("term_index", {})
    jobs: dict[str, dict[str, Any]] = index.get("jobs", {})

    categories = sorted(term_index.keys())
    if not categories:
        print("No categories found in index.")
        return

    while True:
        cat_idx = _prompt_choice("Requirement categories", categories, allow_back=False)
        category = categories[cat_idx]

        while True:
            terms_map = term_index.get(category, {}) or {}
            # Sort by count desc then alpha
            terms = sorted(terms_map.keys(), key=lambda t: (-len(terms_map.get(t, [])), t.lower()))

            if not terms:
                print(f"\nNo terms found for category: {category}")
                break

            term_labels = [f"{t} ({len(terms_map.get(t, []))})" for t in terms]
            term_idx = _prompt_choice(f"{category}: pick a term", term_labels, allow_back=True)
            if term_idx == -1:
                break

            term = terms[term_idx]
            job_ids = terms_map.get(term, [])
            job_cards = []
            for jid in job_ids:
                job = jobs.get(str(jid), {"id": jid})
                job_cards.append(job)

            while True:
                job_labels = [f"{j.get('id')}: {_format_job_line(j)}" for j in job_cards]
                job_idx = _prompt_choice(f"{category} → {term}: matching jobs", job_labels, allow_back=True)
                if job_idx == -1:
                    break

                job = job_cards[job_idx]
                print("\nJob details")
                print("-----------")
                print(f"ID: {job.get('id')}")
                print(f"Title: {job.get('title')}")
                print(f"Company: {job.get('company')}")

                reqs = job.get("requirements", {}).get(category, [])
                if reqs:
                    print(f"\nMatched terms in {category}:")
                    for r in reqs:
                        print(f"- {r}")

                input("\nPress Enter to go back to the job list...")


def _find_latest_run_folder(scraped_data_dir: str) -> str | None:
    if not os.path.isdir(scraped_data_dir):
        return None

    candidates = []
    for name in os.listdir(scraped_data_dir):
        path = os.path.join(scraped_data_dir, name)
        if os.path.isdir(path):
            candidates.append(path)

    if not candidates:
        return None

    # choose most recently modified folder
    candidates.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return candidates[0]


def main() -> None:
    scraped_data_dir = os.path.join(os.getcwd(), "scraped_data")
    run_dir = _find_latest_run_folder(scraped_data_dir)
    if not run_dir:
        print("Couldn't find any run folders under scraped_data/.")
        return

    index_path = os.path.join(run_dir, "requirements_index.json")
    if not os.path.isfile(index_path):
        print(f"Couldn't find requirements_index.json in: {run_dir}")
        print("Run analysis first (Analyze requirements) to generate the index.")
        return

    print(f"Using index: {index_path}")
    browse_requirements_index(index_path)


if __name__ == "__main__":
    main()
