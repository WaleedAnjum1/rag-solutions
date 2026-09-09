"""
Multi-Language Customer Support Bot — Pipeline Test Script

Tests the full ingest → cross-lingual query → draft-reply flow against the live
service.

Usage:
    # Start the service first:
    uvicorn main:app --reload --port 8300

    # Then run this script:
    python test_pipeline.py
"""

import json
import sys
import time

import httpx

BASE_URL = "http://localhost:8300"
TENANT_ID = "test_tenant_001"

# English knowledge base — deliberately the ONLY English source, so that
# non-English queries prove cross-lingual retrieval rather than lucky matching.
# Kept as str (not bytes) and encoded at upload time: support content is full of
# non-ASCII text, which a bytes literal cannot hold.
SAMPLE_FAQ_EN = """
ACME Cloud — Billing & Orders FAQ

Q: How long does a refund take?
A: Refunds are issued to the original payment method within 5 business days of
approval. Bank processing can add 3 to 5 more days, so allow up to 10 business
days in total. Refunds cannot be issued to a different card than the one used
for the original purchase.

Q: Can I cancel my subscription at any time?
A: Yes. Cancel from Settings > Billing > Cancel plan. Your plan stays active
until the end of the current billing period; we do not pro-rate partial months.
Cancelling does not delete your data — exports remain available for 30 days.

Q: What happens if a payment fails?
A: We retry a failed payment three times over 7 days. After the third failure
the workspace is downgraded to the Free plan. No data is deleted during this
period.

Q: How do I change the plan on my workspace?
A: Owners and Billing Admins can change the plan from Settings > Billing. An
upgrade takes effect immediately and is charged pro-rata. A downgrade takes
effect at the start of the next billing period.

Q: Do you charge VAT?
A: VAT is added for customers in the EU and the UK unless a valid VAT number is
saved in Settings > Billing > Tax details. Prices shown on the pricing page
exclude VAT.

Q: What is error code E-4021?
A: E-4021 means the payment provider declined the card as expired. Update the
card details in Settings > Billing > Payment method and retry the invoice.
"""

