"""
Language detection and localisation helpers.

Why this exists
---------------
A multilingual support bot has to answer in the customer's language even when
the knowledge base is written in another one. Three things follow from that:

1. **Detection** — we need the customer's language before we prompt the LLM.
   Detection here is deliberately dependency-free: Unicode script counting for
   non-Latin scripts, plus stopword/diacritic scoring for Latin scripts. It is a
   heuristic, not a classifier. Clients that already know the language (a locale
   header, a user profile) should pass `language` explicitly and skip it.

2. **Naming** — the LLM is instructed with a language *name* ("Spanish"), which
   is far more reliable for a small model than a code ("es").

3. **Refusal** — the model is told to emit `NO_ANSWER_FOUND` when the sources
   don't cover the question, and we replace that sentinel with a localised
   message. Detecting a refusal by matching English text would break the moment
   the model refuses in Turkish.
"""

import logging
import re
import unicodedata

from config import settings

logger = logging.getLogger(__name__)

# Emitted verbatim by the LLM when the retrieved sources do not answer the
# question. Never shown to a customer — it is swapped for a localised message.
NO_ANSWER_SENTINEL = "NO_ANSWER_FOUND"


# ---------------------------------------------------------------------------
# Supported languages
# ---------------------------------------------------------------------------
# Code → English name used in prompts. This is the set we can name and localise
# a refusal for; the detector recognises a subset of it (see _STOPWORDS and
# _SCRIPT_LANGUAGES).

SUPPORTED_LANGUAGES: dict[str, str] = {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "pt": "Portuguese",
    "it": "Italian",
    "nl": "Dutch",
    "pl": "Polish",
    "tr": "Turkish",
    "id": "Indonesian",
    "vi": "Vietnamese",
    "ru": "Russian",
    "uk": "Ukrainian",
    "el": "Greek",
    "ar": "Arabic",
    "ur": "Urdu",
    "fa": "Persian",
    "he": "Hebrew",
    "hi": "Hindi",
    "bn": "Bengali",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "th": "Thai",
}

# Shown to the customer when retrieval finds nothing usable.
REFUSAL_MESSAGES: dict[str, str] = {
    "en": "I couldn't find an answer to that in our support content. I'm passing this to a human agent.",
    "es": "No he encontrado una respuesta a eso en nuestra documentación de soporte. Voy a derivar tu consulta a un agente.",
    "fr": "Je n'ai pas trouvé de réponse à cette question dans notre documentation d'assistance. Je transmets votre demande à un agent.",
    "de": "Ich habe dazu keine Antwort in unseren Support-Inhalten gefunden. Ich leite Ihre Anfrage an einen Mitarbeiter weiter.",
    "pt": "Não encontrei uma resposta para isso na nossa documentação de suporte. Vou encaminhar o seu pedido a um agente.",
    "it": "Non ho trovato una risposta nella nostra documentazione di supporto. Inoltro la tua richiesta a un operatore.",
    "nl": "Ik heb hierover geen antwoord gevonden in onze supportdocumentatie. Ik geef je vraag door aan een medewerker.",
    "pl": "Nie znalazłem odpowiedzi na to pytanie w naszej dokumentacji pomocy. Przekazuję sprawę do konsultanta.",
    "tr": "Bu konuda destek içeriğimizde bir yanıt bulamadım. Talebinizi bir müşteri temsilcisine aktarıyorum.",
    "id": "Saya tidak menemukan jawaban untuk pertanyaan itu di dokumentasi dukungan kami. Saya teruskan ke agen kami.",
    "vi": "Tôi không tìm thấy câu trả lời cho câu hỏi này trong tài liệu hỗ trợ của chúng tôi. Tôi sẽ chuyển yêu cầu của bạn đến nhân viên hỗ trợ.",
    "ru": "Я не нашёл ответа на этот вопрос в нашей справочной документации. Передаю обращение оператору.",
    "uk": "Я не знайшов відповіді на це питання в нашій довідковій документації. Передаю звернення оператору.",
    "el": "Δεν βρήκα απάντηση σε αυτό στο υλικό υποστήριξής μας. Προωθώ το αίτημά σας σε εκπρόσωπο.",
    "ar": "لم أجد إجابة عن هذا في محتوى الدعم لدينا. سأحوّل طلبك إلى أحد الموظفين.",
    "ur": "مجھے ہماری سپورٹ دستاویزات میں اس کا جواب نہیں ملا۔ میں آپ کی درخواست نمائندے کو بھیج رہا ہوں۔",
    "fa": "پاسخی برای این پرسش در مستندات پشتیبانی ما پیدا نکردم. درخواست شما را به یک کارشناس ارجاع می‌دهم.",
    "he": "לא מצאתי תשובה לשאלה הזו בתיעוד התמיכה שלנו. אני מעביר את הפנייה לנציג.",
    "hi": "मुझे हमारी सहायता सामग्री में इसका उत्तर नहीं मिला। मैं आपका अनुरोध एक एजेंट को भेज रहा हूँ।",
    "bn": "আমাদের সহায়তা নথিতে এর উত্তর পাইনি। আপনার অনুরোধটি একজন এজেন্টের কাছে পাঠাচ্ছি।",
    "zh": "我在我们的支持文档中没有找到这个问题的答案。我会将您的问题转交给人工客服。",
    "ja": "サポート資料の中にこのご質問への回答が見つかりませんでした。担当者におつなぎします。",
    "ko": "지원 문서에서 해당 질문에 대한 답을 찾지 못했습니다. 담당 상담원에게 전달하겠습니다.",
    "th": "ฉันไม่พบคำตอบสำหรับคำถามนี้ในเอกสารช่วยเหลือของเรา ฉันจะส่งต่อให้เจ้าหน้าที่",
}


