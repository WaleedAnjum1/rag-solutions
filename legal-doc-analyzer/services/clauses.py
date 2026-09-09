import re
import json
import logging
import httpx
import asyncio
from typing import List, Optional

from config import settings
from models.responses import Clause, RiskFlag, DocumentBrief, SourceChunk

logger = logging.getLogger(__name__)

CLAUSE_TYPES = [
    "parties", "term", "termination", "payment", "confidentiality", "non_compete",
    "indemnity", "liability_cap", "governing_law", "dispute_resolution",
    "force_majeure", "assignment", "ip_ownership", "notice", "renewal", "penalty", "other"
]

def _classify_clause(text: str) -> str:
    t = text.lower()
    if "indemn" in t or "hold harmless" in t: return "indemnity"
    if "confidential" in t or "non-disclosure" in t or "nda" in t or "proprietary" in t: return "confidentiality"
    if "compete" in t or "solicit" in t: return "non_compete"
    if "terminat" in t: return "termination"
    if "liab" in t and ("limit" in t or "cap" in t or "maximum" in t): return "liability_cap"
    if "govern" in t and "law" in t: return "governing_law"
    if "dispute" in t or "arbitrat" in t or "jurisdiction" in t or "venue" in t: return "dispute_resolution"
    if "force majeure" in t or "act of god" in t or "unforeseen" in t: return "force_majeure"
    if "assign" in t and "consent" in t: return "assignment"
    if "intellectual property" in t or "ip " in t or "copyright" in t or "trademark" in t or "patent" in t: return "ip_ownership"
    if "renew" in t or "automatic" in t: return "renewal"
    if "penalt" in t or "liquidated damage" in t: return "penalty"
    if "pay" in t or "fee" in t or "compensation" in t or "invoice" in t: return "payment"
    if "term" in t and ("commence" in t or "expire" in t or "duration" in t): return "term"
    if "notice" in t and ("address" in t or "writing" in t): return "notice"
    if "parties" in t or "between" in t and "agreement" in t: return "parties"
    return "other"

def segment_clauses(text: str) -> list[dict]:
    """Segment text on headings/numbers."""
    # Split on double newline followed by clause numbering or ALL CAPS or WHEREAS
    # E.g. "1. ", "1.1 ", "Article IV", "Section 12", "WHEREAS", "NOW THEREFORE"
    pattern = r'\n\n(?=(?:\d+\.\d*|[A-Z][A-Z\s]+|Article\s+[IVX]+|Section\s+\d+|WHEREAS|NOW THEREFORE)\b)'
    segments = re.split(pattern, text)
    
    clauses = []
    for i, seg in enumerate(segments):
        seg = seg.strip()
        if len(seg) < 20: continue
        
        # Try to extract heading
        heading_match = re.match(r'^((?:\d+\.\d*|[A-Z][A-Z\s]+|Article\s+[IVX]+|Section\s+\d+|WHEREAS).*?)(?:\n|\.)', seg)
        heading = heading_match.group(1).strip() if heading_match else None
        
        clauses.append({
            "id": f"clause_{i}",
            "clause_number": heading.split()[0] if heading and re.match(r'^\d', heading) else None,
            "heading": heading,
            "text": seg,
            "clause_type": _classify_clause(seg)
        })
    return clauses