# Spanish knowledge base — proves per-language content coexists in one tenant
# and that language metadata is stored and filterable.
SAMPLE_POLICY_ES = """
ACME Cloud — Política de envíos y entregas

Plazos de entrega
Los pedidos de hardware se envían en un plazo de 2 días laborables desde la
confirmación del pago. La entrega estándar tarda entre 3 y 7 días laborables
dentro de la Unión Europea.

Pedidos retrasados
Si un pedido no llega en un plazo de 14 días laborables, el cliente puede
solicitar un reenvío gratuito o un reembolso completo. La solicitud debe
realizarse desde el portal de soporte e incluir el número de pedido.

Envíos internacionales
Los envíos fuera de la Unión Europea pueden estar sujetos a aranceles
aduaneros, que corren a cargo del cliente. ACME Cloud no reembolsa los
aranceles aduaneros.

Daños en el transporte
Los daños deben notificarse en un plazo de 48 horas desde la entrega, con
fotografías del embalaje. Tras la verificación se envía un reemplazo sin coste.
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
    print("✓ Health OK" if ok else "✗ Health DEGRADED")
    return ok


def test_languages() -> None:
    print_separator("2. Supported Languages")
    r = httpx.get(f"{BASE_URL}/languages", timeout=10)
    data = r.json()
    print(f"Status: {r.status_code}")
    print(f"Total: {data.get('total')}  (default: {data.get('default_answer_language')})")
    codes = ", ".join(lang["code"] for lang in data.get("languages", []))
    print(f"Codes: {codes}")


def test_ingest(filename: str, content: str, doc_type: str, language: str) -> str | None:
    print_separator(f"3. Ingest — {filename} (type={doc_type}, language={language})")
    files = {"file": (filename, content.encode("utf-8"), "text/plain; charset=utf-8")}
    data = {"tenant_id": TENANT_ID, "doc_type": doc_type, "language": language}

    r = httpx.post(f"{BASE_URL}/ingest", files=files, data=data, timeout=60)
    print(f"Status: {r.status_code}")

    if r.status_code != 201:
        print(f"✗ Ingest failed: {r.text}")
        return None

    result = r.json()
    print(json.dumps(result, indent=2))
    print(
        f"✓ Ingested doc_id={result.get('doc_id')} "
        f"lang={result.get('language')} chunks={result.get('chunks_count')}"
    )
    return result.get("doc_id")


def test_list_tenants() -> None:
    print_separator("4. List Tenants")
    r = httpx.get(f"{BASE_URL}/tenants", timeout=10)
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2))


def test_list_documents() -> None:
    print_separator("5. List Tenant Documents")
    r = httpx.get(f"{BASE_URL}/tenants/{TENANT_ID}/documents", timeout=10)
    print(f"Status: {r.status_code}")
    data = r.json()
    print(json.dumps(data, indent=2))
    print(f"✓ Found {data.get('total', 0)} document(s)")


def test_query(label: str, question: str, expect_language: str | None = None,
               language: str | None = None) -> None:
    print_separator(f"6. Query [{label}]: {question}")
    payload: dict = {"tenant_id": TENANT_ID, "question": question, "top_k": 6}
    if language:
        payload["language"] = language

    r = httpx.post(f"{BASE_URL}/query", json=payload, timeout=180)
    print(f"Status: {r.status_code}")

    if r.status_code != 200:
        print(f"✗ Query failed: {r.text}")
        return

    result = r.json()
    print(
        f"detected={result.get('detected_language')} "
        f"(confidence={result.get('language_confidence')})  "
        f"answering_in={result.get('answer_language')}  "
        f"escalate={result.get('escalate')} "
        f"({result.get('escalation_reason')})  "
        f"top_score={result.get('retrieval_score')}"
    )
    print(f"\nAnswer:\n{result['answer']}")
    print(f"\nSources ({len(result['sources'])}):")
    for src in result["sources"]:
        print(f"  {src['id']}: {src['title']} [{src['kind']}, {src.get('language')}]")

    if expect_language:
        if result.get("answer_language") == expect_language:
            print(f"\n✓ Replied in '{expect_language}' as expected")
        else:
            print(
                f"\n⚠ Expected reply language '{expect_language}', "
                f"got '{result.get('answer_language')}'"
            )


def test_stream(question: str) -> None:
    print_separator(f"7. Streaming Query: {question}")
    payload = {"tenant_id": TENANT_ID, "question": question, "top_k": 6}

    tokens = 0
    print("Streamed answer:\n")
    with httpx.stream(
        "POST", f"{BASE_URL}/query/stream", json=payload, timeout=180
    ) as r:
        print(f"(status {r.status_code})")
        for line in r.iter_lines():
            if not line.startswith("data: "):
                continue
            event = json.loads(line[6:])
            if event.get("done"):
                print(
                    f"\n\n[final] language={event.get('answer_language')} "
                    f"escalate={event.get('escalate')} "
                    f"sources={len(event.get('sources') or [])}"
                )
                break
            if event.get("error"):
                print(f"\n✗ Stream error: {event['error']}")
                break
            print(event.get("token", ""), end="", flush=True)
            tokens += 1

    print(f"\n✓ Received {tokens} token event(s)")


def test_draft_reply() -> None:
    message = "Merhaba, aboneligimi iptal ettim ama param hala geri gelmedi. Ne zaman gelir?"
    print_separator(f"8. Draft Reply (Turkish): {message}")
    payload = {
        "tenant_id": TENANT_ID,
        "message": message,
        "top_k": 6,
        "tone": "friendly",
    }
    r = httpx.post(f"{BASE_URL}/query/draft-reply", json=payload, timeout=180)
    print(f"Status: {r.status_code}")

    if r.status_code != 200:
        print(f"✗ Draft failed: {r.text}")
        return

    result = r.json()
    print(
        f"detected={result.get('detected_language')} "
        f"draft_language={result.get('language')} "
        f"tone={result.get('tone')} escalate={result.get('escalate')}"
    )
    print(f"\nDraft:\n{result['draft']}")
    print(f"\n✓ Grounded in {len(result.get('sources', []))} source chunk(s)")


def test_escalation() -> None:
    print_separator("9. Escalation Test (question the content cannot answer)")
    payload = {
        "tenant_id": TENANT_ID,
        "question": "Können Sie mir sagen, wie das Wetter morgen in Berlin wird?",
        "top_k": 5,
    }
    r = httpx.post(f"{BASE_URL}/query", json=payload, timeout=180)
    result = r.json()
    print(f"Answer: {result['answer']}")
    print(
        f"escalate={result.get('escalate')} "
        f"reason={result.get('escalation_reason')} "
        f"language={result.get('answer_language')}"
    )

    if result.get("escalate"):
        print("✓ Escalated instead of guessing")
    else:
        print("⚠ Did not escalate — check the answer is genuinely grounded")

    if "NO_ANSWER_FOUND" in result.get("answer", ""):
        print("✗ Refusal sentinel leaked into the customer-facing answer")


def test_bad_language() -> None:
    print_separator("10. Validation — unsupported language code")
    payload = {
        "tenant_id": TENANT_ID,
        "question": "How long does a refund take?",
        "language": "xx",
    }
    r = httpx.post(f"{BASE_URL}/query", json=payload, timeout=30)
    print(f"Status: {r.status_code}")
    print(r.text[:300])
    print("✓ Rejected with 400" if r.status_code == 400 else "⚠ Expected 400")


def test_cleanup() -> None:
    print_separator("11. Cleanup — Delete Test Tenant")
    r = httpx.delete(f"{BASE_URL}/tenants/{TENANT_ID}", timeout=30)
    print(f"Status: {r.status_code}")
    print(json.dumps(r.json(), indent=2))
    print("✓ Cleanup complete")


def main():
    print("\n🌍 Multi-Language Customer Support Bot — Pipeline Test")
    print(f"   Service: {BASE_URL}")
    print(f"   Tenant:  {TENANT_ID}\n")

    # 1–2. Service metadata
    healthy = test_health()
    if not healthy:
        print("\n⚠ Service is degraded, but continuing tests…")
    test_languages()

    # 3. Ingest an English FAQ and a Spanish policy into the same tenant
    faq_id = test_ingest("billing_faq_en.txt", SAMPLE_FAQ_EN, "faq", "auto")
    if not faq_id:
        print("\n✗ Ingest failed. Aborting.")
        sys.exit(1)
    test_ingest("politica_envios_es.txt", SAMPLE_POLICY_ES, "policy", "auto")

    time.sleep(1)  # brief pause after ingest

    # 4–5. Tenant management
    test_list_tenants()
    test_list_documents()

    # 6. Cross-lingual queries — each answered from content in another language
    test_query("Spanish → English FAQ", "¿Cuánto tarda en llegar un reembolso?", "es")
    test_query("French → English FAQ", "Puis-je annuler mon abonnement à tout moment ?", "fr")
    test_query("German → English FAQ", "Was bedeutet der Fehlercode E-4021?", "de")
    test_query("English → Spanish policy", "My hardware order is two weeks late. What now?", "en")
    test_query("Forced reply language", "¿Cuánto tarda en llegar un reembolso?", "en",
               language="en")

    # 7. Streaming
    test_stream("¿Cuánto tarda en llegar un reembolso?")

    # 8. Agent-assist draft
    test_draft_reply()

    # 9–10. Guardrails
    test_escalation()
    test_bad_language()

    # 11. Cleanup
    test_cleanup()

    print("\n\n✅ All tests complete.\n")


if __name__ == "__main__":
    main()
