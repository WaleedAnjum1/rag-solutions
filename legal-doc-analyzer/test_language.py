"""
Multi-Language Customer Support Bot — Offline Unit Checks

Covers the parts of the service that need no Ollama, no ChromaDB writes, and no
model download:

    - language detection across scripts and Latin languages
    - reply-language precedence (explicit → detected → fallback)
    - localised refusal lookup
    - SentinelFilter: NO_ANSWER_FOUND must never leak into a stream, and no
      ordinary token may be swallowed
    - prompt invariant: the cached document prefix must stay language-neutral,
      or one customer's language would poison the KV cache for the next

Usage:
    python test_language.py

Exits non-zero if any check fails. `test_pipeline.py` covers the live flow.
"""

import sys

from config import settings
from models.responses import SourceChunk
from services.language import (
    NO_ANSWER_SENTINEL,
    REFUSAL_MESSAGES,
    detect_language,
    is_supported,
    language_name,
    localized_refusal,
    normalize_code,
    resolve_answer_language,
)
from services.rag_chain import (
    REASON_LOW_CONFIDENCE,
    REASON_NOT_COVERED,
    SentinelFilter,
    _build_doc_prompt,
    _build_qa_prompt,
    _evaluate_escalation,
    _question_suffix,
)

_passed = 0
_failed: list[str] = []


def check(label: str, condition: bool, detail: str = "") -> None:
    global _passed
    if condition:
        _passed += 1
    else:
        _failed.append(f"{label}{f'  →  {detail}' if detail else ''}")
        print(f"  ✗ {label}{f'  →  {detail}' if detail else ''}")


def section(label: str) -> None:
    print(f"\n{label}")
    print("-" * len(label))


def chunk(text: str, score: float = 0.8, doc_id: str = "doc_1") -> SourceChunk:
    return SourceChunk(
        chunk_id=f"{doc_id}_chunk_0",
        doc_id=doc_id,
        filename="billing_faq.txt",
        text=text,
        relevance_score=score,
        page=None,
        chunk_index=0,
        doc_type="faq",
        language="en",
    )


# ---------------------------------------------------------------------------
# 1. Language detection
# ---------------------------------------------------------------------------

section("1. Language detection — Latin script (stopwords + diacritics)")

LATIN_CASES = [
    ("en", "How long does a refund take, and can I cancel my order?"),
    ("es", "¿Cuánto tarda un reembolso? ¿Puedo cancelar mi pedido?"),
    ("fr", "Puis-je annuler mon abonnement à tout moment ?"),
    ("de", "Wie kann ich meine Bestellung stornieren und eine Erstattung bekommen?"),
    ("pt", "Quanto tempo demora um reembolso do meu pedido?"),
    ("it", "Quanto tempo serve per un rimborso del mio ordine?"),
    ("nl", "Hoe kan ik mijn bestelling annuleren?"),
    ("pl", "Jak mogę anulować moje zamówienie i otrzymać zwrot?"),
    ("tr", "Siparişimi nasıl iptal edebilirim ve iade alabilir miyim?"),
    ("id", "Bagaimana cara membatalkan pesanan saya dan meminta pengembalian?"),
    ("vi", "Tôi có thể hủy đơn hàng của tôi và hoàn tiền không?"),
]

for expected, text in LATIN_CASES:
    code, confidence = detect_language(text)
    check(
        f"detect '{expected}'",
        code == expected,
        f"got '{code}' (confidence={confidence}) for {text!r}",
    )

section("2. Language detection — non-Latin scripts")

SCRIPT_CASES = [
    ("ru", "Сколько времени занимает возврат средств?"),
    ("uk", "Скільки часу займає повернення коштів?"),
    ("el", "Πόσο καιρό διαρκεί η επιστροφή χρημάτων;"),
    ("ar", "كم يستغرق رد المبلغ إلى بطاقتي؟"),
    ("ur", "میں اپنا آرڈر کیسے منسوخ کروں؟"),
    ("fa", "چه مدت طول می‌کشد تا مبلغ بازگردانده شود؟"),
    ("he", "כמה זמן לוקח החזר כספי?"),
    ("hi", "मेरा रिफंड कितने दिन में आएगा?"),
    ("bn", "আমার রিফান্ড কত দিনে আসবে?"),
    ("zh", "退款需要多长时间？"),
    ("ja", "返金にはどのくらい時間がかかりますか？"),
    ("ko", "환불은 얼마나 걸리나요?"),
    ("th", "การคืนเงินใช้เวลานานเท่าไร"),
]

for expected, text in SCRIPT_CASES:
    code, confidence = detect_language(text)
    check(
        f"detect '{expected}'",
        code == expected,
        f"got '{code}' (confidence={confidence}) for {text!r}",
    )

section("3. Language detection — no signal")

code, confidence = detect_language("")
check("empty string falls back", code == settings.fallback_language, f"got '{code}'")
check("empty string has zero confidence", confidence == 0.0, f"got {confidence}")