# ---------------------------------------------------------------------------
# Script-based detection (non-Latin)
# ---------------------------------------------------------------------------
# Ranges are checked in order; the script with the most characters wins.

_SCRIPT_RANGES: dict[str, tuple[tuple[int, int], ...]] = {
    "arabic":     ((0x0600, 0x06FF), (0x0750, 0x077F), (0xFB50, 0xFDFF), (0xFE70, 0xFEFF)),
    "hebrew":     ((0x0590, 0x05FF),),
    "cyrillic":   ((0x0400, 0x04FF),),
    "greek":      ((0x0370, 0x03FF),),
    "devanagari": ((0x0900, 0x097F),),
    "bengali":    ((0x0980, 0x09FF),),
    "thai":       ((0x0E00, 0x0E7F),),
    "hangul":     ((0x1100, 0x11FF), (0x3130, 0x318F), (0xAC00, 0xD7AF)),
    "kana":       ((0x3040, 0x30FF),),
    "han":        ((0x3400, 0x4DBF), (0x4E00, 0x9FFF)),
}

# Scripts that map 1:1 onto a language.
_SCRIPT_LANGUAGES: dict[str, str] = {
    "hebrew": "he",
    "greek": "el",
    "devanagari": "hi",
    "bengali": "bn",
    "thai": "th",
    "hangul": "ko",
    "kana": "ja",
    "han": "zh",
}

# Perso-Arabic script is shared. These letters split it:
#   Urdu-only retroflex/aspirate letters, then letters shared by Persian + Urdu.
_URDU_LETTERS = frozenset("ٹڈڑںھےۂۓ")
_PERSIAN_LETTERS = frozenset("پچژگکی")

# Ukrainian-only Cyrillic letters.
_UKRAINIAN_LETTERS = frozenset("іїєґ")


# ---------------------------------------------------------------------------
# Stopword-based detection (Latin script)
# ---------------------------------------------------------------------------
# Deliberately small, high-frequency sets biased toward customer-support
# phrasing ("where is my order", "how do I cancel").

