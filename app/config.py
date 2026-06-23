from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
RAW_DATA_DIR = DATA_DIR / "raw"
CLEANED_DATA_DIR = DATA_DIR / "cleaned"
DB_PATH = DATA_DIR / "game_market.db"
WEBAPP_DIR = BASE_DIR / "webapp"
TEMPLATES_DIR = WEBAPP_DIR / "templates"
STATIC_DIR = WEBAPP_DIR / "static"

APP_TITLE = "游戏导航与攻略聚合平台"
REFRESH_INTERVAL_MINUTES = 30
SOURCE_TIMEOUT_SECONDS = 25
DEFAULT_TARGET_RECORDS = 350
MAX_WORKERS = 16

# Bilibili live API parent areas that contain game-related partitions.
GAME_PARENT_AREA_IDS = {2, 3, 6}

NAME_ALIASES = {
    "dota2": "dota2",
    "dota 2": "dota2",
    "dota2刀塔": "dota2",
    "刀塔": "dota2",
    "反恐精英全球攻势": "counterstrike2",
    "反恐精英2": "counterstrike2",
    "csgo": "counterstrike2",
    "cs2": "counterstrike2",
    "counterstrike2": "counterstrike2",
    "绝地求生": "pubg",
    "pubgbattlegrounds": "pubg",
    "pubg": "pubg",
    "apex英雄": "apexlegends",
    "apex legends": "apexlegends",
    "apexlegends": "apexlegends",
    "英雄联盟": "leagueoflegends",
    "leagueoflegends": "leagueoflegends",
    "永劫无间": "naraka",
    "narakabladepoint": "naraka",
    "黑神话悟空": "blackmythwukong",
    "blackmythwukong": "blackmythwukong",
}
