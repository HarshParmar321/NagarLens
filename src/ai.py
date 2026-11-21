"""Claude layer: triage messy complaints/posts, explain cases, answer citizens, write officer briefs.

Rules: Claude never computes or overwrites numbers. Every call is cached on disk (data/cache/ai_cache.json)
and has a deterministic fallback, so the app runs offline and the demo never breaks.
"""
import hashlib
import json
import os
import re
from pathlib import Path

try:  # load ANTHROPIC_API_KEY etc. from the repo's .env (gitignored)
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

CACHE = Path(__file__).resolve().parent.parent / "data" / "cache" / "ai_cache.json"
MODEL = "claude-opus-5-5"
CATEGORIES = ["Pothole", "Waterlogging", "Open or broken manhole", "Choked drain / nullah overflow",
              "Road cave-in", "Broken paver blocks", "Not a road issue"]

_cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
_client = None

# Dev backend while no Anthropic key is set: NAGARLENS_LLM=ollama uses a local Ollama model through its
# Anthropic-compatible Messages endpoint. Answers are cached and labelled 'ollama', never shown as Claude.
PROVIDER = os.environ.get("NAGARLENS_LLM", "claude").lower()
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "hf.co/Jackrong/DeepSeek-V4-Pro-Qwen3.5-9B-MTP-GGUF:Q4_K_M")


def available() -> bool:
    if PROVIDER == "ollama":
        return True
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def engine_name() -> str:
    return f"Ollama ({OLLAMA_MODEL.split('/')[-1]})" if PROVIDER == "ollama" else f"Claude ({MODEL})"


