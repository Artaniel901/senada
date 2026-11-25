"""Unit tests for the parts that need no model: languages, text detection, sentence splitting,
history, export and the record titles. Run: python -m unittest discover -s tests"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ["CICADA_OFFLINE_HOME"] = tempfile.mkdtemp(prefix="cicada-offline-test-")

from cicada_offline import catalog, detect, export, languages  # noqa: E402
from cicada_offline.core import TranscriptLine  # noqa: E402
from cicada_offline.store import History, Settings  # noqa: E402
from cicada_offline.translate import split_sentences  # noqa: E402


class Languages(unittest.TestCase):
    def test_favourites_first_and_unique(self):
        ids = [l.id for l in languages.LANGUAGES]
        self.assertEqual(ids[:3], ["id", "ko", "en"])
        self.assertEqual(len(ids), len(set(ids)))

    def test_every_language_has_an_nllb_code(self):
        for l in languages.LANGUAGES:
            self.assertRegex(l.nllb, r"^[a-z]{3}_[A-Z][a-z]{3}$", l.id)

    def test_whisper_codes_map_back(self):
        self.assertEqual(languages.from_whisper("ko").id, "ko")
        self.assertEqual(languages.from_whisper("jw").id, "jv")
        self.assertEqual(languages.from_whisper("zh").id, "zh")  # Simplified wins over Traditional
        self.assertIsNone(languages.from_whisper("xx"))

    def test_indonesian_regional_languages_are_text_only(self):
        for lid in ("min", "ban", "bjn", "bug", "ace"):
            self.assertIsNone(languages.get(lid).whisper)

    def test_unknown_language_is_an_error(self):
        with self.assertRaises(ValueError):
            languages.get("klingon")


class Detect(unittest.TestCase):
    def test_scripts(self):
        self.assertEqual(detect.detect("오늘 회의는 세 시에 시작합니다"), "ko")
        self.assertEqual(detect.detect("今日はいい天気ですね"), "ja")
        self.assertEqual(detect.detect("今天天气很好"), "zh")
        self.assertEqual(detect.detect("สวัสดีครับ"), "th")

    def test_latin_languages(self):
        self.assertEqual(detect.detect("Saya sedang menulis tesis tentang kondensasi dan hasilnya belum ada"), "id")
        self.assertEqual(detect.detect("The results of the experiment are in the attached figure"), "en")
        self.assertEqual(detect.detect("Der Bericht ist nicht fertig und ich habe keine Zeit"), "de")

    def test_malay_needs_malay_only_words(self):
        self.assertEqual(detect.detect("Saya tidak tahu apa yang mereka mahu kerana mereka belum datang"), "ms")
        self.assertEqual(detect.detect("Saya tidak tahu apa yang mereka mau karena mereka belum datang"), "id")

    def test_too_little_to_tell(self):
        self.assertIsNone(detect.detect(""))
        self.assertIsNone(detect.detect("123 !!"))


class Sentences(unittest.TestCase):
    def test_split_keeps_punctuation(self):
        self.assertEqual(split_sentences("Halo. Apa kabar? Baik!"), ["Halo.", "Apa kabar?", "Baik!"])

    def test_cjk_full_stops(self):
        self.assertEqual(split_sentences("今日は晴れ。明日は雨？"), ["今日は晴れ。", "明日は雨？"])

    def test_no_empty_parts(self):
        self.assertEqual(split_sentences("   "), [])
        self.assertEqual(split_sentences("Tanpa titik"), ["Tanpa titik"])


class FakeModel:
    """Stands in for CTranslate2: 'translates' by upper-casing, so the plumbing can be checked."""
    class Hyp:
        def __init__(self, tokens):
            self.hypotheses = [tokens]

    def __init__(self):
        self.calls = 0

    def translate_batch(self, source, target_prefix, **_):
        self.calls += 1
        return [self.Hyp([p[0]] + [t.upper() for t in s[1:-1]]) for s, p in zip(source, target_prefix)]


class FakeSp:
    def encode(self, text, out_type=str):
        return text.split(" ")

    def decode(self, tokens):
        return " ".join(tokens)


class TranslatorPlumbing(unittest.TestCase):
    def make(self):
        from collections import OrderedDict
        import threading
        from cicada_offline.translate import Translator
        t = Translator.__new__(Translator)
        t.model, t.sp, t.device, t.model_id = FakeModel(), FakeSp(), "cpu", "fake"
        t._cache, t._gate = OrderedDict(), threading.Lock()
        return t

    def test_line_breaks_survive(self):
        t = self.make()
        self.assertEqual(t.translate("satu dua.\ntiga.", "id", "en"), "SATU DUA.\nTIGA.")

    def test_same_language_is_untouched(self):
        t = self.make()
        self.assertEqual(t.translate("halo", "id", "id"), "halo")
        self.assertEqual(t.model.calls, 0)

    def test_cache_skips_the_model(self):
        t = self.make()
        t.translate("halo dunia.", "id", "en")
        t.translate("halo dunia.", "id", "en")
        self.assertEqual(t.model.calls, 1)

    def test_cjk_target_joins_without_spaces(self):
        t = self.make()
        self.assertEqual(t.translate("a. b.", "en", "ja"), "A.B.")


class Stores(unittest.TestCase):
    def test_settings_ignore_unknown_and_wrong_types(self):
        s = Settings()
        s.update({"textTgt": "en", "nope": 1, "overlaySize": "big"})
        again = Settings()
        self.assertEqual(again.get("textTgt"), "en")
        self.assertEqual(again.get("overlaySize"), 28)
        self.assertNotIn("nope", again.values)

    def test_history_keeps_only_the_latest_of_growing_text(self):
        h = History()
        h.clear()
        h.add("id", "en", "Halo", "Hello")
        h.add("id", "en", "Halo semua", "Hello everyone")
        h.add("id", "en", "Sampai jumpa", "Goodbye")
        self.assertEqual([i["text"] for i in History().items], ["Sampai jumpa", "Halo semua"])


class Export(unittest.TestCase):
    lines = [TranscriptLine(id="h1-1", t=1.5, src="안녕하세요", dst="Halo", srcLang="ko", dstLang="id"),
             TranscriptLine(id="h1-2", t=65.0, src="Selamat pagi", dst=None, srcLang="id", dstLang="id")]

    def test_srt(self):
        srt = export.as_srt(self.lines)
        self.assertIn("1\n00:00:01,500 --> 00:00:09,500\nHalo\n", srt)
        self.assertIn("2\n00:01:05,000 --> 00:01:09,000\nSelamat pagi\n", srt)

    def test_text_and_markdown(self):
        self.assertIn("[00:00:01] 안녕하세요\n           Halo", export.as_text("Rapat", self.lines))
        md = export.as_markdown("Rapat", self.lines)
        self.assertIn("| 00:01:05 | Selamat pagi |  |", md)


class Titles(unittest.TestCase):
    def test_indonesian_title_unless_renamed(self):
        from cicada_offline.app import Api
        from cicada_offline.core import Session
        s = Session(id="x", title="会议 11月25日 18:06", startedAt=datetime(2026, 11, 25, 9, 6, tzinfo=timezone.utc))
        self.assertTrue(Api._title(s).startswith("Rekaman 25 Nov "))
        s.renamed, s.title = True, "Kuliah termodinamika"
        self.assertEqual(Api._title(s), "Kuliah termodinamika")


class Catalog(unittest.TestCase):
    def test_models_are_consistent(self):
        for kind, mid in catalog.DEFAULT.items():
            self.assertEqual(catalog.BY_ID[mid].kind, kind)
        self.assertEqual(len(catalog.GPU["sha256"]), 64)

    def test_remove_ignores_unknown_ids(self):
        catalog.remove("../../etc")  # must not touch anything outside models/


if __name__ == "__main__":
    unittest.main()
