# 游戏导航与攻略聚合平台项目报告书

## 1. 项目概述

本项目是一个基于 `FastAPI + SQLite + 原生 HTML/CSS/JavaScript` 的游戏信息聚合平台。系统围绕“热门游戏展示、游戏搜索、攻略视频聚合、B站直播热度展示、自动定时爬取”这几个功能展开。

项目当前保留三类主要数据源：

| 数据源类型 | 代码文件 | 数据来源 | 输出文件 |
| --- | --- | --- | --- |
| 静态网页 + Steam 接口源 | `spiders/static_game_spider.py` | 游民星空游戏库、Steam 商店列表接口 | `data/raw/static_game_catalog.json`、`data/cleaned/static_game_catalog.json` |
| API 接口源 | `spiders/bilibili_live_api_spider.py` | Bilibili 直播分区接口 | `data/raw/bilibili_api_live.json`、`data/cleaned/bilibili_api_live.json` |
| 动态页面源 | `spiders/bilibili_dynamic_live_spider.py` | Bilibili 直播页面背后的动态加载接口 | `data/raw/bilibili_dynamic_live.json`、`data/cleaned/bilibili_dynamic_live.json` |

网页运行后会自动启动定时任务。系统会周期性爬取三类数据源，写入 JSON 文件，再将首页展示所需数据写入 SQLite 数据库。前端页面通过 API 读取数据库聚合结果，并支持输入游戏名称查询对应的基础信息、诊断结果和攻略视频。

## 2. 技术栈

| 模块 | 技术 | 用途 |
| --- | --- | --- |
| Web 后端 | FastAPI | 提供网页入口和 JSON API |
| 页面模板 | Jinja2Templates | 返回 `index.html` 页面 |
| 静态资源服务 | FastAPI StaticFiles | 挂载 `/static`，提供 CSS 和 JavaScript |
| 数据库 | SQLite | 保存当前游戏目录、B站热度、爬取任务记录 |
| 定时任务 | APScheduler | 每隔固定时间自动刷新数据源 |
| HTTP 请求 | requests | 爬取静态网页和接口数据 |
| HTML 解析 | BeautifulSoup | 解析游民星空页面和 Steam 返回的 HTML 片段 |
| 动态搜索降级 | Playwright | B站攻略搜索接口不足时尝试动态页面抓取 |
| 前端 | 原生 HTML/CSS/JavaScript | 展示首页数据、搜索结果和状态信息 |
| 测试 | unittest | 验证清洗、去重和名称匹配逻辑 |

## 3. 项目目录结构

```text
E:/game/gitee_czx/
  app/
    __init__.py
    main.py
    services.py
    batch_crawl.py
    repository.py
    db.py
    scheduler.py
    cleaning.py
    config.py
    utils.py

  spiders/
    __init__.py
    bootstrap.py
    common.py
    static_game_spider.py
    bilibili_live_api_spider.py
    bilibili_dynamic_live_spider.py
    bilibili_strategy_video_spider.py

  webapp/
    templates/
      index.html
    static/
      app.js
      styles.css

  tests/
    test_cleaning.py
    test_matching.py

  data/
    game_market.db
    raw/
      static_game_catalog.json
      bilibili_api_live.json
      bilibili_dynamic_live.json
    cleaned/
      static_game_catalog.json
      bilibili_api_live.json
      bilibili_dynamic_live.json

  docs/
    PROJECT_MAP.md
    PROJECT_REPORT.md

  README.md
  requirements.txt
  项目总结报告模板_czx.docx
```

## 4. 整体功能流程

### 4.1 Web 服务启动流程

入口文件是 `app/main.py`。

```text
uvicorn app.main:app --reload
  -> FastAPI 加载 app/main.py
  -> 创建 FastAPI 应用对象 app
  -> 挂载 webapp/static 为 /static
  -> 创建 CrawlService 实例
  -> 创建 APScheduler 定时器
  -> on_startup()
      -> init_db()
      -> scheduler.start()
      -> 后台线程执行 crawl_service.refresh_all()
```

启动后浏览器访问：

```text
http://127.0.0.1:8000
```

页面由 `webapp/templates/index.html` 返回，页面样式来自 `webapp/static/styles.css`，交互逻辑来自 `webapp/static/app.js`。

### 4.2 自动爬取流程

自动爬取由 `app/scheduler.py` 配置，由 `app/services.py` 执行。

```text
APScheduler 定时触发
  -> CrawlService.refresh_all()
      -> refresh_batch_sources(350)
          -> _fetch_static()
              -> static_game_spider.fetch_static_games()
          -> _fetch_api()
              -> bilibili_live_api_spider.fetch_live_rankings()
          -> _fetch_dynamic()
              -> bilibili_dynamic_live_spider.fetch_dynamic_live_rooms()
          -> 清洗、去重
          -> 写入 data/raw/*.json
          -> 写入 data/cleaned/*.json
      -> CrawlService._refresh_dashboard_tables()
          -> load_cleaned_dataset("static_game_catalog")
          -> repository.replace_game_catalog()
          -> load_cleaned_dataset("bilibili_api_live")
          -> _top_live_room_per_area()
          -> repository.replace_bilibili_live()
```

### 4.3 前端首页加载流程

前端入口是 `webapp/static/app.js`。

```text
浏览器加载 index.html
  -> 加载 /static/app.js
  -> Promise.all([loadDashboard(), loadSchedulerStatus()])
      -> GET /api/dashboard
          -> repository.fetch_dashboard_data()
      -> GET /api/meta
          -> scheduler.get_jobs()
      -> GET /api/batch-status
          -> batch_crawl.get_batch_status()
  -> renderMetrics()
  -> renderHotGames()
  -> renderBilibili()
  -> renderRuns()
  -> renderBatchStatus()
```

### 4.4 手动立即爬取流程

用户点击页面右上角“立即爬取”按钮后执行：

```text
webapp/static/app.js triggerRefresh()
  -> POST /api/refresh
      -> app.main.refresh_now()
          -> CrawlService.refresh_all()
              -> refresh_batch_sources()
              -> _refresh_dashboard_tables()
  -> loadDashboard()
  -> loadSchedulerStatus()
```

