"""Public tests for fail-closed native observation checking; no artwork needed."""
import copy
import unittest
from verify import NativeMismatch, check_selection, close, close_vector


class SelectionChecks(unittest.TestCase):
    def setUp(self):
        self.case = dict(requested_action="Walk", requested_direction=7, camera_view=4,
                         requested_slot=11, resolved_slot=11, resolved_view=3,
                         fallback="NONE", status="REQUESTED_SLOT_VERIFIED", source_delay=2.0,
                         native_delay_factor=20.0, frames_in_slot=2, duration=None,
                         sequence=[dict(tick=t, frame=i, resolved_slot=11, resolved_view=3)
                                   for t, i in [(4, 0), (44, 1), (84, 0), (124, 1)]])

    def check(self, case=None):
        check_selection(case or self.case, "novice", [2.0] * 104, [2] * 104)

    def test_looping_walk_and_camera_boundary(self):
        self.check()

    def test_wrong_slot_rejected(self):
        self.case["resolved_slot"] = 3
        with self.assertRaisesRegex(NativeMismatch, "resolved_slot"):
            self.check()

    def test_one_sample_wrong_slot_rejected(self):
        self.case["sequence"][1]["resolved_slot"] = 3
        with self.assertRaisesRegex(NativeMismatch, "sample1/resolved_slot"):
            self.check()

    def test_wrong_frame_order_rejected(self):
        self.case["sequence"][1]["frame"] = 0
        with self.assertRaisesRegex(NativeMismatch, "sample1/frame"):
            self.check()

    def test_fallback_cannot_pass(self):
        self.case["fallback"] = "MODULO"
        with self.assertRaisesRegex(NativeMismatch, "fallback"):
            self.check()

    def test_invalid_direction_is_not_masked_into_success(self):
        self.case["requested_direction"] = 8
        with self.assertRaisesRegex(NativeMismatch, "ACTION_UNSUPPORTED"):
            self.check()

    def test_missing_sample_rejected(self):
        self.case["sequence"].pop()
        with self.assertRaisesRegex(NativeMismatch, "sequence_length"):
            self.check()

    def test_nonfinite_transform_cannot_compare_equal(self):
        for value in (float("inf"), float("nan")):
            with self.assertRaises(NativeMismatch):
                close(value, 0.0, "rotation")

    def test_missing_or_extra_color_channels_rejected(self):
        for value in ([], [1.0, 1.0, 1.0], [1.0] * 5):
            with self.assertRaisesRegex(NativeMismatch, "color/length"):
                close_vector(value, [1.0] * 4, "color")
        close_vector([1.0] * 4, [1.0] * 4, "color")


if __name__ == "__main__":
    unittest.main()
