# 游戏导航与攻略聚合平台

这是一个基于 FastAPI + SQLite 的课程项目，用三个不同类型的数据源做一个“热门游戏介绍 + 游戏搜索 + 攻略视频聚合”的网页。

## 项目目标

- 主页展示 Steam 热门游戏、价格、类型、简介和封面。
- 用户输入游戏名后，返回游戏基础信息、Steam 商店入口、B站攻略视频入口和简单热度诊断。
- 数据源覆盖课程要求的三类采集方式：静态网页、动态网页、API 接口。

## 三类数据源

| 类型 | 数据源 | 技术 | 用途 |
| --- | --- | --- | --- |
| 静态网页 | 游民星空游戏库 + 游侠专题页 | requests + BeautifulSoup | 批量采集游戏名称、详情页、封面、来源站点 |
| API 接口 | Bilibili 直播分区接口 | requests + 并发请求 | 批量采集直播房间、分区、主播、热度 |
| 动态网页 | Bilibili 直播动态加载数据 | requests 并发采集动态加载接口；单游戏攻略搜索保留 Playwright 降级路径 | 批量采集动态页面背后的直播房间数据，并为网页搜索提供攻略入口 |

## 项目结构

```text
app/                    # FastAPI 后端与核心业务逻辑
  crawlers/             # 可复用爬虫实现
  main.py               # Web 入口和 API 路由
  repository.py         # SQLite 读写和数据聚合
  services.py           # 刷新任务与搜索服务
spiders/                # 课程要求的三类爬虫入口脚本
  spider_static.py      # 静态网页爬虫，默认 350 条
  spider_dynamic.py     # 动态网页数据爬虫，默认 350 条
  spider_api.py         # API 接口爬虫，默认 350 条
data/
  game_market.db        # SQLite 数据库
  raw/                  # 原始采集结果导出
  cleaned/              # 清洗后数据导出
webapp/
  templates/            # 页面模板
  static/               # CSS 和 JS
docs/                   # 报告、分工表、答辩材料
tests/                  # 单元测试
```

## 运行方式

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

启动后打开 <http://127.0.0.1:8000>。

网页启动后会自动启动 APScheduler 定时任务：

- 启动时立即后台刷新一次三类数据源。
- 之后按 `app/config.py` 中的 `REFRESH_INTERVAL_MINUTES` 自动周期刷新，当前为 30 分钟。
- 首页会展示“自动定时爬取”运行状态、下一次执行时间，以及三类 cleaned 数据文件的条数和更新时间。
- 页面右上角“立即爬取”按钮可手动触发同一套批量采集、清洗、去重流程。

如果要启用 B站动态页面真实抓取，额外安装浏览器依赖：

```bash
pip install playwright
playwright install chromium
```

未安装 Playwright 时，搜索功能会自动降级为返回 Bilibili 搜索链接，不影响网页运行。

## 测试

```bash
python -m unittest discover -s tests
```

## 批量采集

三个采集入口都支持 `--limit`，默认目标为 350 条。脚本会同时写入 `data/raw/` 和 `data/cleaned/`，清洗层会过滤空标题、空链接、异常占位文本，并按 URL 或房间 ID 去重。

```bash
python -m spiders.spider_static --limit 350
python -m spiders.spider_api --limit 350
python -m spiders.spider_dynamic --limit 350
```