### 4.5 游戏搜索和攻略视频流程

用户在搜索框输入游戏名后执行：

```text
webapp/static/app.js searchGame(gameName)
  -> GET /api/search?q=游戏名
      -> app.main.search_game(q)
          -> repository.search_game_by_name(query)
              -> utils.normalize_name()
              -> SequenceMatcher 模糊匹配
              -> _match_area()
              -> build_player_diagnosis()
          -> services.find_strategy_videos(game_name)
              -> bilibili_strategy_video_spider.fetch_strategy_videos()
  -> renderResult()
```

搜索结果包含：

- 游戏基础信息
- 来源页面链接
- B站直播间入口
- 诊断标签、诊断说明、操作建议
- B站攻略视频链接

## 5. 后端代码文件说明

### 5.1 `app/main.py`

`app/main.py` 是 FastAPI 应用入口，负责创建 Web 应用、注册路由、启动定时任务和返回 API 数据。

#### 全局对象

| 对象 | 作用 |
| --- | --- |
| `templates` | 绑定 `webapp/templates` 目录，用于返回 HTML 模板 |
| `app` | FastAPI 应用实例 |
| `crawl_service` | 爬取业务服务实例 |
| `scheduler` | APScheduler 定时任务实例 |

#### 函数说明

| 函数 | 类型 | 功能 |
| --- | --- | --- |
| `on_startup()` | FastAPI 启动事件 | 初始化数据库，启动定时器，后台执行首次数据刷新 |
| `on_shutdown()` | FastAPI 关闭事件 | 停止定时器，避免后台任务继续运行 |
| `index(request)` | 页面路由 | 返回首页 `index.html` |
| `favicon()` | 静态兼容路由 | 返回 204，避免浏览器请求 favicon 报错 |
| `get_dashboard()` | API 路由 | 返回首页指标、热门游戏、B站热度和爬取记录 |
| `batch_status()` | API 路由 | 返回三类 cleaned JSON 文件的条数和更新时间 |
| `search_game(q)` | API 路由 | 根据游戏名返回搜索结果、诊断结果和攻略视频 |
| `get_meta()` | API 路由 | 返回定时器运行状态和下一次执行时间 |
| `refresh_now()` | API 路由 | 手动触发完整爬取流程 |
| `_job_next_run_time(job)` | 内部函数 | 将 APScheduler 的下一次运行时间转为 ISO 字符串 |

#### API 路由表

| 路由 | 方法 | 调用函数 | 返回内容 |
| --- | --- | --- | --- |
| `/` | GET | `index()` | HTML 首页 |
| `/favicon.ico` | GET | `favicon()` | 204 响应 |
| `/api/dashboard` | GET | `get_dashboard()` | 首页聚合数据 |
| `/api/batch-status` | GET | `batch_status()` | JSON 文件状态 |
| `/api/search?q=...` | GET | `search_game()` | 游戏搜索结果 |
| `/api/meta` | GET | `get_meta()` | 定时任务状态 |
| `/api/refresh` | POST | `refresh_now()` | 手动刷新结果 |

### 5.2 `app/services.py`

`app/services.py` 是业务服务层，负责协调爬虫、JSON 文件和数据库写入。

#### `CrawlService`

`CrawlService` 是自动和手动爬取的统一入口。

| 方法 | 功能 |
| --- | --- |
| `__init__()` | 创建线程锁 `_lock` |
| `refresh_all()` | 执行完整刷新流程，包含批量爬取、清洗、写 JSON、入库 |
| `_refresh_dashboard_tables()` | 将 cleaned JSON 写入 SQLite 首页展示表 |

`refresh_all()` 使用 `threading.Lock()` 防止重复爬取。如果用户在上一次爬取未结束时再次点击“立即爬取”，函数会返回：

```python
{"started": False, "message": "已有爬取任务正在运行"}
```

#### 其他函数

| 函数 | 功能 |
| --- | --- |
| `find_strategy_videos(game_name)` | 调用 B站攻略视频爬虫，返回前端所需的字典列表 |
| `_top_live_room_per_area(records)` | 从 350 条 B站直播房间中按分区保留热度最高的房间 |

`_top_live_room_per_area()` 的作用是减少首页数据库的数据量。B站爬虫输出的是房间级数据，首页展示使用的是分区级热度，所以每个分区只保留一个热度最高的直播间。

### 5.3 `app/batch_crawl.py`

`app/batch_crawl.py` 是批量采集控制模块，负责一次性运行三类数据源爬虫，并将结果写入 `data/raw` 和 `data/cleaned`。

#### 常量

`DATASET_SPECS` 定义三类数据源的元信息：

| 数据集名 | 页面标签 | 去重主键 | 必填字段 |
| --- | --- | --- | --- |
| `static_game_catalog` | 静态网页源 | `source_url` | `name`, `source_url` |
| `bilibili_api_live` | API 接口源 | `room_id` | `room_title`, `room_url` |
| `bilibili_dynamic_live` | 动态页面源 | `room_id` | `room_title`, `room_url` |

#### 函数说明

| 函数 | 功能 |
| --- | --- |
| `refresh_batch_sources(limit=350)` | 依次执行三类爬虫，写入 raw 和 cleaned JSON，并返回每个数据源的统计信息 |
| `get_batch_status()` | 读取 cleaned JSON 文件，返回条数、更新时间和路径 |
| `load_cleaned_dataset(name)` | 根据数据集名读取对应 cleaned JSON，供入库流程使用 |
| `_fetch_static(limit)` | 调用 `fetch_static_games()` 获取静态游戏目录 |
| `_fetch_api(limit)` | 调用 `fetch_live_rankings()` 获取 B站 API 直播数据 |
| `_fetch_dynamic(limit)` | 调用 `fetch_dynamic_live_rooms()` 获取 B站动态页面数据 |
| `_clean_static(records, limit)` | 调用 `filter_static_games()` 清洗静态游戏数据 |
| `_write_json(path, records)` | 将 Python 列表序列化为 UTF-8 JSON 文件 |

