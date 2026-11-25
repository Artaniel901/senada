"""Listening follows Windows' default device: a switch to headphones mid-meeting, and a headset pulled out,
with a stand-in for the soundcard module (no audio hardware needed).
Run: python -m unittest discover -s tests"""
from __future__ import annotations

import os
import sys
import threading
import types
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from senada import capture  # noqa: E402


class FakeCard:
    """Devices by id; `default` is what Windows calls the default output now. `broken` ids fail to record."""

    def __init__(self, default):
        import numpy as np
        self.np, self.default, self.broken, self.opened = np, default, set(), []
        self.module = types.ModuleType("soundcard")
        self.module.SoundcardRuntimeWarning = RuntimeWarning
        self.module.default_speaker = lambda: types.SimpleNamespace(id=self.default, name=self.default)
        self.module.default_microphone = lambda: self.device(self.default)
        self.module.get_microphone = lambda id, include_loopback=False: self.device(id)
        self.blocks = 0

    def device(self, id):
        card = self

        class Recorder:
            def __enter__(self):
                if id in card.broken:
                    raise RuntimeError("AUDCLNT_E_DEVICE_INVALIDATED")
                card.opened.append(id)
                return self

            def __exit__(self, *a):
                return False

            def record(self, numframes):
                if id in card.broken:
                    raise RuntimeError("AUDCLNT_E_DEVICE_INVALIDATED")
                card.blocks += 1
                threading.Event().wait(0.002)
                return card.np.zeros((numframes, 2), dtype="float32")

        return types.SimpleNamespace(id=id, name=id, recorder=lambda **k: Recorder())


class FollowsDefault(unittest.TestCase):
    def setUp(self):
        self.card = FakeCard("Speakers")
        self._real = sys.modules.get("soundcard")
        sys.modules["soundcard"] = self.card.module

    def tearDown(self):
        if self._real is not None:
            sys.modules["soundcard"] = self._real
        else:
            sys.modules.pop("soundcard", None)

    def source(self, kind=capture.SystemAudio):
        got, devices = [], []
        src = kind(got.append)
        src.check_every, src.retry_wait = 0, 0
        src.on_device = lambda name, switched: devices.append((name, switched))
        return src, got, devices

    def wait_for(self, test, seconds=3.0):
        stop = threading.Event()
        for _ in range(int(seconds / 0.01)):
            if test():
                return True
            stop.wait(0.01)
        return False

    def test_switching_to_headphones_moves_the_listening(self):
        src, got, devices = self.source()
        src.start()
        self.assertTrue(self.wait_for(lambda: self.card.blocks > 5))
        self.card.default = "Headphones"
        self.assertTrue(self.wait_for(lambda: ("Headphones", True) in devices))
        before = len(got)
        self.assertTrue(self.wait_for(lambda: len(got) > before + 5))  # still hearing, now the headphones
        src.stop()
        self.assertEqual(devices[0], ("Speakers", False))
        self.assertEqual(self.card.opened[-1], "Headphones")
        self.assertIsNone(src.error)

    def test_a_pulled_headset_hands_over_to_the_next_default(self):
        self.card.default = "Headset"
        src, got, devices = self.source(capture.Microphone)
        src.start()
        self.assertTrue(self.wait_for(lambda: self.card.blocks > 5))
        self.card.broken.add("Headset")
        self.card.default = "Laptop mic"
        self.assertTrue(self.wait_for(lambda: ("Laptop mic", True) in devices))
        src.stop()
        self.assertIsNone(src.error)
        self.assertFalse(src.running)

    def test_no_device_at_all_stops_with_the_error(self):
        self.card.broken.add("Speakers")
        src, _, devices = self.source()
        src.start()
        self.assertTrue(self.wait_for(lambda: not src.running))
        self.assertIn("INVALIDATED", src.error)
        self.assertEqual(devices, [])


if __name__ == "__main__":
    unittest.main()