code, confidence = detect_language("   ")
check("whitespace falls back", code == settings.fallback_language, f"got '{code}'")

code, confidence = detect_language("zzz qqq", default="es")
check("explicit default is honoured", code == "es", f"got '{code}'")
check("unknown text has zero confidence", confidence == 0.0, f"got {confidence}")

code, confidence = detect_language("E-4021")
check("code-only text falls back", code == settings.fallback_language, f"got '{code}'")

# A confident script hit should outrank a hesitant stopword guess.
_, script_confidence = detect_language("退款需要多长时间？")
_, short_latin_confidence = detect_language("mi pedido")
check(
    "script detection is more confident than a short Latin phrase",
    script_confidence > short_latin_confidence,
    f"script={script_confidence} latin={short_latin_confidence}",
)


# ---------------------------------------------------------------------------
# 4. Code normalisation and naming
# ---------------------------------------------------------------------------

section("4. Code normalisation and naming")

check("normalize 'pt-BR' → 'pt'", normalize_code("pt-BR") == "pt", normalize_code("pt-BR"))
check("normalize 'ES' → 'es'", normalize_code("ES") == "es", normalize_code("ES"))
check("normalize 'zh_Hans' → 'zh'", normalize_code("zh_Hans") == "zh", normalize_code("zh_Hans"))
check("normalize None → ''", normalize_code(None) == "", repr(normalize_code(None)))

check("'de' is supported", is_supported("de"))
check("'pt-BR' is supported", is_supported("pt-BR"))
check("'xx' is not supported", not is_supported("xx"))
check("None is not supported", not is_supported(None))

check("language_name('es') is 'Spanish'", language_name("es") == "Spanish", language_name("es"))
check("language_name('ja') is 'Japanese'", language_name("ja") == "Japanese", language_name("ja"))
check(
    "language_name falls back for unknown codes",
    language_name("xx") == language_name(settings.fallback_language),
    language_name("xx"),
)
check(
    "every supported language can be named",
    all(language_name(c) for c in REFUSAL_MESSAGES),
)


# ---------------------------------------------------------------------------
# 5. Reply-language precedence
# ---------------------------------------------------------------------------

section("5. Reply-language precedence")

check(
    "explicit request wins over detection",
    resolve_answer_language("de", "es") == "de",
    resolve_answer_language("de", "es"),
)
check(
    "'auto' defers to detection",
    resolve_answer_language("auto", "es") == "es",
    resolve_answer_language("auto", "es"),
)
check(
    "None defers to detection",
    resolve_answer_language(None, "tr") == "tr",
    resolve_answer_language(None, "tr"),
)
check(
    "unsupported detection falls back",
    resolve_answer_language(None, "xx") == settings.fallback_language,
    resolve_answer_language(None, "xx"),
)
check(
    "regional request is normalised",
    resolve_answer_language("pt-BR", "es") == "pt",
    resolve_answer_language("pt-BR", "es"),
)


# ---------------------------------------------------------------------------
# 6. Localised refusal
# ---------------------------------------------------------------------------

section("6. Localised refusal")

check(
    "every supported language has a refusal message",
    all(localized_refusal(code) for code in REFUSAL_MESSAGES),
)
check(
    "refusal messages are language-specific",
    localized_refusal("es") != localized_refusal("en"),
)
check(
    "unknown code falls back to the configured language",
    localized_refusal("xx") == REFUSAL_MESSAGES[settings.fallback_language],
)
check(
    "no refusal message leaks the sentinel",
    not any(NO_ANSWER_SENTINEL in msg for msg in REFUSAL_MESSAGES.values()),
)


# ---------------------------------------------------------------------------
# 7. SentinelFilter
# ---------------------------------------------------------------------------

section("7. SentinelFilter — the sentinel must never reach a customer")


def run_filter(tokens: list[str]) -> tuple[str, bool]:
    """Feed tokens through a fresh filter, returning (emitted_text, is_refusal)."""
    f = SentinelFilter()
    emitted = "".join(f.feed(t) for t in tokens)
    tail, refused = f.flush()
    return emitted + tail, refused

text, refused = run_filter(["Refunds ", "take ", "5 ", "business ", "days ", "[Source 1]."])
check("normal answer passes through unchanged",
      text == "Refunds take 5 business days [Source 1].", repr(text))
check("normal answer is not a refusal", not refused)

text, refused = run_filter(["NO", "_ANSWER", "_FOUND"])
check("exact sentinel emits nothing", text == "", repr(text))
check("exact sentinel is flagged as a refusal", refused)

text, refused = run_filter(["NO_ANSWER_FOUND", ".", " Sorry about that."])
check("sentinel with trailing text emits nothing", text == "", repr(text))
check("sentinel with trailing text is a refusal", refused)

text, refused = run_filter(["no_answer_found"])
check("lowercase sentinel is caught", text == "" and refused, repr(text))