#### 采集结果结构

`refresh_batch_sources()` 返回数据示例：

```json
{
  "started": true,
  "message": "自动爬取完成",
  "limit": 350,
  "datasets": [
    {
      "name": "static_game_catalog",
      "label": "静态网页源",
      "raw_count": 350,
      "cleaned_count": 350,
      "elapsed_seconds": 8.41,
      "cleaned_path": "E:/game/gitee_czx/data/cleaned/static_game_catalog.json"
    }
  ],
  "errors": [],
  "finished_at": "2026-06-23T14:41:23+00:00",
  "elapsed_seconds": 55.12
}
```

### 5.4 `app/repository.py`

`app/repository.py` 是数据库读写和搜索诊断模块。所有 SQLite 的业务读写都集中在这里。

#### 写入函数

| 函数 | 功能 |
| --- | --- |
| `begin_run(source)` | 在 `crawl_runs` 表插入一条 running 状态记录 |
| `finish_run(run_id, status, record_count, error_message)` | 更新爬取任务状态 |
| `replace_game_catalog(records)` | 清空并重写 `game_catalog_current` 表 |
| `replace_bilibili_live(records)` | 清空并重写 `bilibili_live_current`，同时追加 `bilibili_live_history` |

`replace_game_catalog()` 会调用 `filter_game_catalog()`，再次执行入库前清洗，避免脏数据进入数据库。

`replace_bilibili_live()` 同时写入两张表：

- `bilibili_live_current`：当前最新热度数据。
- `bilibili_live_history`：历史热度记录。

#### 读取和聚合函数

| 函数 | 功能 |
| --- | --- |
| `fetch_dashboard_data()` | 为 `/api/dashboard` 聚合首页所需全部数据 |
| `search_game_by_name(query)` | 对用户输入的游戏名进行模糊匹配，返回最接近的游戏 |
| `build_player_diagnosis(game, live_area)` | 根据游戏排名和 B站热度生成诊断文本 |
| `_match_area(game_name, bilibili_areas)` | 将游戏名称和 B站直播分区名称进行归一化匹配 |
| `_shape_game(row)` | 将 SQLite 行对象转换为前端使用的游戏对象 |

#### 首页数据返回结构

`fetch_dashboard_data()` 返回：

| 字段 | 来源 | 用途 |
| --- | --- | --- |
| `metrics` | SQLite 聚合查询 | 首页指标卡片 |
| `games` | `game_catalog_current` | 热门游戏卡片 |
| `bilibili_areas` | `bilibili_live_current` | B站直播热度列表 |
| `source_runs` | `crawl_runs` | 数据源运行状态 |
| `generated_at` | `utc_now_iso()` | 页面显示数据生成时间 |

#### 游戏搜索逻辑

`search_game_by_name(query)` 的执行步骤：

1. 调用 `normalize_name(query)` 去掉符号、转小写、应用别名表。
2. 读取 `game_catalog_current` 中全部游戏。
3. 对每条游戏记录调用 `normalize_name(game["name"])`。
4. 使用 `SequenceMatcher` 计算输入名称和游戏名称的相似度。
5. 如果一个字符串包含另一个字符串，则额外增加 `0.35` 匹配分。
6. 选择最高分游戏。
7. 如果最高分小于 `0.28`，返回 `None`。
8. 调用 `_match_area()` 匹配 B站直播分区。
9. 调用 `build_player_diagnosis()` 生成诊断文本。

#### 诊断规则

| 条件 | 输出标签 | 业务含义 |
| --- | --- | --- |
| `rank <= 5` 且 `online >= 100000` | 热门爆款 | 游戏目录排名靠前，B站直播热度较高 |
| `rank <= 10` 且 `online < 30000` | 高关注但直播讨论较少 | 游戏目录靠前，但直播端声量较低 |
| `rank > 10` 且 `online >= 100000` | 直播话题型游戏 | B站热度高于游戏目录位置 |
| 其他情况 | 常规关注 | 热度处于普通范围 |

### 5.5 `app/db.py`

`app/db.py` 负责 SQLite 数据库连接、建表和旧表迁移。

#### 函数说明

| 函数 | 功能 |
| --- | --- |
| `ensure_data_dir()` | 确保 `data/` 目录存在 |
| `get_connection()` | 创建 SQLite 连接，并设置 `row_factory = sqlite3.Row` |
| `connect()` | 数据库上下文管理器，自动提交和关闭连接 |
| `init_db()` | 创建项目需要的数据库表 |
| `_ensure_column(conn, table, column, column_type)` | 给旧表补充缺失字段 |
| `_migrate_legacy_game_catalog(conn)` | 将旧表 `steam_popular_current` 迁移到新表 `game_catalog_current` |

#### 数据库表结构

##### `crawl_runs`

记录每次爬取任务。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `source` | TEXT | 数据源名称 |
| `status` | TEXT | `running`、`success` 或 `failed` |
| `started_at` | TEXT | 开始时间 |
| `finished_at` | TEXT | 结束时间 |
| `record_count` | INTEGER | 本次写入条数 |
| `error_message` | TEXT | 错误信息 |

##### `game_catalog_current`

保存首页当前游戏目录。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `app_id` | INTEGER | 游戏 ID，主键 |
| `rank_index` | INTEGER | 首页排序 |
| `name` | TEXT | 游戏名称 |
| `platforms` | TEXT | 平台 |
| `source_url` | TEXT | 来源页面 |
| `header_image` | TEXT | 封面图 |
| `source_site` | TEXT | 来源站点 |
| `scraped_at` | TEXT | 入库时间 |

##### `bilibili_live_current`

保存当前 B站直播热度。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `area_id` | INTEGER | B站子分区 ID，主键 |
| `parent_area_id` | INTEGER | 父分区 ID |
| `parent_area_name` | TEXT | 父分区名称 |
| `area_name` | TEXT | 子分区名称 |
| `room_id` | INTEGER | 直播间 ID |
| `room_title` | TEXT | 直播间标题 |
| `streamer_name` | TEXT | 主播名称 |
| `online` | INTEGER | 在线热度 |
| `tags` | TEXT | 标签 |
| `cover_url` | TEXT | 封面图 |
| `room_url` | TEXT | 直播间链接 |
| `scraped_at` | TEXT | 入库时间 |

