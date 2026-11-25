"""Live hearing without a speech model: what Whisper wrote that can't be speech, choosing the language only
among the expected ones, the speech segmenter on sound with no voice, and the settings that feed them.
Run: python -m unittest discover -s tests"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SENADA_HOME", tempfile.mkdtemp(prefix="senada-test-"))

from senada import asr, speech  # noqa: E402
from senada.app import _hearable  # noqa: E402


class Plausible(unittest.TestCase):
    def test_real_lines_pass(self):
        self.assertTrue(speech.plausible("Jadi kemarin aku udah coba, tapi hasilnya belum sesuai.", "id"))
        self.assertTrue(speech.plausible("그거 진짜 별로였어, meeting은 취소야.", "ko"))  # English inside Korean
        self.assertTrue(speech.plausible("会议三点开始", "zh"))

    def test_the_khmer_line_heard_for_indonesian_is_dropped(self):
        # From a real session: Whisper small wrote this for Indonesian under music and called it Javanese.
        self.assertFalse(speech.plausible("តំំំំំំំំ", "jv"))
        self.assertFalse(speech.plausible("តំំំំំំំំ", "id"))

    def test_repeated_letter_is_noise(self):
        self.assertFalse(speech.plausible("aaaaaaaaaaa", "id"))
        self.assertFalse(speech.plausible("", "id"))

    def test_one_word_over_and_over_is_noise(self):
        # From a real mic session: a tap on the laptop heard as this.
        self.assertFalse(speech.plausible("dis dis dis dis dis", "id"))
        self.assertTrue(speech.plausible("Iya, iya, iya, iya, betul sekali itu yang saya maksud kemarin sore.", "id"))

    def test_wrong_script_for_the_language(self):
        self.assertFalse(speech.plausible("Halo semuanya apa kabar", "ko"))
        self.assertTrue(speech.plausible("Halo semuanya apa kabar", None))


class FakeWhisper:
    """detect_language's reply: Whisper's own top choices, the case from the real session."""
    def __init__(self, probs):
        self.probs, self.asked = probs, 0

    def detect_language(self, audio=None):
        self.asked += 1
        return self.probs[0][0], self.probs[0][1], self.probs


def recognizer(probs):
    r = asr.Recognizer.__new__(asr.Recognizer)
    r.model = FakeWhisper(probs)
    return r


class Candidates(unittest.TestCase):
    def test_only_expected_languages_are_chosen(self):
        # Whisper's own pick was Javanese; among Indonesian, Korean and English, Indonesian leads.
        r = recognizer([("jw", 0.46), ("id", 0.30), ("ms", 0.15), ("ko", 0.02), ("en", 0.03)])
        lang, share = r._choose(None, ["id", "ko", "en"])
        self.assertEqual(lang, "id")
        self.assertAlmostEqual(share, 0.30 / 0.35)

    def test_one_candidate_skips_detection(self):
        r = recognizer([("en", 1.0)])
        self.assertEqual(r._choose(None, ["ko"]), ("ko", 1.0))
        self.assertEqual(r.model.asked, 0)

    def test_unknown_or_unheard_candidates_are_ignored(self):
        r = recognizer([("id", 0.9)])
        self.assertEqual(r._choose(None, ["klingon", "min"]), (None, 0.0))  # Minangkabau: text only


class Seg:
    def __init__(self, no_speech_prob, avg_logprob):
        self.no_speech_prob, self.avg_logprob = no_speech_prob, avg_logprob


class NoiseFilter(unittest.TestCase):
    def test_whisper_signs_of_noise(self):
        self.assertTrue(asr._speech(Seg(0.05, -0.3)))
        self.assertFalse(asr._speech(Seg(0.8, -0.2)))  # it says nothing was said
        self.assertFalse(asr._speech(Seg(0.5, -1.0)))  # probably nothing, and unsure of the words
        self.assertFalse(asr._speech(Seg(0.1, -1.6)))  # words it hardly believes


class Segmenter(unittest.TestCase):
    def test_music_and_silence_without_voice_make_no_lines(self):
        import numpy as np
        out = []
        seg = speech.SpeechSegmenter()
        seg.on_segment = out.append
        t = np.arange(16000 * 6) / 16000
        tone = 0.3 * np.sin(2 * np.pi * 440 * t) + 0.2 * np.sin(2 * np.pi * 660 * t)
        pcm = (np.concatenate([np.zeros(16000 * 2), tone]) * 32767).astype(np.int16).tobytes()
        for i in range(0, len(pcm), 3200):
            seg.feed(pcm[i:i + 3200])
        seg.flush()
        self.assertEqual(out, [])
        self.assertLess(len(seg._buf), 16000)  # the waiting audio doesn't grow without speech


class Joining(unittest.TestCase):
    """Scraps like "mana" or "THIS" came out alone and misheard; a breath inside a sentence must not cut it."""
    S = 16000

    def spans(self, *pairs):
        return speech.SpeechSegmenter()._join([{"start": int(a * self.S), "end": int(b * self.S)} for a, b in pairs])

    def test_short_scrap_joins_the_speech_after_it(self):
        self.assertEqual(self.spans((0, 0.5), (0.9, 3.0)), [{"start": 0, "end": 3 * self.S}])

    def test_short_scrap_alone_after_a_long_quiet(self):
        self.assertEqual(len(self.spans((0, 0.5), (2.0, 3.0))), 2)

    def test_full_sentences_stay_apart(self):
        self.assertEqual(len(self.spans((0, 2.0), (2.5, 4.0))), 2)


class Partial(unittest.TestCase):
    def test_a_sentence_still_spoken_is_handed_over_while_it_goes_on(self):
        import numpy as np
        seg = speech.SpeechSegmenter()
        looks, done = [], []
        seg.on_partial, seg.on_segment = looks.append, done.append
        # Stand in for the voice detector: one span from 0.5 s to the end of what has arrived.
        import faster_whisper.vad as vad
        real = vad.get_speech_timestamps
        vad.get_speech_timestamps = lambda audio, *a, **k: [{"start": 8000, "end": len(audio)}]
        try:
            for _ in range(40):  # 4 s of "speech", 100 ms at a time
                seg.feed(np.full(1600, 1000, dtype=np.int16).tobytes())
        finally:
            vad.get_speech_timestamps = real
        self.assertEqual(done, [])
        self.assertGreaterEqual(len(looks), 3)  # about one look every 0.8 s
        self.assertEqual(looks[0].start, 0.5)


class FakeHearing:
    def hear(self, samples, language=None, candidates=None, prompt="", fallback=True):
        return asr.Heard(text="Kita mulai rapatnya sekarang.", lang=language or "id", probability=1.0)


class FakePenalar:
    alive = True

    def __init__(self):
        self.calls = 0

    def translate_line(self, *a, **k):
        self.calls += 1
        from senada.reason import Line
        return Line("We start the meeting now.", [], "")


class FakeNllb:
    def translate(self, text, src, tgt, beam=2):
        return "NLLB: " + text


class FakeStore:
    def __init__(self):
        self.lines = []

    def append(self, sid, line):
        self.lines.append(line)


class Pipeline(unittest.TestCase):
    """Words show the moment Whisper has them; Penalar only fills in, and steps aside when lines pile up."""

    def session(self):
        from senada.live import LiveSession
        events = []
        s = LiveSession(FakeHearing(), FakeNllb(), FakeStore(), "mic", "id", "en", events.append, reasoner=FakePenalar())
        return s, events

    def test_heard_words_show_before_the_translation(self):
        s, events = self.session()
        s._hear(speech.Stretch(b"\0" * 3200, 1.0, 1))
        self.assertEqual([e["type"] for e in events], ["line"])
        self.assertTrue(events[0]["translating"])
        self.assertEqual(events[0]["src"], "Kita mulai rapatnya sekarang.")
        self.assertEqual(s._finish.qsize(), 1)
        s._complete(*s._finish.get())
        self.assertEqual(events[-1]["dst"], "We start the meeting now.")
        self.assertEqual(s.reasoner.calls, 1)

    def test_lines_waiting_behind_go_to_nllb(self):
        s, events = self.session()
        s._hear(speech.Stretch(b"\0" * 3200, 1.0, 1))
        s._hear(speech.Stretch(b"\0" * 3200, 4.0, 2))
        s._complete(*s._finish.get())  # one more is waiting: no Penalar for this one
        self.assertEqual(events[-1]["dst"], "NLLB: Kita mulai rapatnya sekarang.")
        s._complete(*s._finish.get())  # the last one has Penalar again
        self.assertEqual(events[-1]["dst"], "We start the meeting now.")
        self.assertEqual(s.reasoner.calls, 1)

    def test_whisper_hears_with_the_users_terms_only(self):
        s, _ = self.session()
        s.hints = lambda: ("", "fluks massa\nKookmin University")
        asked = []
        s.recognizer.hear = lambda samples, **k: asked.append(k.get("prompt")) or FakeHearing().hear(samples, **k)
        s._hear(speech.Stretch(b"\0" * 3200, 1.0, 1))
        s._hear(speech.Stretch(b"\0" * 3200, 4.0, 2))  # not the sentence before: it misled Whisper on FLEURS
        self.assertEqual(asked, ["fluks massa, Kookmin University."] * 2)


class Settings(unittest.TestCase):
    def test_hearable_keeps_known_speech_languages_once(self):
        self.assertEqual(_hearable(["id", "ko", "id", "min", "klingon", 3, "en"]), ["id", "ko", "en"])
        self.assertEqual(_hearable("id"), [])


if __name__ == "__main__":
    unittest.main()
