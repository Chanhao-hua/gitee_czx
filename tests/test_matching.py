import unittest

from app.repository import build_matches, build_player_diagnosis
from app.utils import normalize_name


class NormalizeNameTests(unittest.TestCase):
    def test_normalize_name_collapses_punctuation_and_aliases(self):
        self.assertEqual(normalize_name("Dota 2 刀塔"), "dota2")
        self.assertEqual(normalize_name("CS2"), "counterstrike2")
        self.assertEqual(normalize_name("绝地求生"), "pubg")


class BuildMatchesTests(unittest.TestCase):
    def test_build_matches_joins_steam_and_bilibili_using_normalized_name(self):
        steam_games = [
            {"name": "Dota 2 刀塔", "rank_index": 1, "final_price": "免费", "genres": "MOBA"},
            {"name": "其它游戏", "rank_index": 2, "final_price": "¥ 59", "genres": "动作"},
        ]
        bilibili_areas = [
            {"area_name": "刀塔", "online": 320000},
            {"area_name": "永劫无间", "online": 120000},
        ]

        matches = build_matches(steam_games, bilibili_areas)

        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["game_name"], "Dota 2 刀塔")
        self.assertEqual(matches[0]["area_name"], "刀塔")

    def test_build_player_diagnosis_for_hot_game(self):
        diagnosis = build_player_diagnosis({"rank_index": 3}, {"online": 150000})

        self.assertEqual(diagnosis["label"], "热门爆款")


if __name__ == "__main__":
    unittest.main()