##### `bilibili_live_history`

保存 B站直播热度历史记录。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | INTEGER | 主键 |
| `area_id` | INTEGER | 子分区 ID |
| `room_id` | INTEGER | 直播间 ID |
| `online` | INTEGER | 在线热度 |
| `room_title` | TEXT | 直播间标题 |
| `captured_at` | TEXT | 采集时间 |

### 5.6 `app/cleaning.py`

`app/cleaning.py` 是通用数据清洗模块。爬虫导出和数据库入库都会调用这里的函数。

#### 常量

| 常量 | 功能 |
| --- | --- |
| `INVALID_TEXT_MARKERS` | 定义无效文本标记，例如空字符串、`null`、`undefined`、`暂无`、`未知` |
| `STATIC_GAME_BLOCKLIST` | 静态游戏目录的已知非游戏条目黑名单 |

#### 函数说明

| 函数 | 功能 |
| --- | --- |
| `clean_text(value)` | 将任意值转为字符串，去除全角空格和多余空白 |
| `is_valid_text(value, min_length=1)` | 判断文本是否满足最小长度且不属于无效标记 |
| `clean_url(value)` | 清理 URL，将 `//` 开头的链接补全为 `https://` |
| `dedupe_records(records, key_fields, required_fields, limit)` | 通用去重函数，按指定字段去重并校验必填字段 |
| `filter_game_catalog(records, limit)` | 清洗游戏目录，按 `app_id` 去重 |
| `filter_static_games(records, limit)` | 清洗静态游戏源，按 `source_url` 去重并过滤非游戏页 |
| `filter_videos(records, limit)` | 清洗攻略视频，按 `video_url` 去重 |
| `filter_bilibili_live(records, limit)` | 清洗 B站直播数据，按 `room_id` 去重 |

#### `dedupe_records()` 处理步骤

1. 遍历输入数据。
2. 对字符串字段调用 `clean_text()`。
3. 对 URL 字段调用 `clean_url()`。
4. 检查必填字段是否有效。
5. 根据 `key_fields` 生成去重键。
6. 跳过重复记录。
7. 达到 `limit` 后停止追加。

### 5.7 `app/config.py`

`app/config.py` 是集中配置文件。

| 配置项 | 当前值 | 作用 |
| --- | --- | --- |
| `BASE_DIR` | 项目根目录 | 计算其他路径 |
| `DATA_DIR` | `data/` | 数据目录 |
| `RAW_DATA_DIR` | `data/raw` | 原始 JSON 输出目录 |
| `CLEANED_DATA_DIR` | `data/cleaned` | 清洗后 JSON 输出目录 |
| `DB_PATH` | `data/game_market.db` | SQLite 数据库文件 |
| `WEBAPP_DIR` | `webapp/` | 前端目录 |
| `TEMPLATES_DIR` | `webapp/templates` | 模板目录 |
| `STATIC_DIR` | `webapp/static` | 静态资源目录 |
| `APP_TITLE` | 游戏导航与攻略聚合平台 | FastAPI 标题和页面标题 |
| `REFRESH_INTERVAL_MINUTES` | 30 | 自动爬取间隔 |
| `SOURCE_TIMEOUT_SECONDS` | 25 | 外部请求超时时间 |
| `DEFAULT_TARGET_RECORDS` | 350 | 默认目标采集条数 |
| `MAX_WORKERS` | 16 | 最大并发请求数 |
| `GAME_PARENT_AREA_IDS` | `{2, 3, 6}` | B站游戏相关父分区 |
| `NAME_ALIASES` | 字典 | 游戏名称别名映射 |

### 5.8 `app/utils.py`

`app/utils.py` 提供通用工具函数。

| 函数 | 功能 |
| --- | --- |
| `utc_now_iso()` | 返回当前 UTC 时间，格式为 ISO 字符串 |
| `normalize_name(name)` | 清理游戏名称，保留数字、字母、中文，转小写，并应用别名表 |

`normalize_name()` 用于搜索匹配和 B站分区匹配。例如：

| 输入 | 输出 |
| --- | --- |
| `Dota 2 刀塔` | `dota2` |
| `CS2` | `counterstrike2` |
| `绝地求生` | `pubg` |

### 5.9 `app/scheduler.py`

`app/scheduler.py` 负责创建定时任务。

#### 函数说明

| 函数 | 功能 |
| --- | --- |
| `create_scheduler(crawl_service)` | 创建 `BackgroundScheduler`，每 30 分钟执行一次 `crawl_service.refresh_all()` |

定时任务参数：

| 参数 | 作用 |
| --- | --- |
| `timezone="UTC"` | 使用 UTC 时区 |
| `trigger="interval"` | 固定间隔执行 |
| `minutes=REFRESH_INTERVAL_MINUTES` | 执行间隔 |
| `id="refresh-all-sources"` | 任务 ID |
| `replace_existing=True` | 重复创建时替换旧任务 |
| `max_instances=1` | 同一任务最多一个实例 |
| `coalesce=True` | 延迟任务合并执行 |

## 6. 爬虫代码文件说明

### 6.1 `spiders/bootstrap.py`

该文件用于支持直接运行爬虫脚本。

#### 函数说明

| 函数 | 功能 |
| --- | --- |
| `ensure_project_root_on_path()` | 将项目根目录加入 `sys.path`，保证 `python spiders/xxx.py` 可以导入 `app` 和 `spiders` 包 |

没有该函数时，直接运行脚本可能出现：

```text
ModuleNotFoundError: No module named 'app'
```

当前三个主爬虫文件都会在导入 `app.*` 前调用该函数。

### 6.2 `spiders/common.py`

该文件提供爬虫命令行参数解析和 JSON 导出工具。

| 函数 | 功能 |
| --- | --- |
| `parse_limit(description)` | 解析命令行参数 `--limit` |
| `write_dataset(name, raw_records, cleaned_records, started_at)` | 将 raw 和 cleaned 数据写入 JSON，并在终端输出统计信息 |
| `_write_json(path, records)` | 执行具体 JSON 文件写入 |

