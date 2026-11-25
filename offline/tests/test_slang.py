import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from senada import slang  # noqa: E402


class Lists(unittest.TestCase):
    def test_every_row_has_forms_and_something_to_give(self):
        for lang in ("id", "ko", "en"):
            words = slang._load(lang)
            self.assertGreater(len(words), 70, lang)
            for w in words:
                self.assertTrue(w.form, lang)
                self.assertTrue(w.plain or w.meaning, (lang, w.form))


class Find(unittest.TestCase):
    def test_slang_found_in_order_everyday_words_left_out(self):
        notes = slang.notes("Gue lagi gabut banget nih, ada yang mau mabar?", "id")
        self.assertTrue(notes.startswith("gabut = "))
        self.assertIn("mabar = ", notes)
        self.assertNotIn("gue", notes)  # Gemma knows it; it is only swapped for NLLB

    def test_whole_words_only_outside_korean(self):
        self.assertEqual(slang.find("Dia makan kepiting", "id"), [])  # "kepo" is not in "kepiting"
        self.assertEqual(slang.find("He is a mediocre tbhx", "en"), [])

    def test_longest_form_wins(self):
        forms = [w.form for w in slang.find("Nggak ngotak sih itu orang", "id")]
        self.assertEqual(forms, ["nggak ngotak"])
        forms = [w.form for w in slang.find("ㅇㅈ? ㅇㅇㅈ.", "ko")]
        self.assertEqual(forms, ["ㅇㅈ", "ㅇㅇㅈ"])

    def test_korean_with_endings(self):
        forms = [w.form for w in slang.find("킹받네 진짜, 존맛탱이다, TMI였어", "ko")]
        self.assertEqual(forms, ["킹받", "존맛탱", "tmi"])

    def test_off_switch(self):
        slang.ENABLED = False
        try:
            self.assertEqual(slang.find("gabut", "id"), [])
            self.assertEqual(slang.plain("gak", "id"), "gak")
        finally:
            slang.ENABLED = True


class Plain(unittest.TestCase):
    def test_swaps_safe_words_for_nllb(self):
        self.assertEqual(slang.plain("Gue lagi mager, gak mau keluar.", "id"), "saya lagi malas bergerak, tidak mau keluar.")
        self.assertEqual(slang.plain("No cap, he's lowkey kinda mid ngl.", "en"),
                         "honestly, he's kind of kind of mid not going to lie.")

    def test_leaves_words_with_an_ordinary_sense(self):
        self.assertEqual(slang.plain("Ini mah red flag, mending cabut aja.", "id"), "Ini mah red flag, mending cabut saja.")

    def test_korean_stem_with_ending_is_left_whole(self):
        self.assertEqual(slang.plain("이거 존맛탱이다. 어쩔티비~", "ko"), "이거 존맛탱이다. 어쩌라고~")
        self.assertEqual(slang.plain("TMI였어", "ko"), "너무 많은 정보였어")


class User(unittest.TestCase):
    def tearDown(self):
        slang.set_user("")

    def test_own_words_any_language_and_first(self):
        slang.set_user("gabut = lagi santai di kos\nbaris tanpa tanda sama dengan\n= kosong\nmeong =")
        self.assertEqual(len(slang._user), 1)
        self.assertTrue(slang.notes("aku gabut", "ko").startswith("gabut = lagi santai di kos"))
        self.assertEqual(slang.notes("aku gabut", "id"), "gabut = lagi santai di kos")  # once, the user's

    def test_own_words_are_not_swapped_for_nllb(self):
        slang.set_user("wibu = suka anime")
        self.assertEqual(slang.plain("dia wibu", "en"), "dia wibu")


if __name__ == "__main__":
    unittest.main()