text, refused = run_filter(["N", "ope", ", that is covered [Source 2]."])
check("sentinel-prefixed real answer is not swallowed",
      text == "Nope, that is covered [Source 2].", repr(text))
check("sentinel-prefixed real answer is not a refusal", not refused)

text, refused = run_filter(["\n", "\n", "Yes, you can cancel."])
check("leading whitespace is preserved", text == "\n\nYes, you can cancel.", repr(text))

text, refused = run_filter(["Un ", "reembolso ", "tarda ", "5 ", "días."])
check("non-English answer passes through", text == "Un reembolso tarda 5 días.", repr(text))

text, refused = run_filter([])
check("empty stream emits nothing", text == "" and not refused, repr(text))

# Once past the sentinel check the filter must not buffer — a streamed answer
# has to reach the customer token by token, not in one lump at the end.
f = SentinelFilter()
first = f.feed("Refunds ")
second = f.feed("take 5 days.")
check("tokens are released immediately after passthrough starts",
      first == "Refunds " and second == "take 5 days.", f"{first!r} / {second!r}")


# ---------------------------------------------------------------------------
# 8. Prompt invariants
# ---------------------------------------------------------------------------

section("8. Prompt invariants — the cached prefix must be language-neutral")

chunks = [chunk("Refunds are issued within 5 business days of approval.")]
doc_prompt = _build_doc_prompt(chunks)

check("doc prompt carries the support content",
      "Refunds are issued within 5 business days" in doc_prompt)
check("doc prompt numbers its sources", "[Source 1]" in doc_prompt)
check("doc prompt carries no filled-in reply-language block",
      "=== Reply Language ===" not in doc_prompt)
check("doc prompt contains no language directive",
      not any(name in doc_prompt for name in ("Spanish", "German", "Japanese")))
check("doc prompt contains no customer message", "Customer Message" not in doc_prompt)

suffix_es = _question_suffix("¿Cuánto tarda un reembolso?", "es")
suffix_de = _question_suffix("¿Cuánto tarda un reembolso?", "de")
check("question suffix names the reply language", "Spanish" in suffix_es, suffix_es)
check("suffixes differ per language", suffix_es != suffix_de)
check("question suffix carries the question", "reembolso" in suffix_es)

# This is the property that makes one cached KV context reusable for every
# language: the full prompt must be exactly [cached prefix] + [fresh suffix].
for lang, suffix in (("es", suffix_es), ("de", suffix_de)):
    full = _build_qa_prompt("¿Cuánto tarda un reembolso?", chunks, lang)
    check(f"full prompt for '{lang}' starts with the cacheable prefix",
          full.startswith(doc_prompt))
    check(f"full prompt for '{lang}' is prefix + suffix",
          full == doc_prompt + suffix)

# Multiple chunks from the same document share one source number; a second
# document gets the next one.
multi = [
    chunk("Refunds take 5 business days.", doc_id="doc_1"),
    chunk("Cancellation keeps the plan until the period ends.", doc_id="doc_1"),
    chunk("Los pedidos se envian en 2 dias laborables.", doc_id="doc_2"),
]
multi_prompt = _build_doc_prompt(multi)
check("chunks of one document share a source number",
      multi_prompt.count("[Source 1]") == 2, str(multi_prompt.count("[Source 1]")))
check("a second document gets the next source number", "[Source 2]" in multi_prompt)
check("no third source is invented", "[Source 3]" not in multi_prompt)


# ---------------------------------------------------------------------------
# 9. Escalation
# ---------------------------------------------------------------------------

section("9. Escalation decisions")

escalate, reason = _evaluate_escalation("NO_ANSWER_FOUND", [chunk("anything", score=0.9)])
check("sentinel escalates", escalate and reason == REASON_NOT_COVERED, f"{escalate}/{reason}")

grounded = "Refunds take 5 business days [Source 1]."
escalate, reason = _evaluate_escalation(grounded, [chunk("Refunds…", score=0.82)])
check("a well-grounded answer does not escalate",
      not escalate and reason is None, f"{escalate}/{reason}")

weak = settings.escalation_min_relevance - 0.1
escalate, reason = _evaluate_escalation(grounded, [chunk("Unrelated…", score=weak)])
check("a weak best match escalates for review",
      escalate and reason == REASON_LOW_CONFIDENCE, f"{escalate}/{reason}")

escalate, reason = _evaluate_escalation(grounded, [])
check("no chunks escalates", escalate and reason == REASON_LOW_CONFIDENCE, f"{escalate}/{reason}")


# ---------------------------------------------------------------------------
# Summary
# ---------------------------------------------------------------------------

print(f"\n{'=' * 60}")
if _failed:
    print(f"  {_passed} passed, {len(_failed)} FAILED")
    print("=" * 60)
    for failure in _failed:
        print(f"  ✗ {failure}")
    print()
    sys.exit(1)

print(f"  ✅ All {_passed} checks passed")
print("=" * 60 + "\n")