输出格式示例：

```text
static_game_catalog: raw=350 cleaned=350 elapsed=8.41s cleaned_file=E:\game\gitee_czx\data\cleaned\static_game_catalog.json
```

### 6.3 `spiders/static_game_spider.py`

该文件负责静态游戏目录采集。数据来源为游民星空游戏库和 Steam 商店列表接口。

#### 数据类

`StaticGameInfo` 定义静态游戏记录结构：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `app_id` | int | 游戏 ID |
| `rank_index` | int | 排名 |
| `name` | str | 游戏名称 |
| `platforms` | str | 平台 |
| `source_url` | str | 来源页面 |
| `header_image` | str | 封面图 |
| `source_site` | str | 来源站点 |

#### 常量

| 常量 | 作用 |
| --- | --- |
| `GAMERSKY_URL` | 游民星空游戏库首页 |
| `STEAM_SEARCH_URL` | Steam 搜索结果接口 |
| `STEAM_PAGE_SIZE` | Steam 单页请求数量 |
| `STEAM_SEARCHES` | Steam 多个列表筛选条件 |

`STEAM_SEARCHES` 包含：

- `topsellers`
- `globaltopsellers`
- `popularnew`
- `specials`
- `newreleases`
- `comingsoon`
- `Released_DESC`
- `Reviews_DESC`
- `Name_ASC`

这些筛选条件用于扩大数据覆盖范围，保证清洗去重后可以达到 350 条。

#### 函数说明

| 函数 | 功能 |
| --- | --- |
| `fetch_static_games(limit=350)` | 静态游戏目录爬虫主函数 |
| `main()` | 命令行入口 |
| `_safe_fetch_gamersky()` | 捕获游民星空请求异常，失败时返回空列表 |
| `_fetch_gamersky()` | 请求游民星空页面并解析游戏条目 |
| `_fetch_steam_games(seed_records, limit)` | 使用 Steam 多个列表接口补齐游戏数量 |
| `_fetch_steam_search_page(session, search, start)` | 请求 Steam 搜索 JSON 接口 |
| `_parse_steam_results(results_html)` | 解析 Steam 返回的 HTML 片段 |
| `_strip_query(url)` | 删除 URL 查询参数和 fragment |
| `_record(app_id, name, source_url, header_image, source_site)` | 统一记录字段 |

#### 执行流程

```text
main()
  -> parse_limit()
  -> fetch_static_games(limit)
      -> _safe_fetch_gamersky()
          -> _fetch_gamersky()
              -> requests.get(GAMERSKY_URL)
              -> BeautifulSoup 解析 li.gamelist
              -> _record()
      -> filter_static_games()
      -> _fetch_steam_games()
          -> _fetch_steam_search_page()
          -> _parse_steam_results()
          -> filter_static_games()
      -> 设置 app_id 和 rank_index
      -> 返回 StaticGameInfo 列表
  -> filter_static_games()
  -> write_dataset("static_game_catalog", ...)
```

#### 单独运行命令

```bash
python -m spiders.static_game_spider --limit 350
python spiders/static_game_spider.py --limit 350
```

### 6.4 `spiders/bilibili_live_api_spider.py`

该文件负责 B站 API 接口源采集。它会抓取 B站直播游戏相关分区下的直播间数据。

#### 数据类

`BilibiliLiveArea` 定义 B站直播记录结构：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `area_id` | int | 子分区 ID |
| `parent_area_id` | int | 父分区 ID |
| `parent_area_name` | str | 父分区名称 |
| `area_name` | str | 子分区名称 |
| `room_id` | int | 直播间 ID |
| `room_title` | str | 直播间标题 |
| `streamer_name` | str | 主播名称 |
| `online` | int | 在线热度 |
| `tags` | str | 标签 |
| `cover_url` | str | 封面图 |
| `room_url` | str | 直播间链接 |

#### 常量

| 常量 | 作用 |
| --- | --- |
| `AREA_LIST_URL` | B站直播分区列表接口 |
| `ROOM_LIST_URL` | B站直播房间列表接口 |
| `HEADERS` | 请求头，包含 User-Agent 和 Referer |

#### 函数说明

| 函数 | 功能 |
| --- | --- |
| `fetch_live_rankings(limit_per_area=1, limit=None, workers=16)` | 并发抓取 B站直播房间数据 |
| `main()` | 命令行入口 |
| `_parse_args(description)` | 解析 `--limit` 和 `--workers` |
| `_session()` | 创建带请求头的 requests Session |
| `_fetch_room_page(parent_id, parent_name, area_id, area_name, limit_per_area)` | 请求单个分区的房间列表 |

#### 执行流程

```text
main()
  -> _parse_args()
  -> fetch_live_rankings(limit_per_area=8, limit=args.limit, workers=args.workers)
      -> _session()
      -> 请求 AREA_LIST_URL 获取分区列表
      -> 根据 GAME_PARENT_AREA_IDS 过滤游戏相关父分区
      -> 生成子分区任务列表 jobs
      -> ThreadPoolExecutor 并发执行 _fetch_room_page()
      -> filter_bilibili_live()
      -> 按 online 降序排序
      -> 返回 BilibiliLiveArea 列表
  -> filter_bilibili_live()
  -> write_dataset("bilibili_api_live", ...)
```

#### 并发参数

`--workers` 控制并发请求数。代码内部会限制为：

```python
max(1, min(workers, MAX_WORKERS))
```

当前 `MAX_WORKERS = 16`。

#### 单独运行命令

```bash
python -m spiders.bilibili_live_api_spider --limit 350 --workers 16
python spiders/bilibili_live_api_spider.py --limit 350 --workers 16
```

### 6.5 `spiders/bilibili_dynamic_live_spider.py`

该文件表示动态页面源。B站直播页面数据由前端动态接口加载，本项目直接复用 B站直播接口爬虫获取动态加载数据，以提高速度和稳定性。

#### 函数说明

