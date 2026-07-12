import datetime
import warnings
import unittest

from agents.generation.phase2.steering import _now


class SteeringTest(unittest.TestCase):
    def test_now_is_parseable_utc_without_deprecation_warning(self) -> None:
        with warnings.catch_warnings():
            warnings.simplefilter("error", DeprecationWarning)
            timestamp = _now()

        self.assertTrue(timestamp.endswith("Z"))
        parsed = datetime.datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        self.assertEqual(parsed.utcoffset(), datetime.timedelta(0))


if __name__ == "__main__":
    unittest.main()
