# 游戏导航与攻略聚合平台

这是一个基于 FastAPI + SQLite 的课程项目。网页首页展示热门游戏目录、B站直播热度和数据源状态；用户输入游戏名后，系统返回基础信息、来源页面、B站直播入口、攻略视频和简单热度诊断。

## 数据源

| 类型 | 文件 | 数据来源 | 主要字段 |
| --- | --- | --- | --- |
| 静态网页 + Steam 接口 | `spiders/static_game_spider.py` | 游民星空游戏库、Steam 商店热销/新品/折扣列表 | 游戏名、详情页、封面、来源站点 |
| API 接口 | `spiders/bilibili_live_api_spider.py` | Bilibili 直播分区接口 | 分区、房间、主播、热度、直播间链接 |
| 动态页面 | `spiders/bilibili_dynamic_live_spider.py` | Bilibili 直播页面背后的动态加载数据 | 房间、分区、热度、直播间链接 |
| 攻略搜索 | `spiders/bilibili_strategy_video_spider.py` | Bilibili 搜索接口，失败时降级为搜索页链接 | 视频标题、UP 主、播放/弹幕、视频链接 |

## 项目结构

```text
app/
  main.py          FastAPI 入口，定义网页和 API 路由
  services.py      爬取服务层，负责手动/定时刷新和攻略搜索
  batch_crawl.py   批量采集三类数据源，写入 data/raw 与 data/cleaned
  repository.py    SQLite 读写、首页聚合、搜索匹配和诊断逻辑
  db.py            SQLite 建表与旧表迁移
  scheduler.py     APScheduler 定时任务配置
  cleaning.py      通用清洗、过滤脏数据、去重
  config.py        路径、爬取数量、超时、别名表等配置
  utils.py         时间和游戏名归一化工具

spiders/
  static_game_spider.py
  bilibili_live_api_spider.py
  bilibili_dynamic_live_spider.py
  bilibili_strategy_video_spider.py
  common.py        命令行参数和 JSON 导出工具

webapp/
  templates/index.html
  static/app.js
  static/styles.css

tests/
  test_cleaning.py
  test_matching.py

data/
  game_market.db
  raw/
  cleaned/
```

## 运行方式

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动后打开 <http://127.0.0.1:8000>。

网页启动时会自动后台刷新一次数据，之后按 `app/config.py` 中的 `REFRESH_INTERVAL_MINUTES` 周期刷新，当前为 30 分钟。页面右上角“立即爬取”按钮会调用同一套刷新流程。

## 单独运行爬虫

```bash
python -m spiders.static_game_spider --limit 350
python -m spiders.bilibili_live_api_spider --limit 350 --workers 16
python -m spiders.bilibili_dynamic_live_spider --limit 350 --workers 16
```

也可以直接运行脚本文件，适合在 PyCharm 或命令行里单独调试某个爬虫：

```bash
python spiders/static_game_spider.py --limit 350
python spiders/bilibili_live_api_spider.py --limit 350 --workers 16
python spiders/bilibili_dynamic_live_spider.py --limit 350 --workers 16
```

每个命令都会同时写入：

- `data/raw/*.json`：原始采集结果
- `data/cleaned/*.json`：过滤脏数据、去重后的结果

## 主要函数调用流程

### 1. 网页启动自动爬取

```text
app.main.on_startup()
  -> init_db()
  -> scheduler.start()
  -> CrawlService.refresh_all()
      -> refresh_batch_sources(350)
          -> static_game_spider.fetch_static_games()
          -> bilibili_live_api_spider.fetch_live_rankings()
          -> bilibili_dynamic_live_spider.fetch_dynamic_live_rooms()
          -> cleaning.filter_static_games()/filter_bilibili_live()
          -> 写入 data/raw 和 data/cleaned
      -> CrawlService._refresh_dashboard_tables()
          -> load_cleaned_dataset()
          -> repository.replace_game_catalog()
          -> repository.replace_bilibili_live()
```

### 2. 首页数据展示

```text
webapp/static/app.js loadDashboard()
  -> GET /api/dashboard
      -> repository.fetch_dashboard_data()
          -> 读取 game_catalog_current
          -> 读取 bilibili_live_current
          -> 读取 crawl_runs
  -> renderMetrics()
  -> renderHotGames()
  -> renderBilibili()
  -> renderRuns()
```

### 3. 自动爬取状态展示

```text
webapp/static/app.js loadSchedulerStatus()
  -> GET /api/meta
      -> scheduler.get_jobs()
  -> GET /api/batch-status
      -> batch_crawl.get_batch_status()
          -> 统计 data/cleaned 中三个 JSON 文件条数和更新时间
  -> renderBatchStatus()
```

### 4. 手动立即爬取

```text
点击“立即爬取”
  -> POST /api/refresh
      -> CrawlService.refresh_all()
      -> refresh_batch_sources()
      -> _refresh_dashboard_tables()
  -> 前端重新调用 loadDashboard() 和 loadSchedulerStatus()
```

### 5. 搜索游戏和攻略视频

```text
输入游戏名并提交
  -> GET /api/search?q=...
      -> repository.search_game_by_name()
          -> utils.normalize_name()
          -> difflib.SequenceMatcher 模糊匹配游戏名
          -> _match_area() 尝试匹配 B站直播分区
          -> build_player_diagnosis() 输出诊断文本
      -> services.find_strategy_videos()
          -> bilibili_strategy_video_spider.fetch_strategy_videos()
          -> B站搜索接口抓取攻略视频
  -> renderResult()
```

## 清洗与去重规则

- `cleaning.clean_text()`：去除多余空格和全角空格
- `cleaning.clean_url()`：把 `//` 开头的链接补成 `https://`
- `cleaning.dedupe_records()`：按 URL 或房间 ID 去重
- `cleaning.filter_static_games()`：过滤空名称、空链接、重复链接和已知非游戏页
- `cleaning.filter_bilibili_live()`：过滤空房间、空标题、重复房间

## 测试

```bash
python -m unittest discover -s tests
```
