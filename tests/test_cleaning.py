import unittest

from app.cleaning import filter_static_games, filter_steam_popular, filter_videos


class CleaningTests(unittest.TestCase):
    def test_filter_steam_popular_removes_dirty_and_duplicate_rows(self):
        rows = [
            {"app_id": 10, "name": "  Good Game  ", "source_url": "https://store.test/app/10"},
            {"app_id": 10, "name": "Good Game duplicate", "source_url": "https://store.test/app/10"},
            {"app_id": 11, "name": "", "source_url": "https://store.test/app/11"},
            {"app_id": 12, "name": "No Url", "source_url": ""},
        ]

        cleaned = filter_steam_popular(rows)

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["name"], "Good Game")

    def test_filter_videos_normalizes_protocol_relative_url(self):
        rows = [
            {"title": "攻略", "video_url": "//www.bilibili.com/video/BV1", "author": "UP"},
            {"title": "重复攻略", "video_url": "https://www.bilibili.com/video/BV1", "author": "UP"},
            {"title": "", "video_url": "https://www.bilibili.com/video/BV2", "author": "UP"},
        ]

        cleaned = filter_videos(rows)

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["video_url"], "https://www.bilibili.com/video/BV1")

    def test_filter_static_games_removes_known_non_game_rows(self):
        rows = [
            {
                "name": "感谢你的投递",
                "source_url": "https://ku.gamersky.com/2024/thank-you-for-your-application/",
            },
            {"name": "太吾绘卷", "source_url": "https://ku.gamersky.com/2018/tai-wu-hui-juan/"},
        ]

        cleaned = filter_static_games(rows)

        self.assertEqual(len(cleaned), 1)
        self.assertEqual(cleaned[0]["name"], "太吾绘卷")


if __name__ == "__main__":
    unittest.main()