_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset("the a an is are was my me you your how where what when why can cannot do does not and or of to in for with this that it if please help order refund cancel account".split()),
    "es": frozenset("el la los las un una es son mi mis me su como donde que cuando por para no y o de en con esto esa si puedo puede pedido factura cuenta cancelar reembolso ayuda".split()),
    "fr": frozenset("le la les un une est sont mon ma mes je vous votre comment ou est-ce que quand pourquoi pas et de du des en pour avec cette si puis-je peux commande facture compte annuler remboursement aide".split()),
    "de": frozenset("der die das ein eine ist sind mein meine ich sie ihre wie wo was wann warum nicht und oder von zu in für mit diese wenn kann bestellung rechnung konto stornieren erstattung hilfe".split()),
    "pt": frozenset("o a os as um uma é são meu minha eu você seu como onde que quando por para não e ou de em com este se posso pode pedido fatura conta cancelar reembolso ajuda".split()),
    "it": frozenset("il lo la i gli le un una è sono mio mia io tu tuo come dove che quando perché non e o di in per con questo se posso può ordine fattura account annullare rimborso aiuto".split()),
    "nl": frozenset("de het een is zijn mijn ik je jouw uw hoe waar wat wanneer waarom niet en of van naar in voor met deze als kan bestelling factuur account annuleren terugbetaling hulp".split()),
    "pl": frozenset("nie jest są mój moja ja ty twoje jak gdzie co kiedy dlaczego i lub od do w dla z to jeśli czy mogę może zamówienie faktura konto anulować zwrot pomoc".split()),
    "tr": frozenset("bir ve veya benim ben siz sizin nasıl nerede ne zaman neden değil için ile bu şu eğer mi mu bilir miyim sipariş fatura hesap iptal iade yardım".split()),
    "id": frozenset("yang dan atau saya anda kamu bagaimana dimana di mana apa kapan mengapa tidak untuk dengan ini itu jika bisa dapat pesanan tagihan akun batalkan pengembalian bantuan".split()),
    "vi": frozenset("và hoặc tôi bạn của làm sao thế nào ở đâu gì khi nào tại sao không cho với này nếu có thể đơn hàng hóa đơn tài khoản hủy hoàn tiền trợ giúp".split()),
}

# Characters that strongly suggest a language when there are too few words for
# stopwords to decide. Scored below a stopword hit — several of these are shared
# between languages, so they nudge rather than decide.
_CHAR_HINTS: dict[str, frozenset[str]] = {
    "es": frozenset("ñ¿¡"),
    "pt": frozenset("ãõ"),
    "fr": frozenset("œçèêû"),
    "de": frozenset("ßäöü"),
    "tr": frozenset("ğşıçİ"),
    "pl": frozenset("łżśćęąźń"),
    "vi": frozenset("ơưđấầệọ"),
}

_HINT_WEIGHT = 0.75
_TOKEN_RE = re.compile(r"[^\W\d_]+", re.UNICODE)

# Single letters are not evidence of a language: support messages are full of
# them ("Error E-4021", "plan B"), and a lone "e" is a stopword in Portuguese,
# Italian, and French at once — enough to route a reply into the wrong language.
_MIN_TOKEN_LEN = 2

# Stopword hits needed before a guess counts as fully evidenced. Below this the
# confidence is scaled down, so a two-word phrase never scores like a paragraph.
_FULL_EVIDENCE_HITS = 4.0


def normalize_code(code: str | None) -> str:
    """Normalise a language tag to a bare lowercase code ('pt-BR' → 'pt')."""
    if not code:
        return ""
    return code.strip().lower().replace("_", "-").split("-")[0]


def is_supported(code: str | None) -> bool:
    return normalize_code(code) in SUPPORTED_LANGUAGES


def language_name(code: str | None) -> str:
    """English name of a language code, for use inside prompts."""
    normalized = normalize_code(code)
    return SUPPORTED_LANGUAGES.get(
        normalized,
        SUPPORTED_LANGUAGES[settings.fallback_language],
    )


def localized_refusal(code: str | None) -> str:
    """Customer-facing 'not covered' message in the requested language."""
    normalized = normalize_code(code)
    return REFUSAL_MESSAGES.get(
        normalized,
        REFUSAL_MESSAGES.get(settings.fallback_language, REFUSAL_MESSAGES["en"]),
    )


def _dominant_script(text: str) -> tuple[str | None, int, int]:
    """Return (script_name, script_char_count, total_letter_count)."""
    counts: dict[str, int] = {}
    letters = 0

    for char in text:
        if not char.isalpha():
            continue
        letters += 1
        code_point = ord(char)
        for script, ranges in _SCRIPT_RANGES.items():
            if any(low <= code_point <= high for low, high in ranges):
                counts[script] = counts.get(script, 0) + 1
                break

    if not counts:
        return None, 0, letters

    script = max(counts, key=lambda s: counts[s])
    return script, counts[script], letters