def _key(task, payload):
    return PROVIDER + ":" + task + ":" + hashlib.sha256(json.dumps(payload, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _parse_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else None


def _save():
    CACHE.parent.mkdir(parents=True, exist_ok=True)
    CACHE.write_text(json.dumps(_cache, ensure_ascii=False, indent=1), encoding="utf-8")


def _call(task, payload, system, user, schema=None, max_tokens=2000):
    """Return (result, source) where source is 'claude', 'cache' or None (caller uses fallback)."""
    k = _key(task, payload)
    if k in _cache:
        return _cache[k], "cache"
    if not available():
        return None, None
    global _client
    try:
        import anthropic
        if PROVIDER == "ollama":
            _client = _client or anthropic.Anthropic(base_url=OLLAMA_URL, api_key="ollama", timeout=120)
            sys_ = system + (f"\nReturn ONLY a JSON object matching this JSON schema, no other text:\n{json.dumps(schema)}"
                             if schema else "")
            resp = _client.messages.create(model=OLLAMA_MODEL, max_tokens=max_tokens, system=sys_,
                                           messages=[{"role": "user", "content": user}])
        else:
            _client = _client or anthropic.Anthropic()
            resp = _client.beta.messages.create(
                model=MODEL, max_tokens=max_tokens, system=system, messages=[{"role": "user", "content": user}],
                output_config={"effort": "low", **({"format": {"type": "json_schema", "schema": schema}} if schema else {})},
                betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        if resp.stop_reason == "refusal":
            return None, None
        text = "".join(b.text for b in resp.content if b.type == "text")
        text = re.sub(r"<think>.*?</think>", "", text, flags=re.S).strip()
        out = (_parse_json(text) if PROVIDER == "ollama" else json.loads(text)) if schema else text
        if schema and (not out or not set(schema["required"]) <= set(out)):
            return None, None
        if schema and out.get("category") not in CATEGORIES:
            out["category"] = "Not a road issue"
        _cache[k] = out
        _save()
        return out, PROVIDER
    except Exception:  # network, auth, schema: fall back deterministically
        return None, None


# ---------- 1. Triage a raw complaint or social post ----------
TRIAGE_SCHEMA = {
    "type": "object", "additionalProperties": False,
    "required": ["category", "locality", "road_name", "landmark", "severity", "is_noise", "summary_en"],
    "properties": {
        "category": {"type": "string", "enum": CATEGORIES},
        "locality": {"type": "string"}, "road_name": {"type": "string"}, "landmark": {"type": "string"},
        "severity": {"type": "integer", "minimum": 1, "maximum": 5},
        "is_noise": {"type": "boolean", "description": "forward, thank-you, sarcasm or not a civic road issue"},
        "summary_en": {"type": "string"}}}

TRIAGE_SYSTEM = ("You triage Mumbai civic road complaints written in English, Hinglish, Marathi or Hindi. "
                 "Extract only what the text says; use an empty string when a field is not stated. "
                 "Severity: 5 = open manhole or cave-in or danger to life, 4 = deep waterlogging, "
                 "3 = pothole on a busy road, 2 = minor, 1 = cosmetic. Mark forwards, thank-yous and jokes as noise.")

# Most specific problems first, so "paver blocks ... water collecting" stays a paver issue.
KEYWORDS = [("Road cave-in", ["cave", "crater", "sinkhole", "dhas", "dhans", "खचला", "धंसी", "धंस"]),
            ("Open or broken manhole", ["manhole", "chamber", "dhakkan", "मैनहोल", "मॅनहोल", "ढक्कन", "झाकण"]),
            ("Broken paver blocks", ["paver", "pavement block", "पेव्हर", "पेवर"]),
            ("Choked drain / nullah overflow", ["drain", "nullah", "nala", "gutter", "नाला", "गटार", "नाली"]),
            ("Pothole", ["pothole", "khadda", "khada", "gaddha", "खड्डा", "खड्डे", "गड्ढा", "गड्ढे"]),
            ("Waterlogging", ["waterlog", "water logged", "flood", "paani", "pani", "knee", "पाणी", "पानी", "bhar gaya", "bharl"])]
SEV = {"Road cave-in": 5, "Open or broken manhole": 5, "Waterlogging": 4, "Pothole": 3,
       "Choked drain / nullah overflow": 3, "Broken paver blocks": 2, "Not a road issue": 1}


def cached_triage(text: str):
    """Return a cached model triage (Claude or Ollama) for this text, or None. Never calls a model."""
    for prov in ("claude", "ollama"):
        hit = _cache.get(prov + ":" + _key("triage", text).split(":", 1)[1])
        if hit:
            return {**hit, "source": "cache"}
    return None


def triage(text: str, gazetteer: list[str], reported: str = "", lang: str = "", allow_call: bool = True) -> dict:
    out, src = _call("triage", text, TRIAGE_SYSTEM, f"Complaint:\n{text}", TRIAGE_SCHEMA, 800) if allow_call else (None, None)
    if out:
        return {**out, "source": src}
    hit = cached_triage(text)
    if hit:
        return hit
    low = text.lower()
    # Rules override the citizen's category only for English text, or when the citizen picked a vague
    # category ("Road related" / "Other"); keyword rules are weaker than the citizen for Hindi/Marathi/Hinglish.
    vague = reported in ("Road related", "Other", "")
    kw = next((c for c, kws in KEYWORDS if any(k in low for k in kws)), None)
    if vague:
        cat = kw or "Not a road issue"
    elif lang in ("en", "") and kw:
        cat = kw
    else:
        cat = reported if reported in SEV else (kw or "Not a road issue")
    loc = next((g for g in gazetteer if g and g.lower() in low), "")
    road = (re.search(r"\b(?:on|at)\s+([A-Z][\w .]+?(?:Road|Marg|Highway|Rd))", text) or [None, ""])[1]
    noise = bool(re.search(r"\b(fwd|forwarded|thank|thanks|dhanyavad)\b", low))
    return {"category": cat, "locality": loc, "road_name": road, "landmark": "", "severity": SEV[cat],
            "is_noise": noise, "summary_en": text[:120], "source": "rules"}


# ---------- 2. Plain-language case verdict ----------
CASE_SYSTEM = ("You are an evidence-grounded municipal audit assistant for Mumbai. Use ONLY the supplied records and "
               "computed findings. Never infer fraud, guilt or intent, and never change a number. In under 110 words, "
               "plain English a citizen understands: what happened, whether the fix held, what the audit found and "
               "a fair alternative explanation, and the one next action for the ward officer.")


def explain_case(case: dict) -> tuple[str, str]:
    out, src = _call("case", case, CASE_SYSTEM, json.dumps(case, default=str, ensure_ascii=False), max_tokens=600)
    if out:
        return out, src
    w = case["work_order"]
    held = "held for 30 days" if w["reopened_within_30d"] == "N" else "failed within 30 days"
    flags = "; ".join(f["reason"] for f in case["findings"]) or "No audit rule was triggered."
    action = case["findings"][0]["review_action"] if case["findings"] else "No action needed beyond routine monitoring."
    return (f"{case['n_complaints']} citizen complaint(s) led to work order {w['work_order_id']} on {w['road_name']}. "
            f"{w['contractor_name']} carried out the repair ({w['repair_method']}) for ₹{w['cost_inr']:,} "
            f"(rate card ₹{w['expected_cost_inr']:,.0f}); the SLA was {'met' if w['sla_met'] == 'Y' else 'missed'} and the fix {held}. "
            f"Audit: {flags} Next step: {action}"), "template"


# ---------- 3. Citizen answer in their own language ----------
CITIZEN_SYSTEM = ("You answer a Mumbai citizen's question about their civic complaint. Reply in the SAME language and "
                  "script as the question (Marathi, Hindi, Hinglish or English). Use only the records given; never "
                  "change a number or guess. Under 90 words, warm and plain, end with one practical next step.")

TEMPL = {
    "mr": "तुमची तक्रार {cid} {received} ला नोंदवली गेली. काम {wo} अंतर्गत {contractor} ने दुरुस्ती केली, खर्च ₹{cost}. {held}",
    "hi": "आपकी शिकायत {cid} {received} को दर्ज हुई. काम {wo} के तहत {contractor} ने मरम्मत की, खर्च ₹{cost}. {held}",
    "en": "Your complaint {cid} was logged on {received}. {contractor} repaired it under work order {wo} for ₹{cost}. {held}"}
HELD = {"mr": ("दुरुस्ती 30 दिवस टिकली.", "मात्र 30 दिवसांच्या आत दुरुस्ती पुन्हा खराब झाली."),
        "hi": ("मरम्मत 30 दिन टिकी.", "लेकिन 30 दिनों के अंदर मरम्मत फिर खराब हो गई."),
        "en": ("The fix held for 30 days.", "But the fix failed within 30 days.")}


def detect_lang(q: str) -> str:
    if re.search(r"[ऀ-ॿ]", q):
        return "mr" if re.search(r"(माझी|काय|झालं|आहे|तक्रार)", q) else "hi"
    return "en"


def answer_citizen(question: str, records: dict) -> tuple[str, str]:
    question = question[:500]
    # Cache by complaint + language, not the raw question, so free-text variations cannot grow the cache
    # without bound or trigger a new model call for the same complaint.
    cid = (records.get("complaint") or {}).get("complaint_id")
    cache_payload = {"cid": cid, "lang": detect_lang(question)} if cid else {"q": question, "r": records}
    out, src = _call("citizen", cache_payload, CITIZEN_SYSTEM,
                     f"Question: {question}\nRecords: {json.dumps(records, default=str, ensure_ascii=False)}", max_tokens=600)
    if out:
        return out, src
    lang = detect_lang(question)
    w = records.get("work_order")
    if not w:
        return {"mr": "तुमची तक्रार अजून कोणत्याही कामाशी जोडलेली नाही.", "hi": "आपकी शिकायत अभी किसी काम से नहीं जुड़ी है.",
                "en": "Your complaint is not yet linked to any repair job."}[lang], "template"
    return TEMPL[lang].format(cid=records["complaint"]["complaint_id"], received=str(records["complaint"]["received_at"])[:10],
                              wo=w["work_order_id"], contractor=w["contractor_name"], cost=f"{w['cost_inr']:,}",
                              held=HELD[lang][w["reopened_within_30d"] == "Y"]), "template"


# ---------- 3b. Scorecard narrative (organizer's starter prompt) ----------
SCORECARD_SYSTEM = ("Write a fair, plain-language scorecard a Mumbai citizen could read, from the computed numbers and the "
                    "draft given. Cover speed, how long repairs lasted, cost vs the rate card, and one thing to improve. "
                    "Under 120 words, no accusations, keep every number exactly as given, and say 'compared with peers "
                    "doing the same kind of work' where the draft compares like with like.")


def scorecard_narrative(row: dict, template: str) -> tuple[str, str]:
    keep = {k: v for k, v in row.items() if not k.endswith("_z") and k not in ("speed_focus", "durability_focus")}
    out, src = _call("scorecard", {"row": keep, "draft": template}, SCORECARD_SYSTEM,
                     f"Numbers: {json.dumps(keep, default=str)}\nDraft: {template}", max_tokens=500)
    return (out, src) if out else (template, "template")


# ---------- 4. Ward officer brief ----------
BRIEF_SYSTEM = ("Write a one-page brief for a Mumbai ward officer from the computed audit leads and plan. Neutral tone, "
                "no blame. Sections: Top 3 leads to verify (cite work order ids and rupee amounts exactly), "
                "Money to recover, Where the next rupee goes, What to check this week. Markdown, under 250 words.")


def officer_brief(payload: dict) -> tuple[str, str]:
    out, src = _call("brief", payload, BRIEF_SYSTEM, json.dumps(payload, default=str, ensure_ascii=False), max_tokens=1500)
    if out:
        return out, src
    lines = [f"# Ward {payload['ward']} officer brief", "", "## Top leads to verify"]
    lines += [f"- **{l['work_order_id']}** ({l['rule_id']}): {l['reason']} At risk ₹{l['amount_at_risk_inr']:,}. "
              f"Next: {l['review_action']}" for l in payload["leads"][:3]]
    lines += ["", f"## Money to recover\n₹{payload['recoverable_inr']:,} across {payload['n_leads']} leads.",
              "", "## Where the next rupee goes"]
    lines += [f"- {s['road_name']}: {s['category_reported']} (score {s['risk_score']}), est. ₹{s['est_cost_inr']:,.0f}"
              for s in payload["plan"][:5]]
    return "\n".join(lines), "template"
