"""The languages both engines know: an id the UI uses, its name in Indonesian and in itself, the NLLB-200
code (translation) and the Whisper code (speech; None when Whisper can't hear it, so text only).
Indonesian, Korean and English come first; the regional languages of Indonesia NLLB knows are here too."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    id: str
    name: str  # in Indonesian
    native: str
    nllb: str
    whisper: str | None


FAVORITES = ("id", "ko", "en")

_TABLE = [
    ("id", "Indonesia", "Bahasa Indonesia", "ind_Latn", "id"),
    ("ko", "Korea", "한국어", "kor_Hang", "ko"),
    ("en", "Inggris", "English", "eng_Latn", "en"),
    ("ja", "Jepang", "日本語", "jpn_Jpan", "ja"),
    ("zh", "Mandarin (Sederhana)", "简体中文", "zho_Hans", "zh"),
    ("zh-Hant", "Mandarin (Tradisional)", "繁體中文", "zho_Hant", "zh"),
    ("yue", "Kanton", "粵語", "yue_Hant", "yue"),
    ("ms", "Melayu", "Bahasa Melayu", "zsm_Latn", "ms"),
    ("jv", "Jawa", "Basa Jawa", "jav_Latn", "jw"),
    ("su", "Sunda", "Basa Sunda", "sun_Latn", "su"),
    ("min", "Minangkabau", "Baso Minang", "min_Latn", None),
    ("ban", "Bali", "Basa Bali", "ban_Latn", None),
    ("bjn", "Banjar", "Bahasa Banjar", "bjn_Latn", None),
    ("bug", "Bugis", "Basa Ugi", "bug_Latn", None),
    ("ace", "Aceh", "Bahsa Acèh", "ace_Latn", None),
    ("tl", "Tagalog", "Tagalog", "tgl_Latn", "tl"),
    ("vi", "Vietnam", "Tiếng Việt", "vie_Latn", "vi"),
    ("th", "Thai", "ไทย", "tha_Thai", "th"),
    ("km", "Khmer", "ខ្មែរ", "khm_Khmr", "km"),
    ("lo", "Laos", "ລາວ", "lao_Laoo", "lo"),
    ("my", "Burma", "မြန်မာ", "mya_Mymr", "my"),
    ("hi", "Hindi", "हिन्दी", "hin_Deva", "hi"),
    ("bn", "Bengali", "বাংলা", "ben_Beng", "bn"),
    ("ur", "Urdu", "اردو", "urd_Arab", "ur"),
    ("ta", "Tamil", "தமிழ்", "tam_Taml", "ta"),
    ("te", "Telugu", "తెలుగు", "tel_Telu", "te"),
    ("ne", "Nepal", "नेपाली", "npi_Deva", "ne"),
    ("si", "Sinhala", "සිංහල", "sin_Sinh", "si"),
    ("ar", "Arab", "العربية", "arb_Arab", "ar"),
    ("fa", "Persia", "فارسی", "pes_Arab", "fa"),
    ("he", "Ibrani", "עברית", "heb_Hebr", "he"),
    ("tr", "Turki", "Türkçe", "tur_Latn", "tr"),
    ("ru", "Rusia", "Русский", "rus_Cyrl", "ru"),
    ("uk", "Ukraina", "Українська", "ukr_Cyrl", "uk"),
    ("kk", "Kazakh", "Қазақ", "kaz_Cyrl", "kk"),
    ("uz", "Uzbek", "Oʻzbek", "uzn_Latn", "uz"),
    ("mn", "Mongol", "Монгол", "khk_Cyrl", "mn"),
    ("de", "Jerman", "Deutsch", "deu_Latn", "de"),
    ("fr", "Prancis", "Français", "fra_Latn", "fr"),
    ("es", "Spanyol", "Español", "spa_Latn", "es"),
    ("pt", "Portugis", "Português", "por_Latn", "pt"),
    ("it", "Italia", "Italiano", "ita_Latn", "it"),
    ("nl", "Belanda", "Nederlands", "nld_Latn", "nl"),
    ("pl", "Polandia", "Polski", "pol_Latn", "pl"),
    ("cs", "Ceko", "Čeština", "ces_Latn", "cs"),
    ("sk", "Slowakia", "Slovenčina", "slk_Latn", "sk"),
    ("hu", "Hungaria", "Magyar", "hun_Latn", "hu"),
    ("ro", "Rumania", "Română", "ron_Latn", "ro"),
    ("bg", "Bulgaria", "Български", "bul_Cyrl", "bg"),
    ("el", "Yunani", "Ελληνικά", "ell_Grek", "el"),
    ("sr", "Serbia", "Српски", "srp_Cyrl", "sr"),
    ("hr", "Kroasia", "Hrvatski", "hrv_Latn", "hr"),
    ("sl", "Slovenia", "Slovenščina", "slv_Latn", "sl"),
    ("sv", "Swedia", "Svenska", "swe_Latn", "sv"),
    ("no", "Norwegia", "Norsk", "nob_Latn", "no"),
    ("da", "Denmark", "Dansk", "dan_Latn", "da"),
    ("fi", "Finlandia", "Suomi", "fin_Latn", "fi"),
    ("et", "Estonia", "Eesti", "est_Latn", "et"),
    ("lv", "Latvia", "Latviešu", "lvs_Latn", "lv"),
    ("lt", "Lituania", "Lietuvių", "lit_Latn", "lt"),
    ("ca", "Katalan", "Català", "cat_Latn", "ca"),
    ("eu", "Basque", "Euskara", "eus_Latn", "eu"),
    ("gl", "Galisia", "Galego", "glg_Latn", "gl"),
    ("cy", "Wales", "Cymraeg", "cym_Latn", "cy"),
    ("ka", "Georgia", "ქართული", "kat_Geor", "ka"),
    ("hy", "Armenia", "Հայերեն", "hye_Armn", "hy"),
    ("az", "Azerbaijan", "Azərbaycan", "azj_Latn", "az"),
    ("sw", "Swahili", "Kiswahili", "swh_Latn", "sw"),
    ("am", "Amhara", "አማርኛ", "amh_Ethi", "am"),
    ("yo", "Yoruba", "Yorùbá", "yor_Latn", "yo"),
    ("ha", "Hausa", "Hausa", "hau_Latn", "ha"),
    ("so", "Somali", "Soomaali", "som_Latn", "so"),
    ("af", "Afrikaans", "Afrikaans", "afr_Latn", "af"),
]

LANGUAGES = [Language(*row) for row in _TABLE]
BY_ID = {lang.id: lang for lang in LANGUAGES}
# Whisper names a language once; the first entry with that code wins (zh -> Simplified).
BY_WHISPER: dict[str, Language] = {}
for _lang in LANGUAGES:
    if _lang.whisper and _lang.whisper not in BY_WHISPER:
        BY_WHISPER[_lang.whisper] = _lang


def get(lang_id: str) -> Language:
    try:
        return BY_ID[lang_id]
    except KeyError:
        raise ValueError(f"unknown language: {lang_id}") from None


def from_whisper(code: str | None) -> Language | None:
    return BY_WHISPER.get(code or "")


def as_json() -> list[dict]:
    return [{"id": l.id, "name": l.name, "native": l.native, "speech": l.whisper is not None,
             "favorite": l.id in FAVORITES} for l in LANGUAGES]
