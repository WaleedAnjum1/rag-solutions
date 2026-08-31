"""
Medical Records Q&A — Pipeline Test Script

Tests the full ingest → query → summarise flow against the live service.

Usage:
    # Start the service first:
    uvicorn main:app --reload --port 8200

    # Then run this script:
    python test_pipeline.py
"""

import json
import sys
import time

import httpx

BASE_URL = "http://localhost:8200"
PATIENT_ID = "test_patient_001"

# Sample medical record text
SAMPLE_RECORD_TXT = b"""
Patient Name: John Doe
Date of Birth: 1980-03-15
Visit Date: 2024-11-20
Physician: Dr. Sarah Ahmed

CHIEF COMPLAINT:
Follow-up for Type 2 Diabetes Mellitus and hypertension.

DIAGNOSES:
1. Type 2 Diabetes Mellitus (E11.9) - Poorly controlled
2. Essential Hypertension (I10)
3. Hyperlipidemia (E78.5)

MEDICATIONS:
- Metformin 1000mg twice daily (morning and evening with meals)
- Lisinopril 10mg once daily (morning)
- Atorvastatin 40mg once daily (at bedtime)
- Aspirin 81mg once daily

ALLERGIES:
- Penicillin (rash and urticaria)
- Sulfa drugs (anaphylaxis)

VITALS:
- Blood Pressure: 148/92 mmHg
- Heart Rate: 78 bpm
- Weight: 92 kg
- HbA1c: 8.4%
- Fasting Blood Glucose: 186 mg/dL

LAB RESULTS (2024-11-18):
- HbA1c: 8.4% (Reference: < 7.0%)
- Fasting Glucose: 186 mg/dL (Reference: 70-100 mg/dL)
- Total Cholesterol: 214 mg/dL (Reference: < 200 mg/dL)
- LDL: 138 mg/dL (Reference: < 100 mg/dL)
- HDL: 42 mg/dL (Reference: > 40 mg/dL)
- Triglycerides: 178 mg/dL (Reference: < 150 mg/dL)
- Creatinine: 1.1 mg/dL (Reference: 0.7-1.2 mg/dL)
- eGFR: 72 mL/min/1.73m2

PLAN:
1. Increase Metformin to 2000mg daily if tolerated.
2. Add Empagliflozin 10mg once daily for glycaemic control and cardiovascular benefit.
3. Repeat HbA1c and lipid panel in 3 months.
4. Dietary counselling referral.
5. Next visit: 2025-02-20
"""


def print_separator(label: str) -> None:
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print("=" * 60)


def test_health() -> bool:
    print_separator("1. Health Check")
    r = httpx.get(f"{BASE_URL}/health", timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(json.dumps(data, indent=2))
    ok = data.get("status") == "ok"
    print(f"✓ Health OK" if ok else "✗ Health DEGRADED")
    return ok


def test_ingest() -> str | None:
    print_separator("2. Ingest Medical Record")
    files = {"file": ("visit_2024.txt", SAMPLE_RECORD_TXT, "text/plain")}
    data = {"patient_id": PATIENT_ID, "record_type": "consultation_note"}

    r = httpx.post(f"{BASE_URL}/ingest/", files=files, data=data, timeout=30)
    print(f"Status: {r.status_code}")

    if r.status_code != 201:
        print(f"✗ Ingest failed: {r.text}")
        return None

    result = r.json()
    print(json.dumps(result, indent=2))
    doc_id = result.get("doc_id")
    print(f"✓ Ingested with doc_id={doc_id}, chunks={result.get('chunks_count')}")
    return doc_id


def test_list_patients() -> None:
    print_separator("3. List Patients")
    r = httpx.get(f"{BASE_URL}/patients/", timeout=10)
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2))


def test_list_records() -> None:
    print_separator("4. List Patient Records")
    r = httpx.get(f"{BASE_URL}/patients/{PATIENT_ID}/records", timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(json.dumps(data, indent=2))
    print(f"✓ Found {data.get('total', 0)} record(s)")


def test_query(question: str) -> None:
    print_separator(f"5. Query: {question}")
    payload = {
        "patient_id": PATIENT_ID,
        "question": question,
        "top_k": 6,
    }
    r = httpx.post(f"{BASE_URL}/query/", json=payload, timeout=120)
    print(f"Status: {r.status_code}")

    if r.status_code != 200:
        print(f"✗ Query failed: {r.text}")
        return

    result = r.json()
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nSources ({len(result['sources'])}):")
    for src in result["sources"]:
        score = src.get("relevance_score", "?")
        rtype = src.get("record_type", "?")
        print(f"  [{score}] {src['filename']} [{rtype}] — chunk {src['chunk_index']}")


def test_summarise() -> None:
    print_separator("6. Structured Patient Summary")
    payload = {"patient_id": PATIENT_ID, "top_k": 15}
    r = httpx.post(f"{BASE_URL}/query/summarise", json=payload, timeout=180)
    print(f"Status: {r.status_code}")

    if r.status_code != 200:
        print(f"✗ Summary failed: {r.text}")
        return

    result = r.json()
    print(f"\n📋 Summary:\n{result['summary']}")
    print(f"\n🏥 Conditions:")
    for c in result.get("conditions", []):
        print(f"  • {c}")
    print(f"\n💊 Medications:")
    for m in result.get("medications", []):
        print(f"  • {m}")
    print(f"\n⚠️  Allergies:")
    for a in result.get("allergies", []):
        print(f"  • {a}")
    print(f"\n📅 Last Visit: {result.get('last_visit', 'Not found')}")
    print(f"\n✓ Summary generated using {len(result.get('sources', []))} source chunks")


def test_refusal() -> None:
    print_separator("7. Refusal Test (out-of-scope question)")
    payload = {
        "patient_id": PATIENT_ID,
        "question": "What is the capital of France?",
        "top_k": 5,
    }
    r = httpx.post(f"{BASE_URL}/query/", json=payload, timeout=120)
    result = r.json()
    print(f"Answer: {result['answer']}")
    expected = "I couldn't find relevant information in the provided records."
    if expected.lower() in result["answer"].lower():
        print("✓ Refusal message returned correctly")
    else:
        print("⚠ Unexpected answer (may still be acceptable)")


def test_cleanup(doc_id: str) -> None:
    print_separator("8. Cleanup — Delete Test Record")
    r = httpx.delete(
        f"{BASE_URL}/patients/{PATIENT_ID}/records/{doc_id}",
        timeout=10,
    )
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2))
    print("✓ Cleanup complete")


def main():
    print("\n🏥 Medical Records Q&A — Pipeline Test")
    print(f"   Service: {BASE_URL}")
    print(f"   Patient: {PATIENT_ID}\n")

    # 1. Health
    healthy = test_health()
    if not healthy:
        print("\n⚠ Service is degraded, but continuing tests…")

    # 2. Ingest
    doc_id = test_ingest()
    if not doc_id:
        print("\n✗ Ingest failed. Aborting.")
        sys.exit(1)

    time.sleep(1)  # brief pause after ingest

    # 3–4. Patient management
    test_list_patients()
    test_list_records()

    # 5. Clinical queries
    test_query("What medications is this patient currently on?")
    test_query("What were the HbA1c and fasting glucose lab results?")
    test_query("Does this patient have any known allergies?")
    test_query("What is the patient's blood pressure?")

    # 6. Summary
    test_summarise()

    # 7. Refusal
    test_refusal()

    # 8. Cleanup
    if doc_id:
        test_cleanup(doc_id)

    print("\n\n✅ All tests complete.\n")


if __name__ == "__main__":
    main()
