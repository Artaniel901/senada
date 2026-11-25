"""The languages both engines know: an id the UI uses, its name in Indonesian and in itself, the NLLB-200
code (translation) and the Whisper code (speech; None when Whisper can't hear it, so text only).
Indonesian, Korean and English come first; then every other language NLLB-200 translates (202 in all),
including the regional languages of Indonesia."""
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
    ("no", "Norwegia (Bokmål)", "Norsk bokmål", "nob_Latn", "no"),
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
    # The rest of NLLB-200: every language it translates is offered. Whisper hears only some of them,
    # so the others are for typed text.
    # Asia
    ("mr", "Marathi", "मराठी", "mar_Deva", "mr"),
    ("gu", "Gujarati", "ગુજરાતી", "guj_Gujr", "gu"),
    ("pa", "Punjabi", "ਪੰਜਾਬੀ", "pan_Guru", "pa"),
    ("kn", "Kannada", "ಕನ್ನಡ", "kan_Knda", "kn"),
    ("ml", "Malayalam", "മലയാളം", "mal_Mlym", "ml"),
    ("or", "Odia", "ଓଡ଼ିଆ", "ory_Orya", None),
    ("as", "Assam", "অসমীয়া", "asm_Beng", "as"),
    ("sd", "Sindhi", "سنڌي", "snd_Arab", "sd"),
    ("ps", "Pashto", "پښتو", "pbt_Arab", "ps"),
    ("prs", "Dari", "دری", "prs_Arab", None),
    ("ks", "Kashmir (Arab)", "کٲشُر", "kas_Arab", None),
    ("ks-Deva", "Kashmir (Dewanagari)", "कॉशुर", "kas_Deva", None),
    ("sa", "Sanskerta", "संस्कृतम्", "san_Deva", "sa"),
    ("mai", "Maithili", "मैथिली", "mai_Deva", None),
    ("bho", "Bhojpuri", "भोजपुरी", "bho_Deva", None),
    ("awa", "Awadhi", "अवधी", "awa_Deva", None),
    ("mag", "Magahi", "मगही", "mag_Deva", None),
    ("hne", "Chhattisgarhi", "छत्तीसगढ़ी", "hne_Deva", None),
    ("mni", "Manipuri", "মৈতৈলোন্", "mni_Beng", None),
    ("sat", "Santali", "ᱥᱟᱱᱛᱟᱲᱤ", "sat_Beng", None),  # NLLB names it sat_Beng; its data is Ol Chiki
    ("lus", "Mizo", "Mizo ṭawng", "lus_Latn", None),
    ("bo", "Tibet", "བོད་སྐད།", "bod_Tibt", "bo"),
    ("dz", "Dzongkha", "རྫོང་ཁ", "dzo_Tibt", None),
    ("ky", "Kirgiz", "Кыргызча", "kir_Cyrl", None),
    ("tg", "Tajik", "Тоҷикӣ", "tgk_Cyrl", "tg"),
    ("tk", "Turkmen", "Türkmençe", "tuk_Latn", "tk"),
    ("tt", "Tatar", "Татарча", "tat_Cyrl", "tt"),
    ("ba", "Bashkir", "Башҡортса", "bak_Cyrl", "ba"),
    ("ug", "Uighur", "ئۇيغۇرچە", "uig_Arab", None),
    ("azb", "Azerbaijan Selatan", "تۆرکجه", "azb_Arab", None),
    ("crh", "Tatar Krimea", "Qırımtatarca", "crh_Latn", None),
    ("shn", "Shan", "တႆး", "shn_Mymr", None),
    ("kac", "Kachin", "Jinghpaw", "kac_Latn", None),
    ("ceb", "Cebuano", "Sinugboanon", "ceb_Latn", None),
    ("ilo", "Ilokano", "Ilokano", "ilo_Latn", None),
    ("war", "Waray", "Winaray", "war_Latn", None),
    ("pag", "Pangasinan", "Pangasinan", "pag_Latn", None),
    ("ace-Arab", "Aceh (Jawi)", "بهسا اچيه", "ace_Arab", None),
    ("bjn-Arab", "Banjar (Jawi)", "بهاس بنجر", "bjn_Arab", None),
    # Pacific
    ("tpi", "Tok Pisin", "Tok Pisin", "tpi_Latn", None),
    ("fj", "Fiji", "Vosa Vakaviti", "fij_Latn", None),
    ("sm", "Samoa", "Gagana Sāmoa", "smo_Latn", None),
    ("mi", "Maori", "Te Reo Māori", "mri_Latn", "mi"),
    # Arabic as spoken, Kurdish, Yiddish
    ("arz", "Arab Mesir", "العربية المصرية", "arz_Arab", None),
    ("ary", "Arab Maroko", "الدارجة المغربية", "ary_Arab", None),
    ("aeb", "Arab Tunisia", "الدارجة التونسية", "aeb_Arab", None),
    ("apc", "Arab Syam Utara", "العربية الشامية الشمالية", "apc_Arab", None),
    ("ajp", "Arab Syam Selatan", "العربية الشامية الجنوبية", "ajp_Arab", None),
    ("acm", "Arab Irak", "العربية العراقية", "acm_Arab", None),
    ("acq", "Arab Yaman (Taizz-Aden)", "العربية التعزية العدنية", "acq_Arab", None),
    ("ars", "Arab Najd", "العربية النجدية", "ars_Arab", None),
    ("ckb", "Kurdi Sorani", "کوردیی ناوەندی", "ckb_Arab", None),
    ("ku", "Kurdi Kurmanji", "Kurmancî", "kmr_Latn", None),
    ("yi", "Yiddi", "ייִדיש", "ydd_Hebr", "yi"),
    # Europe
    ("is", "Islandia", "Íslenska", "isl_Latn", "is"),
    ("fo", "Faroe", "Føroyskt", "fao_Latn", "fo"),
    ("nn", "Norwegia (Nynorsk)", "Nynorsk", "nno_Latn", "nn"),
    ("ga", "Irlandia", "Gaeilge", "gle_Latn", None),
    ("gd", "Gaelik Skotlandia", "Gàidhlig", "gla_Latn", None),
    ("lb", "Luksemburg", "Lëtzebuergesch", "ltz_Latn", "lb"),
    ("li", "Limburg", "Limburgs", "lim_Latn", None),
    ("mt", "Malta", "Malti", "mlt_Latn", "mt"),
    ("mk", "Makedonia", "Македонски", "mkd_Cyrl", "mk"),
    ("sq", "Albania", "Shqip", "als_Latn", "sq"),
    ("bs", "Bosnia", "Bosanski", "bos_Latn", "bs"),
    ("be", "Belarus", "Беларуская", "bel_Cyrl", "be"),
    ("ltg", "Latgalia", "Latgalīšu", "ltg_Latn", None),
    ("szl", "Silesia", "Ślōnsko", "szl_Latn", None),
    ("oc", "Oksitan", "Occitan", "oci_Latn", "oc"),
    ("ast", "Asturia", "Asturianu", "ast_Latn", None),
    ("sc", "Sardinia", "Sardu", "srd_Latn", None),
    ("scn", "Sisilia", "Sicilianu", "scn_Latn", None),
    ("vec", "Venesia", "Vèneto", "vec_Latn", None),
    ("lij", "Liguria", "Ligure", "lij_Latn", None),
    ("lmo", "Lombardia", "Lombard", "lmo_Latn", None),
    ("fur", "Friuli", "Furlan", "fur_Latn", None),
    ("eo", "Esperanto", "Esperanto", "epo_Latn", None),
    # The Americas
    ("ht", "Kreol Haiti", "Kreyòl ayisyen", "hat_Latn", "ht"),
    ("pap", "Papiamento", "Papiamentu", "pap_Latn", None),
    ("qu", "Quechua", "Runasimi", "quy_Latn", None),
    ("ay", "Aymara", "Aymar aru", "ayr_Latn", None),
    ("gn", "Guarani", "Avañe'ẽ", "grn_Latn", None),
    # Africa
    ("zu", "Zulu", "isiZulu", "zul_Latn", None),
    ("xh", "Xhosa", "isiXhosa", "xho_Latn", None),
    ("ig", "Igbo", "Igbo", "ibo_Latn", None),
    ("rw", "Kinyarwanda", "Ikinyarwanda", "kin_Latn", None),
    ("rn", "Kirundi", "Ikirundi", "run_Latn", None),
    ("mg", "Malagasi", "Malagasy", "plt_Latn", "mg"),
    ("ln", "Lingala", "Lingála", "lin_Latn", "ln"),
    ("sn", "Shona", "chiShona", "sna_Latn", "sn"),
    ("ny", "Chichewa", "Chicheŵa", "nya_Latn", None),
    ("st", "Sotho Selatan", "Sesotho", "sot_Latn", None),
    ("nso", "Sotho Utara", "Sesotho sa Leboa", "nso_Latn", None),
    ("tn", "Tswana", "Setswana", "tsn_Latn", None),
    ("ts", "Tsonga", "Xitsonga", "tso_Latn", None),
    ("ss", "Swati", "siSwati", "ssw_Latn", None),
    ("ti", "Tigrinya", "ትግርኛ", "tir_Ethi", None),
    ("om", "Oromo", "Afaan Oromoo", "gaz_Latn", None),
    ("lg", "Luganda", "Luganda", "lug_Latn", None),
    ("luo", "Luo", "Dholuo", "luo_Latn", None),
    ("ki", "Kikuyu", "Gĩkũyũ", "kik_Latn", None),
    ("kam", "Kamba", "Kikamba", "kam_Latn", None),
    ("wo", "Wolof", "Wolof", "wol_Latn", None),
    ("ff", "Fula", "Fulfulde", "fuv_Latn", None),
    ("bm", "Bambara", "Bamanankan", "bam_Latn", None),
    ("ak", "Akan", "Akan", "aka_Latn", None),
    ("tw", "Twi", "Twi", "twi_Latn", None),
    ("ee", "Ewe", "Eʋegbe", "ewe_Latn", None),
    ("fon", "Fon", "Fɔngbè", "fon_Latn", None),
    ("mos", "Mossi", "Mooré", "mos_Latn", None),
    ("dyu", "Dyula", "Julakan", "dyu_Latn", None),
    ("kbp", "Kabiye", "Kabɩyɛ", "kbp_Latn", None),
    ("kea", "Kreol Tanjung Verde", "Kabuverdianu", "kea_Latn", None),
    ("sg", "Sango", "Sängö", "sag_Latn", None),
    ("kg", "Kongo", "Kikongo", "kon_Latn", None),
    ("lua", "Luba-Kasai", "Tshiluba", "lua_Latn", None),
    ("kmb", "Kimbundu", "Kimbundu", "kmb_Latn", None),
    ("umb", "Umbundu", "Umbundu", "umb_Latn", None),
    ("cjk", "Chokwe", "Chokwe", "cjk_Latn", None),
    ("bem", "Bemba", "Ichibemba", "bem_Latn", None),
    ("tum", "Tumbuka", "Chitumbuka", "tum_Latn", None),
    ("din", "Dinka", "Thuɔŋjäŋ", "dik_Latn", None),
    ("nus", "Nuer", "Thok Naath", "nus_Latn", None),
    ("kab", "Kabyle", "Taqbaylit", "kab_Latn", None),
    ("tzm", "Tamazight Atlas Tengah", "ⵜⴰⵎⴰⵣⵉⵖⵜ", "tzm_Tfng", None),
    ("taq", "Tamasheq (Latin)", "Tamajaq", "taq_Latn", None),
    ("taq-Tfng", "Tamasheq (Tifinagh)", "ⵜⴰⵎⴰⵌⴰⵇ", "taq_Tfng", None),
    ("knc", "Kanuri (Latin)", "Kanuri", "knc_Latn", None),
    ("knc-Arab", "Kanuri (Arab)", "كانوري", "knc_Arab", None),
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
