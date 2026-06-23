import unittest

from app.repository import build_player_diagnosis
from app.utils import normalize_name


class NormalizeNameTests(unittest.TestCase):
    def test_normalize_name_collapses_punctuation_and_aliases(self):
        self.assertEqual(normalize_name("Dota 2 刀塔"), "dota2")
        self.assertEqual(normalize_name("CS2"), "counterstrike2")
        self.assertEqual(normalize_name("绝地求生"), "pubg")


class DiagnosisTests(unittest.TestCase):
    def test_build_player_diagnosis_for_hot_game(self):
        diagnosis = build_player_diagnosis({"rank_index": 3}, {"online": 150000})

        self.assertEqual(diagnosis["label"], "热门爆款")


if __name__ == "__main__":
    unittest.main()