def _resolve_arabic_script(text: str) -> str:
    """Split Perso-Arabic script into Urdu, Persian, or Arabic."""
    chars = set(text)
    if chars & _URDU_LETTERS:
        return "ur"
    if chars & _PERSIAN_LETTERS:
        return "fa"
    return "ar"


def _latin_tokens(text: str) -> list[str]:
    """Lowercased words from `text` that are long enough to count as evidence."""
    return [t for t in _TOKEN_RE.findall(text.lower()) if len(t) >= _MIN_TOKEN_LEN]


def _score_latin(text: str, tokens: list[str]) -> dict[str, float]:
    """Score each Latin-script language by stopword hits plus character hints."""
    token_set = set(tokens)
    present = set(text.lower())

    scores: dict[str, float] = {}
    for code, stopwords in _STOPWORDS.items():
        score = float(len(token_set & stopwords))
        hints = _CHAR_HINTS.get(code)
        if hints and (present & hints):
            score += _HINT_WEIGHT
        if score:
            scores[code] = score
    return scores


def detect_language(text: str, default: str | None = None) -> tuple[str, float]:
    """
    Best-effort language detection.

    Args:
        text:    Customer message or document text.
        default: Code to return when detection finds no signal.
                 Defaults to `settings.fallback_language`.

    Returns:
        (language_code, confidence) where confidence is in [0, 1]. A confidence
        of 0.0 means "no signal at all — this is the fallback".
    """
    fallback = normalize_code(default) or settings.fallback_language
    if not text or not text.strip():
        return fallback, 0.0

    # Normalise compatibility forms (e.g. Arabic presentation forms) so script
    # detection sees the canonical code points.
    sample = unicodedata.normalize("NFKC", text[:2000])

    script, script_chars, letters = _dominant_script(sample)
    if script and letters and script_chars / letters >= 0.30:
        if script == "arabic":
            return _resolve_arabic_script(sample), 0.95
        if script == "cyrillic":
            code = "uk" if set(sample.lower()) & _UKRAINIAN_LETTERS else "ru"
            return code, 0.95
        if script == "kana":
            return "ja", 0.95
        if script == "han":
            # Kana anywhere in the text means Japanese even if Han dominates.
            kana = sum(1 for c in sample if 0x3040 <= ord(c) <= 0x30FF)
            return ("ja" if kana else "zh"), 0.95
        mapped = _SCRIPT_LANGUAGES.get(script)
        if mapped:
            return mapped, 0.95

    tokens = _latin_tokens(sample)
    scores = _score_latin(sample, tokens)
    if not scores:
        return fallback, 0.0

    ranked = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    best_code, best_score = ranked[0]
    runner_up = ranked[1][1] if len(ranked) > 1 else 0.0

    # Confidence combines how much evidence was found (`volume`) with how
    # decisively it beat the next-best language (`margin`). Neither works alone:
    # a two-word phrase can match one language perfectly, and a long document
    # matches several languages a little. Caps at 0.90, below the 0.95 a script
    # match earns.
    volume = min(1.0, best_score / _FULL_EVIDENCE_HITS)
    margin = (best_score - runner_up) / best_score
    confidence = 0.25 + 0.65 * volume * (0.5 + 0.5 * margin)
    if best_score == runner_up:
        # Two languages tied — usually a short phrase of shared vocabulary.
        confidence = min(confidence, 0.35)

    return best_code, round(confidence, 2)


def resolve_answer_language(requested: str | None, detected: str | None) -> str:
    """
    Decide which language the reply must be written in.

    Precedence: explicit request → detected language → configured fallback.
    An unsupported explicit request is rejected upstream (see the routers), so
    reaching the fallback here means detection produced something we can't name.
    """
    candidate = normalize_code(requested) or normalize_code(settings.default_answer_language)
    if candidate and candidate != "auto":
        return candidate if is_supported(candidate) else settings.fallback_language

    detected_code = normalize_code(detected)
    if is_supported(detected_code):
        return detected_code

    logger.debug("Unsupported detected language '%s' — falling back.", detected)
    return settings.fallback_language
