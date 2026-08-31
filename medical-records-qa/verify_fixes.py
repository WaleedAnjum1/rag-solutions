"""
Offline verification for the readings / filtering / knowledge-link fixes.

Runs the pure functions in services.rag_chain against the chunks already
ingested in ./chroma_db — no server and no Ollama needed.

    .venv/bin/python verify_fixes.py
"""

import sys

from services.rag_chain import (
    _build_knowledge_sources,
    _extract_readings_regex,
    _filter_readings_by_question,
)
from services.vectorstore import VectorStore

failures: list[str] = []


def check(label: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {label}{f'  — {detail}' if detail else ''}")
    if not ok:
        failures.append(label)


def load_chunks():
    store = VectorStore()
    for patient_id in store.list_patients():
        for record in store.list_records(patient_id):
            chunks = store.get_all_chunks(patient_id, record.doc_id)
            if chunks:
                print(f"Using patient={patient_id} doc={record.filename} ({len(chunks)} chunks)\n")
                return chunks
    return []


chunks = load_chunks()
if not chunks:
    print("No ingested documents found in ./chroma_db — ingest a report first.")
    sys.exit(1)

# --- Extraction ------------------------------------------------------------
readings = _extract_readings_regex(chunks)
names = [r["name"] for r in readings]

print(f"{len(readings)} readings extracted:")
for r in readings:
    print(f"  {r['name']:<32} {r['value']:>8} {r['unit']:<10} ({r['reference_range']}) {r['status']}")
print()

check("no duplicate reading names", len(names) == len(set(names)),
      f"dupes: {sorted({n for n in names if names.count(n) > 1})}")
check("no chunk-boundary artifact 'ocytes'", "ocytes" not in names)
check("no unit leaked into a name", not [n for n in names if n.lower().endswith((" fl", " pg", " %"))],
      str([n for n in names if n.lower().endswith((" fl", " pg", " %"))]))
check("differential % and absolute count kept distinct",
      not any(n.lower().startswith("abs") for n in names)
      or len([n for n in names if n.lower().startswith("abs")]) > 0,
      f"abs rows: {[n for n in names if n.lower().startswith('abs')]}")

# --- Filtering -------------------------------------------------------------
print()


def filtered(q: str) -> list[str]:
    return [r["name"] for r in _filter_readings_by_question(readings, q)]


cases = [
    ("What is monocytes?", "some"),
    ("What is Hb?", "some"),
    ("What is my hemoglobin?", "some"),
    ("What are my white blood cells?", "some"),
    ("What is my ALP?", "some"),
    ("Summarise the lab report", "all"),
    ("What are my allergies?", "none"),
    ("What is my vitamin D?", "none"),
]

for question, expect in cases:
    got = filtered(question)
    if expect == "all":
        ok = len(got) == len(readings)
    elif expect == "none":
        ok = len(got) == 0
    else:
        ok = 0 < len(got) < len(readings)
    check(f"{question!r} → {expect}", ok, f"{len(got)} rows: {got[:4]}")

# --- Knowledge links -------------------------------------------------------
print()
for question in ["what are my white blood cells?", "are my platelets normal?",
                 "what about neutrophils?", "explain my hemoglobin"]:
    srcs = _build_knowledge_sources(question)
    check(f"knowledge link for {question!r}", len(srcs) > 0,
          ", ".join(s.title for s in srcs))

print()
if failures:
    print(f"{len(failures)} check(s) failed.")
    sys.exit(1)
print("All checks passed.")
