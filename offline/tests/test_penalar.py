"""Penalar without a model: reading the model's replies, which misheard-word fixes a line takes, the word
list, long-text pieces, and the line flow with its NLLB fallback. Run: python -m unittest discover -s tests"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SENADA_HOME", tempfile.mkdtemp(prefix="senada-test-"))

from senada import catalog, export, reason  # noqa: E402
from senada.core import TranscriptLine  # noqa: E402
from senada.live import interpret  # noqa: E402


class Replies(unittest.TestCase):
    def test_json_inside_chatter_is_found(self):
        got = reason.parse_reply('Sure!\n```json\n{"translation": " “Halo semua” ", "note": ""}\n```')
        self.assertEqual(got["translation"], "Halo semua")
        self.assertEqual(got["note"], "")

    def test_no_translation_is_no_answer(self):
        self.assertIsNone(reason.parse_reply("Let me think about this sentence."))
        self.assertIsNone(reason.parse_reply('{"translation": "  "}'))
        self.assertIsNone(reason.parse_reply('{"translation": 3}'))
        self.assertIsNone(reason.parse_reply('{"translation": "a",'))

    def test_echoed_unclear_mark_becomes_an_ellipsis(self):
        self.assertEqual(reason.parse_reply('{"translation": "UNCLEAR", "note": "x"}')["translation"], "…")
        self.assertEqual(reason.parse_reply('{"translation": "Unclear words", "note": ""}')["translation"], "Unclear words")

    def test_note_that_is_not_text_becomes_empty(self):
        self.assertEqual(reason.parse_reply('{"translation": "x", "note": null}')["note"], "")


class Fixes(unittest.TestCase):
    def test_similar_spelling_with_confidence_is_taken(self):
        self.assertTrue(reason.take_fix("Coevisien", "Koefisien", 0.9, []))

    def test_unsure_or_rephrased_is_dropped(self):
        self.assertFalse(reason.take_fix("Coevisien", "Koefisien", 0.5, []))
        self.assertFalse(reason.take_fix("barang", "payung biru", 0.95, []))
        self.assertFalse(reason.take_fix("rapat", "Rapat", 0.95, []))

    def test_word_list_wins_over_confidence(self):
        self.assertTrue(reason.take_fix("fluk semasa", "fluks massa", 0.3, ["Fluks massa"]))

    def test_hangul_compares_by_letters(self):
        # 거울 (mirror) and 겨울 (winter) differ in one vowel: a plausible mishearing.
        self.assertTrue(reason.take_fix("거울", "겨울", 0.9, []))
        self.assertFalse(reason.take_fix("사과", "회의", 0.9, []))


class Words(unittest.TestCase):
    def test_lines_and_commas_without_repeats(self):
        self.assertEqual(reason.word_list("fluks massa, koefisien\n\n Kookmin \nkoefisien"),
                         ["fluks massa", "koefisien", "Kookmin"])


class Pieces(unittest.TestCase):
    def test_short_text_is_one_piece(self):
        self.assertEqual(reason.chunks("satu\ndua"), ["satu\ndua"])

    def test_long_text_splits_on_paragraphs_and_keeps_everything(self):
        paras = [("kalimat %d " % i) * 30 for i in range(12)]
        text = "\n".join(paras)
        pieces = reason.chunks(text, limit=900)
        self.assertGreater(len(pieces), 1)
        self.assertEqual("\n".join(pieces), text)
        self.assertTrue(all(len(p) <= 900 for p in pieces))


class Pairs(unittest.TestCase):
    def test_regional_languages_go_to_nllb(self):
        self.assertTrue(reason.handles("id", "ko"))
        self.assertTrue(reason.handles("mr", "is"))
        self.assertFalse(reason.handles("min", "id"))
        self.assertFalse(reason.handles("en", "bug"))
        self.assertFalse(reason.handles("arz", "en"))  # Arabic as spoken: NLLB

    def test_penalar_languages_are_listed_ones(self):
        from senada import languages
        self.assertLessEqual(reason.PENALAR, set(languages.BY_ID))

    def test_every_language_has_a_name_for_the_prompt(self):
        from senada import languages
        for l in languages.LANGUAGES:
            self.assertIn(l.id, reason.ENGLISH, l.id)


class FakeReasoner:
    alive = True

    def __init__(self, line=None, fail=False):
        self.line, self.fail, self.seen = line, fail, []

    def translate_line(self, text, src, tgt, recent, topic, words, unsure=False):
        self.unsure = unsure
        self.seen.append((text, list(recent), topic, words))
        if self.fail:
            raise TimeoutError("slow")
        return self.line

    def fix_line(self, text, src, recent, topic, words, unsure=False):
        self.fixed = text
        if self.fail:
            raise TimeoutError("slow")
        return self.line.fixes if self.line else []


class FakeNllb:
    def __init__(self):
        self.asked = []

    def translate(self, text, src, tgt, beam=2):
        self.asked.append(text)
        return "[nllb] " + text


def heard(text, src="id", tgt="en"):
    return TranscriptLine(id="h1-1", t=0.0, speaker="them", src=text, dst=None, srcLang=src, dstLang=tgt)


class LineFlow(unittest.TestCase):
    def test_penalar_fixes_show_in_the_line_and_its_exports(self):
        r = FakeReasoner(reason.Line("The heat transfer coefficient drops.", [("Coevisien", "Koefisien")], ""))
        line, recent = heard("Coevisien perpindahan panas turun."), []
        note = interpret(line, r, FakeNllb(), recent, ("kondensasi", "koefisien"))
        self.assertEqual(note, "")
        self.assertEqual(line.src, "Coevisien perpindahan panas turun.")  # what was heard stays, as in Cicada
        self.assertEqual(line.shown, "Koefisien perpindahan panas turun.")
        self.assertEqual(line.dst, "The heat transfer coefficient drops.")
        self.assertEqual(recent, [(line.shown, line.dst)])
        self.assertIn("Koefisien perpindahan", export.as_text("t", [line]))
        self.assertEqual(r.seen[0][2:], ("kondensasi", "koefisien"))

    def test_context_is_the_lines_before(self):
        r = FakeReasoner(reason.Line("B", [], ""))
        recent = [("a%d" % i, "A%d" % i) for i in range(10)]
        interpret(heard("b"), r, None, recent, ("", ""))
        self.assertEqual(r.seen[0][1][-1], ("a9", "A9"))
        self.assertEqual(len(recent), 8)  # the running context stays short

    def test_failure_falls_back_to_nllb(self):
        nllb = FakeNllb()
        line = heard("Halo")
        interpret(line, FakeReasoner(fail=True), nllb, [], ("", ""))
        self.assertEqual(line.dst, "[nllb] Halo")
        line2 = heard("Halo lagi")
        interpret(line2, FakeReasoner(line=None), nllb, [], ("", ""))
        self.assertEqual(line2.dst, "[nllb] Halo lagi")

    def test_regional_language_skips_penalar(self):
        r, nllb = FakeReasoner(reason.Line("x", [], "")), FakeNllb()
        line = heard("Baa kaba?", src="min", tgt="id")
        interpret(line, r, nllb, [], ("", ""))
        self.assertEqual(r.seen, [])
        self.assertEqual(line.dst, "[nllb] Baa kaba?")

    def test_same_language_is_not_translated_but_misheard_words_are_fixed(self):
        r, nllb = FakeReasoner(reason.Line("", [("Coevisien", "Koefisien")], "")), FakeNllb()
        line = heard("Coevisien naik", src="id", tgt="id")
        interpret(line, r, nllb, [], ("", ""))
        self.assertIsNone(line.dst)
        self.assertEqual(r.seen, [])
        self.assertEqual(nllb.asked, [])
        self.assertEqual(line.shown, "Koefisien naik")

    def test_same_language_fix_failure_keeps_the_line(self):
        line = heard("Halo semua", src="id", tgt="id")
        interpret(line, FakeReasoner(fail=True), None, [], ("", ""))
        self.assertIsNone(line.fixes)
        self.assertEqual(line.shown, "Halo semua")


class Proposed(unittest.TestCase):
    def test_only_quoted_and_sure_fixes_are_taken(self):
        proposed = [{"from": "Coevisien", "to": "Koefisien", "confidence": 0.9},
                    {"from": "tidak ada", "to": "ada", "confidence": 0.99},  # not in the line
                    {"from": "naik", "to": "meningkat tajam", "confidence": 0.95},  # a rephrasing
                    "junk", {"from": "naik", "to": 5}]
        self.assertEqual(reason.taken_fixes(proposed, "Coevisien naik", []), [("Coevisien", "Koefisien")])
        self.assertEqual(reason.taken_fixes(None, "x", []), [])

    def test_note_comes_back(self):
        line = heard("밥 한번 먹자", src="ko", tgt="id")
        note = interpret(line, FakeReasoner(reason.Line("Kapan-kapan makan bareng ya.", [], "Basa-basi sopan.")), None, [], ("", ""))
        self.assertEqual(note, "Basa-basi sopan.")


class SameLanguageText(unittest.TestCase):
    def test_comes_back_unchanged_while_no_engine_is_loaded(self):
        from senada.app import Api
        api = Api()  # engines are not loaded until the window starts
        r = api.translate("밥 먹었어?", "auto", "ko", remember=False)
        self.assertEqual((r.get("text"), r.get("src"), r.get("engine")), ("밥 먹었어?", "ko", "none"))
        self.assertIn("error", api.translate("Halo", "id", "ko", remember=False))


class PenalarCatalog(unittest.TestCase):
    def test_models_and_runtime_are_listed(self):
        llm = [m for m in catalog.MODELS if m.kind == "llm"]
        self.assertEqual({m.id for m in llm}, {"gemma4-e4b", "gemma4-e2b"})
        self.assertIn(catalog.DEFAULT["llm"], catalog.BY_ID)
        self.assertRegex(catalog.LLAMA["sha256"], r"^[0-9a-f]{64}$")

    def test_model_needs_the_runtime_too(self):
        # Under the test home there is no runtime, so no Penalar model counts as installed.
        os.environ["SENADA_MODELS"] = tempfile.mkdtemp(prefix="senada-models-")
        try:
            self.assertFalse(catalog.installed("gemma4-e2b"))
        finally:
            del os.environ["SENADA_MODELS"]


if __name__ == "__main__":
    unittest.main()