| 函数 | 功能 |
| --- | --- |
| `fetch_dynamic_live_rooms(limit, workers=16)` | 调用 `fetch_live_rankings()` 获取动态页面背后的直播数据 |
| `main()` | 命令行入口 |
| `_parse_args(description)` | 解析 `--limit` 和 `--workers` |

#### 执行流程

```text
main()
  -> _parse_args()
  -> fetch_dynamic_live_rooms(args.limit, workers=args.workers)
      -> fetch_live_rankings(limit_per_area=8, limit=limit, workers=workers)
  -> filter_bilibili_live()
  -> write_dataset("bilibili_dynamic_live", ...)
```

#### 单独运行命令

```bash
python -m spiders.bilibili_dynamic_live_spider --limit 350 --workers 16
python spiders/bilibili_dynamic_live_spider.py --limit 350 --workers 16
```

### 6.6 `spiders/bilibili_strategy_video_spider.py`

该文件负责 B站攻略视频搜索。该爬虫主要在用户搜索游戏时调用，不参与首页 350 条批量展示。

#### 数据类

`BilibiliVideo` 定义攻略视频记录结构：

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `title` | str | 视频标题 |
| `author` | str | UP 主 |
| `stats` | str | 播放和弹幕信息 |
| `video_url` | str | 视频链接 |
| `cover_url` | str | 封面图 |
| `source_note` | str | 来源说明 |

#### 函数说明

| 函数 | 功能 |
| --- | --- |
| `bilibili_search_url(keyword)` | 构造 B站搜索页 URL |
| `fetch_strategy_videos(game_name, limit=6)` | 搜索单个游戏攻略视频 |
| `fetch_strategy_videos_bulk(keywords, limit=350, workers=4)` | 批量搜索多个关键词 |
| `_fetch_bilibili_api_page(keyword, page)` | 请求 B站搜索 API |
| `_fetch_bilibili_dynamic_page(keyword, page_limit=2)` | 使用 Playwright 抓取 B站搜索页 |
| `_build_search_terms(keywords)` | 构造搜索关键词列表 |
| `_fallback_search_record(keyword, reason)` | 生成搜索页入口兜底记录 |
| `_strip_html(value)` | 删除标题中的 HTML 高亮标签 |
| `_first_text(locator, selectors)` | Playwright 页面解析辅助函数 |
| `_first_attr(locator, selectors, attr)` | Playwright 属性解析辅助函数 |
| `_normalize_bilibili_url(url)` | 补全 B站 URL |

#### 执行流程

```text
fetch_strategy_videos(game_name)
  -> fetch_strategy_videos_bulk([game_name], limit=6)
      -> _build_search_terms()
      -> ThreadPoolExecutor 并发请求 _fetch_bilibili_api_page()
      -> filter_videos()
      -> 如果数量不足
          -> _fetch_bilibili_dynamic_page()
              -> 如果未安装 Playwright
                  -> _fallback_search_record()
      -> 返回 BilibiliVideo 列表
```

## 7. 前端代码文件说明

### 7.1 `webapp/templates/index.html`

该文件是网页结构模板，由 FastAPI 的 `index()` 路由返回。

页面区域：

| 区域 | DOM 标识 | 功能 |
| --- | --- | --- |
| 顶部标题区 | `topbar` | 显示系统名称和“立即爬取”按钮 |
| 搜索区 | `search-form` | 输入游戏名并提交搜索 |
| 自动爬取状态区 | `scheduler-pill`, `next-run` | 显示定时任务状态 |
| 批量数据源状态区 | `batch-panel` | 显示三类 cleaned JSON 条数 |
| 搜索结果区 | `result-panel` | 显示游戏搜索结果和攻略视频 |
| 首页指标区 | `metrics-grid` | 显示游戏条数、B站分区数、热度峰值 |
| 热门游戏区 | `hot-games` | 显示游戏卡片 |
| B站热度区 | `bilibili-list` | 显示直播热度列表 |
| 数据源运行状态区 | `source-runs` | 显示最近一次爬取任务记录 |

页面最后加载：

```html
<script src="/static/app.js"></script>
```

### 7.2 `webapp/static/app.js`

该文件负责前端数据请求、事件绑定和 DOM 渲染。

#### DOM 变量

| 变量 | 对应元素 |
| --- | --- |
| `refreshButton` | “立即爬取”按钮 |
| `refreshStatus` | 爬取状态文本 |
| `schedulerPill` | 定时任务状态标签 |
| `nextRun` | 下一次执行时间 |
| `searchForm` | 搜索表单 |
| `searchInput` | 搜索输入框 |
| `resultPanel` | 搜索结果区域 |

#### 工具函数

| 函数 | 功能 |
| --- | --- |
| `escapeHtml(value)` | 转义 HTML 特殊字符，避免接口数据直接插入 HTML |
| `formatNumber(value)` | 按中文地区格式化数字 |
| `formatDate(value)` | 将时间字符串格式化为本地时间 |

#### 渲染函数

| 函数 | 功能 |
| --- | --- |
| `renderMetrics(metrics)` | 渲染首页指标卡片 |
| `renderMetricCard([label, value, sub])` | 渲染单个指标卡片 |
| `renderBatchStatus(status)` | 渲染三类数据源文件状态 |
| `renderRuns(runs)` | 渲染最近爬取任务状态 |
| `renderHotGames(games)` | 渲染热门游戏卡片 |
| `renderBilibili(areas)` | 渲染 B站直播热度列表 |
| `renderResult(payload)` | 渲染游戏搜索结果、诊断结果和攻略视频 |
| `renderError(message)` | 渲染搜索错误信息 |

#### 请求函数

| 函数 | 请求接口 | 功能 |
| --- | --- | --- |
| `loadDashboard()` | `GET /api/dashboard` | 获取首页游戏、热度和任务记录 |
| `loadSchedulerStatus()` | `GET /api/meta`、`GET /api/batch-status` | 获取定时任务和数据文件状态 |
| `searchGame(gameName)` | `GET /api/search?q=...` | 搜索游戏并显示攻略视频 |
| `triggerRefresh()` | `POST /api/refresh` | 手动触发爬取 |