async def _summarize_clause(clause_text: str, model: str, base_url: str) -> str:
    prompt = (
        "You are a legal assistant. Summarize the following contract clause in one plain-language sentence.\n\n"
        f"Clause:\n{clause_text}\n\n"
        "Summary:"
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": -1,
        "options": {"temperature": 0.1, "num_predict": 120},
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(f"{base_url}/api/generate", json=payload)
            resp.raise_for_status()
            return resp.json().get("response", "").strip()
        except Exception as e:
            logger.warning(f"Summarize failed: {e}")
            return "Could not summarize."

async def analyze_clauses(chunks: List[SourceChunk], model: str, base_url: str) -> List[Clause]:
    full_text = "\n\n".join(c.text for c in sorted(chunks, key=lambda x: x.chunk_index))
    segments = segment_clauses(full_text)
    
    # Run summaries concurrently
    tasks = [_summarize_clause(seg["text"], model, base_url) for seg in segments]
    summaries = await asyncio.gather(*tasks)
    
    res = []
    for seg, summary in zip(segments, summaries):
        res.append(Clause(
            id=seg["id"],
            clause_number=seg["clause_number"],
            heading=seg["heading"],
            text=seg["text"],
            clause_type=seg["clause_type"],
            summary=summary,
        ))
    return res

def analyze_risks(clauses: List[Clause], doc_type: str) -> List[RiskFlag]:
    risks = []
    types_found = set(c.clause_type for c in clauses)
    
    # 1. Present-but-adverse
    for c in clauses:
        t = c.text.lower()
        if c.clause_type == "liability_cap" and "unlimited" in t:
            risks.append(RiskFlag(id=f"risk_{len(risks)}", severity="high", title="Unlimited Liability", rationale="Liability is not capped.", clause_ref=c.heading or c.id))
        if c.clause_type == "termination" and ("unilateral" in t or "sole discretion" in t):
            risks.append(RiskFlag(id=f"risk_{len(risks)}", severity="medium", title="Unilateral Termination", rationale="One party can terminate at their sole discretion.", clause_ref=c.heading or c.id))
        if c.clause_type == "renewal" and "automatic" in t and "without notice" in t:
            risks.append(RiskFlag(id=f"risk_{len(risks)}", severity="medium", title="Auto-renewal without notice", rationale="Contract renews automatically without requiring notice.", clause_ref=c.heading or c.id))
        if c.clause_type == "governing_law" and not any(country in t for country in ["pakistan", "uae", "united states", "uk", "england"]):
            risks.append(RiskFlag(id=f"risk_{len(risks)}", severity="low", title="Foreign Governing Law", rationale="Governing law is outside standard jurisdictions.", clause_ref=c.heading or c.id))
        if c.clause_type == "confidentiality" and ("perpetual" in t or "indefinite" in t):
            risks.append(RiskFlag(id=f"risk_{len(risks)}", severity="medium", title="Perpetual Confidentiality", rationale="Confidentiality obligations do not expire.", clause_ref=c.heading or c.id))
        if c.clause_type == "assignment" and "without consent" in t:
            risks.append(RiskFlag(id=f"risk_{len(risks)}", severity="high", title="Assignment without consent", rationale="Contract can be assigned without prior written consent.", clause_ref=c.heading or c.id))

    # 2. Missing-clause
    if doc_type == "nda" and "term" not in types_found:
        risks.append(RiskFlag(id=f"risk_{len(risks)}", severity="high", title="Missing Term", rationale="NDA has no specified term.", clause_ref=None))
    if doc_type == "lease" and "payment" not in types_found:
        risks.append(RiskFlag(id=f"risk_{len(risks)}", severity="high", title="Missing Payment Terms", rationale="Lease does not specify payment details.", clause_ref=None))
    if doc_type in ["contract", "employment_agreement"] and "governing_law" not in types_found:
        risks.append(RiskFlag(id=f"risk_{len(risks)}", severity="medium", title="Missing Governing Law", rationale="No governing law specified.", clause_ref=None))

    return risks

async def extract_brief(clauses: List[Clause], doc_id: str, model: str, base_url: str) -> DocumentBrief:
    # Just LLM over the clauses to extract fields
    full_text = "\n\n".join(c.text for c in clauses[:15]) # Limit to avoid context length issues
    prompt = (
        "You are a legal assistant. Extract the following information from the contract text as a JSON object:\n"
        "- parties: list of strings\n"
        "- effective_date: string or null\n"
        "- term: string or null\n"
        "- governing_law: string or null\n"
        "- key_obligations: list of strings\n"
        "- termination_triggers: list of strings\n"
        "- unusual_provisions: list of strings\n\n"
        f"Contract:\n{full_text}\n\n"
        "Return ONLY valid JSON."
    )
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "keep_alive": -1,
        "options": {"temperature": 0.1, "num_predict": 500},
        "format": "json"
    }
    async with httpx.AsyncClient(timeout=60) as client:
        try:
            resp = await client.post(f"{base_url}/api/generate", json=payload)
            resp.raise_for_status()
            data = json.loads(resp.json().get("response", "{}"))
            return DocumentBrief(
                doc_id=doc_id,
                parties=data.get("parties", []),
                effective_date=data.get("effective_date"),
                term=data.get("term"),
                governing_law=data.get("governing_law"),
                key_obligations=data.get("key_obligations", []),
                termination_triggers=data.get("termination_triggers", []),
                unusual_provisions=data.get("unusual_provisions", []),
            )
        except Exception as e:
            logger.warning(f"Extract brief failed: {e}")
            return DocumentBrief(doc_id=doc_id, parties=[], key_obligations=[], termination_triggers=[], unusual_provisions=[])

async def compare_documents(clauses_a: List[Clause], clauses_b: List[Clause], model: str, base_url: str) -> List[dict]:
    # Group by clause type
    a_types = {c.clause_type: c for c in clauses_a}
    b_types = {c.clause_type: c for c in clauses_b}
    
    all_types = set(a_types.keys()) | set(b_types.keys())
    diffs = []
    
    for t in all_types:
        ca = a_types.get(t)
        cb = b_types.get(t)
        
        if ca and not cb:
            diffs.append({"clause_type": t, "status": "present_in_a", "clause_a": ca.model_dump(), "clause_b": None, "explanation": None})
        elif cb and not ca:
            diffs.append({"clause_type": t, "status": "present_in_b", "clause_a": None, "clause_b": cb.model_dump(), "explanation": None})
        elif ca and cb:
            # Quick exact match or LLM comparison
            if ca.text == cb.text:
                diffs.append({"clause_type": t, "status": "identical", "clause_a": ca.model_dump(), "clause_b": cb.model_dump(), "explanation": None})
            else:
                diffs.append({"clause_type": t, "status": "different", "clause_a": ca.model_dump(), "clause_b": cb.model_dump(), "explanation": "Clauses differ in text."})
                
    return diffs
