"""Guesses the language of typed text with no model: the script settles most (Hangul, kana, Thai…);
for Latin, Cyrillic and Arabic script a short list of each language's commonest words decides.
Returns a language id from languages.py, or None when it can't tell (the UI then asks)."""
from __future__ import annotations

import re
import unicodedata

_SCRIPTS = [
    ("ko", re.compile(r"[가-힯ᄀ-ᇿ㄰-㆏]")),
    ("ja", re.compile(r"[぀-ヿ]")),
    ("th", re.compile(r"[฀-๿]")),
    ("lo", re.compile(r"[຀-໿]")),
    ("km", re.compile(r"[ក-៿]")),
    ("my", re.compile(r"[က-႟]")),
    ("he", re.compile(r"[֐-׿]")),
    ("el", re.compile(r"[Ͱ-Ͽ]")),
    ("ka", re.compile(r"[Ⴀ-ჿ]")),
    ("hy", re.compile(r"[԰-֏]")),
    ("hi", re.compile(r"[ऀ-ॿ]")),
    ("bn", re.compile(r"[ঀ-৿]")),
    ("ta", re.compile(r"[஀-௿]")),
    ("te", re.compile(r"[ఀ-౿]")),
    ("si", re.compile(r"[඀-෿]")),
    ("am", re.compile(r"[ሀ-፿]")),
]
_HAN = re.compile(r"[一-鿿]")
_CYRILLIC = re.compile(r"[Ѐ-ӿ]")
_ARABIC = re.compile(r"[؀-ۿ]")
_WORD = re.compile(r"[^\W\d_]+", re.UNICODE)

# The commonest short words of each language (no overlap where it matters: "di" is Indonesian,
# "de" Spanish/French/Dutch/Portuguese are told apart by their neighbours).
_WORDS = {
    "id": "yang dan di ini itu dengan untuk tidak ada saya akan dari ke pada juga bisa kami kita mereka sudah apa adalah atau karena tapi sangat lagi belum sedang terima kasih tolong bagaimana kenapa dimana",
    "ms": "yang dan di ini itu dengan untuk tidak ada saya akan dari ke pada juga boleh kami kita mereka sudah apa adalah atau kerana tetapi sangat lagi belum sedang terima kasih tolong bagaimana mengapa",
    "en": "the and is are to of in that it for you with on this be was have not but what they we at from by or can will would there their your about how which",
    "jv": "lan ing iki kuwi aku kowe ora wis arep karo saka sing ana apa piye kepiye mboten nggih kula panjenengan menika",
    "su": "jeung di ieu éta abdi anjeun henteu teu geus bade ka tina nu aya naon kumaha sareng atuh mah",
    "tl": "ang ng sa na mga ay at ko mo siya ako ikaw hindi oo po salamat ito iyan kami tayo sila",
    "vi": "và của là có không những được cho trong một các này với người tôi bạn đã rất",
    "es": "el la de que y en los se del las por un para con no una su al es lo como más pero sus le ya o",
    "pt": "o a de que e do da em um para é com não uma os no se na por mais as dos como mas ao ele",
    "fr": "le la de et les des est un une du en que qui dans pour pas sur au avec ce il elle nous vous je",
    "de": "der die und das ist nicht ich ein zu den mit sie es sich des auf für im dem auch eine wir",
    "it": "il di che e la per un non una sono del della in le ho mi è si con ma lo gli anche",
    "nl": "de het een en van is dat niet ik je op te zijn met voor maar wat er ook",
    "tr": "ve bir bu da de için ile çok ne ben sen o var yok değil gibi daha ama mı mi",
    "pl": "i w nie na się to że z do jest jak co ale tak już czy mnie jestem",
    "sw": "na ya wa kwa ni katika la za kuwa hii hiyo mimi wewe sana",
    "ru": "и в не на что я с он как это по но они она мы вы так же",
    "uk": "і в не на що я з він як це по але вони вона ми ви так також",
    "ar": "في من على إلى أن هذا التي الذي مع كان لا ما هو هي",
    "fa": "و در به از که این را با است برای آن یک من شما",
    "ur": "اور کے کی میں ہے سے کو یہ نہیں کہ ہیں تھا",
}
_SETS = {lang: set(words.split()) for lang, words in _WORDS.items()}
_MS_ONLY = set("mahu kerana boleh tetapi sahaja awak hendak mengapa betul bagaimanakah kenderaan percuma".split())
_ID_ONLY = set("mau karena bisa tapi saja kamu ingin kenapa benar gimana nggak enggak gratis".split())
_FAMILY = {"cyrillic": ("ru", "uk"), "arabic": ("ar", "fa", "ur")}


def detect(text: str) -> str | None:
    text = unicodedata.normalize("NFC", text or "")
    letters = [c for c in text if c.isalpha()]
    if len(letters) < 2:
        return None
    n = len(letters)
    for lang, rx in _SCRIPTS:
        if len(rx.findall(text)) / n > 0.2:
            return lang
    if len(_HAN.findall(text)) / n > 0.3:
        return "zh"
    words = [w.lower() for w in _WORD.findall(text)]
    if len(_CYRILLIC.findall(text)) / n > 0.4:
        return _best(words, _FAMILY["cyrillic"]) or "ru"
    if len(_ARABIC.findall(text)) / n > 0.4:
        return _best(words, _FAMILY["arabic"]) or "ar"
    return _best(words, [l for l in _SETS if l not in _FAMILY["cyrillic"] + _FAMILY["arabic"]])


def _best(words: list[str], langs) -> str | None:
    if not words:
        return None
    scores = {l: sum(1 for w in words if w in _SETS[l]) for l in langs}
    best = max(scores, key=scores.get)
    if scores[best] == 0:
        return None
    # Indonesian and Malay share most short words: between the two, only the words each has alone count.
    if best in ("id", "ms") and "id" in scores and "ms" in scores:
        ms_only = sum(1 for w in words if w in _MS_ONLY)
        id_only = sum(1 for w in words if w in _ID_ONLY)
        return "ms" if ms_only > id_only else "id"
    return best