#### 事件绑定

| 事件 | 处理函数 | 功能 |
| --- | --- | --- |
| `searchForm.submit` | `searchGame(searchInput.value)` | 提交搜索 |
| `document.click` | 读取 `[data-game]` | 点击游戏卡片中的“查攻略”按钮 |
| `refreshButton.click` | `triggerRefresh()` | 手动刷新数据 |

#### 自动刷新

页面加载后执行：

```javascript
Promise.all([loadDashboard(), loadSchedulerStatus()]);
setInterval(loadDashboard, 30000);
setInterval(loadSchedulerStatus, 30000);
```

页面每 30 秒刷新一次首页数据和任务状态。

### 7.3 `webapp/static/styles.css`

该文件负责页面视觉样式和响应式布局。

主要样式模块：

| 样式区域 | 功能 |
| --- | --- |
| `:root` | 定义全局颜色变量 |
| `.page-shell` | 页面主容器宽度和边距 |
| `.topbar` | 顶部标题和按钮区域 |
| `.search-panel` | 搜索和自动爬取状态区域 |
| `.metrics-grid` | 指标卡片网格 |
| `.game-grid` | 热门游戏卡片网格 |
| `.two-col` | B站热度和数据源状态双栏布局 |
| `.result-panel` | 搜索结果区域 |
| `.video-grid` | 攻略视频卡片网格 |
| `@media (max-width: 980px)` | 平板和窄屏布局适配 |
| `@media (max-width: 560px)` | 手机端布局适配 |

## 8. 测试代码文件说明

### 8.1 `tests/test_cleaning.py`

该文件验证清洗模块。

| 测试函数 | 验证内容 |
| --- | --- |
| `test_filter_game_catalog_removes_dirty_and_duplicate_rows()` | 游戏目录按 `app_id` 去重，并过滤空名称和空链接 |
| `test_filter_videos_normalizes_protocol_relative_url()` | 视频 URL 自动补全 `https:`，并按 `video_url` 去重 |
| `test_filter_static_games_removes_dirty_and_duplicate_rows()` | 静态游戏源过滤空名称，并按 `source_url` 去重 |

### 8.2 `tests/test_matching.py`

该文件验证名称匹配和诊断逻辑。

| 测试函数 | 验证内容 |
| --- | --- |
| `test_normalize_name_collapses_punctuation_and_aliases()` | 验证别名归一化，例如 `Dota 2 刀塔`、`CS2`、`绝地求生` |
| `test_build_player_diagnosis_for_hot_game()` | 验证高排名和高热度时输出 `热门爆款` |

### 8.3 测试命令

```bash
python -m unittest discover -s tests
```

## 9. 数据文件说明

### 9.1 `data/raw`

`data/raw` 保存原始采集结果。原始结果已经经过字段结构整理，但没有作为最终数据源状态使用。

当前文件：

| 文件 | 内容 |
| --- | --- |
| `static_game_catalog.json` | 静态游戏目录原始记录 |
| `bilibili_api_live.json` | B站 API 直播原始记录 |
| `bilibili_dynamic_live.json` | B站动态页面源原始记录 |

### 9.2 `data/cleaned`

`data/cleaned` 保存过滤和去重后的结果，是入库流程读取的数据来源。

当前文件：

| 文件 | 内容 | 当前目标数量 |
| --- | --- | --- |
| `static_game_catalog.json` | 清洗后的游戏目录 | 350 |
| `bilibili_api_live.json` | 清洗后的 B站 API 直播房间 | 350 |
| `bilibili_dynamic_live.json` | 清洗后的 B站动态页面直播房间 | 350 |

### 9.3 `data/game_market.db`

`data/game_market.db` 是 SQLite 数据库文件。网页 API 从该数据库读取首页展示数据。

## 10. 运行说明

### 10.1 安装依赖

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

`requirements.txt` 当前包含：

```text
fastapi
uvicorn
requests
beautifulsoup4
jinja2
apscheduler
playwright
```

### 10.2 启动网页

```bash
uvicorn app.main:app --reload
```

启动成功后访问：

```text
http://127.0.0.1:8000
```

### 10.3 单独运行爬虫

模块运行方式：

```bash
python -m spiders.static_game_spider --limit 350
python -m spiders.bilibili_live_api_spider --limit 350 --workers 16
python -m spiders.bilibili_dynamic_live_spider --limit 350 --workers 16
```

脚本运行方式：

```bash
python spiders/static_game_spider.py --limit 350
python spiders/bilibili_live_api_spider.py --limit 350 --workers 16
python spiders/bilibili_dynamic_live_spider.py --limit 350 --workers 16
```

### 10.4 手动刷新数据库

如果已经单独运行了三个爬虫，需要把 cleaned JSON 写入 SQLite，可以执行：

```bash
python - <<'PY'
from app.db import init_db
from app.services import CrawlService
from app.repository import fetch_dashboard_data

init_db()
CrawlService()._refresh_dashboard_tables()
print(fetch_dashboard_data()["metrics"])
PY
```

PowerShell 环境可以使用：

```powershell
@'
from app.db import init_db
from app.services import CrawlService
from app.repository import fetch_dashboard_data

init_db()
CrawlService()._refresh_dashboard_tables()
print(fetch_dashboard_data()["metrics"])
'@ | python -
```

## 11. 核心业务流程汇总

### 11.1 数据采集到入库

```text
spiders/*.py
  -> 采集外部数据
  -> app.cleaning 过滤和去重
  -> data/raw/*.json
  -> data/cleaned/*.json
  -> app.services.CrawlService._refresh_dashboard_tables()
  -> app.repository.replace_game_catalog()
  -> app.repository.replace_bilibili_live()
  -> data/game_market.db
```

### 11.2 数据库到前端展示

```text
webapp/static/app.js
  -> GET /api/dashboard
  -> app.main.get_dashboard()
  -> app.repository.fetch_dashboard_data()
  -> SQLite 查询
  -> JSONResponse
  -> renderMetrics()
  -> renderHotGames()
  -> renderBilibili()
  -> renderRuns()
```

### 11.3 搜索功能

```text
用户输入游戏名
  -> searchGame()
  -> GET /api/search?q=...
  -> search_game()
  -> search_game_by_name()
  -> find_strategy_videos()
  -> fetch_strategy_videos()
  -> renderResult()
```

## 12. 当前项目特性

### 12.1 数据量

当前三类主要数据源均按 350 条目标数量采集：

| 数据源 | cleaned 数量 |
| --- | --- |
| 静态游戏目录 | 350 |
| B站 API 直播数据 | 350 |
| B站动态页面源数据 | 350 |

### 12.2 数据清洗

项目对数据执行以下处理：

- 空名称过滤
- 空链接过滤
- 无效占位文本过滤
- URL 协议补全
- 游戏目录按 `app_id` 或 `source_url` 去重
- B站直播数据按 `room_id` 去重
- 攻略视频按 `video_url` 去重

### 12.3 自动定时爬取

自动爬取由 APScheduler 控制。默认每 30 分钟执行一次完整刷新流程。

配置位置：

```python
REFRESH_INTERVAL_MINUTES = 30
```

文件位置：

```text
app/config.py
```

### 12.4 单独运行支持

三个主爬虫均支持以下两种方式：

- `python -m spiders.xxx`
- `python spiders/xxx.py`

直接运行脚本依赖 `spiders/bootstrap.py` 将项目根目录加入 `sys.path`。

### 12.5 并发采集

B站直播数据采集使用 `ThreadPoolExecutor` 并发请求多个直播分区。

默认最大并发：

```python
MAX_WORKERS = 16
```

命令行参数：

```bash
--workers 16
```

## 13. 维护说明

### 13.1 修改采集数量

默认采集数量配置在：

```text
app/config.py
```

配置项：

```python
DEFAULT_TARGET_RECORDS = 350
```

单独运行爬虫时可以使用 `--limit` 覆盖：

```bash
python spiders/static_game_spider.py --limit 500
```

### 13.2 修改自动爬取间隔

修改文件：

```text
app/config.py
```

配置项：

```python
REFRESH_INTERVAL_MINUTES = 30
```

### 13.3 修改 B站分区范围

修改文件：

```text
app/config.py
```

配置项：

```python
GAME_PARENT_AREA_IDS = {2, 3, 6}
```

该集合用于筛选 B站直播中和游戏相关的父分区。

### 13.4 增加游戏名称别名

修改文件：

```text
app/config.py
```

配置项：

```python
NAME_ALIASES = {
    "cs2": "counterstrike2"
}
```

增加别名后，`utils.normalize_name()` 会自动应用到搜索匹配和分区匹配中。

### 13.5 增加新的数据源

推荐流程：

1. 在 `spiders/` 下新增爬虫文件。
2. 输出字段统一为字典列表。
3. 在 `app/cleaning.py` 中增加对应清洗函数。
4. 在 `app/batch_crawl.py` 的 `DATASET_SPECS` 中登记数据源。
5. 在 `refresh_batch_sources()` 的任务列表中加入新的 fetcher 和 cleaner。
6. 如需入库，在 `app/db.py` 增加表结构，在 `app/repository.py` 增加写入和读取函数。
7. 如需前端展示，在 `app/main.py` 增加 API 或扩展现有 API，在 `webapp/static/app.js` 增加渲染逻辑。

## 14. 验证结果

当前项目已经完成以下验证：

```bash
python spiders/static_game_spider.py --limit 350
python spiders/bilibili_live_api_spider.py --limit 350 --workers 16
python spiders/bilibili_dynamic_live_spider.py --limit 350 --workers 16
python -m unittest discover -s tests
```

验证结果：

| 项目 | 结果 |
| --- | --- |
| 静态游戏目录单独运行 | 成功，cleaned 350 条 |
| B站 API 爬虫单独运行 | 成功，cleaned 350 条 |
| B站动态页面源单独运行 | 成功，cleaned 350 条 |
| SQLite 首页数据刷新 | 成功 |
| 单元测试 | 5 个测试通过 |
| Python 语法编译检查 | 19 个文件通过 |

## 15. 文件职责总表

| 文件 | 职责 |
| --- | --- |
| `app/main.py` | FastAPI 应用入口、路由、启动事件、关闭事件 |
| `app/services.py` | 爬取服务层、刷新流程、攻略视频服务 |
| `app/batch_crawl.py` | 三类数据源批量采集、JSON 写入、数据源状态统计 |
| `app/repository.py` | SQLite 读写、首页聚合、搜索匹配、诊断文本 |
| `app/db.py` | 数据库连接、建表、旧表迁移 |
| `app/scheduler.py` | APScheduler 定时任务配置 |
| `app/cleaning.py` | 数据清洗、过滤脏数据、去重 |
| `app/config.py` | 项目路径、采集数量、超时、并发、别名配置 |
| `app/utils.py` | 时间生成、游戏名归一化 |
| `spiders/bootstrap.py` | 支持直接运行爬虫脚本 |
| `spiders/common.py` | 爬虫命令行参数和 JSON 导出 |
| `spiders/static_game_spider.py` | 游民星空和 Steam 游戏目录采集 |
| `spiders/bilibili_live_api_spider.py` | B站直播 API 数据采集 |
| `spiders/bilibili_dynamic_live_spider.py` | B站动态页面源数据采集 |
| `spiders/bilibili_strategy_video_spider.py` | B站攻略视频搜索 |
| `webapp/templates/index.html` | 首页 HTML 结构 |
| `webapp/static/app.js` | 前端请求、事件处理、DOM 渲染 |
| `webapp/static/styles.css` | 页面样式和响应式布局 |
| `tests/test_cleaning.py` | 清洗和去重测试 |
| `tests/test_matching.py` | 名称归一化和诊断逻辑测试 |
| `requirements.txt` | Python 依赖列表 |
| `README.md` | 项目快速说明和运行命令 |
| `docs/PROJECT_MAP.md` | 项目结构和函数调用说明 |
| `docs/PROJECT_REPORT.md` | 当前完整项目报告书 |
