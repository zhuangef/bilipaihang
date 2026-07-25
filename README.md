# bili_up_video_rank

抓取 B 站指定关注分组中的全部 UP 主，遍历每位 UP 的投稿视频，获取播放、收藏、点赞、投币、评论、弹幕、分享、发布时间、时长等信息，排序后导出 JSON、CSV、Excel。

## 功能

- 自动获取指定关注分组的全部 UP 主。
- 自动分页遍历每位 UP 的投稿；传入 `start_date` 时遇到更早视频会提前停止，避免无效翻页。
- 获取每个视频的完整统计数据。
- 按播放、收藏、点赞、投币、评论、分享、发布时间、时长排序。
- 支持断点续跑，已完成 UP 不重复抓取。
- 自动限速与重试，并用本地缓存减少重复请求视频详情。
- 支持按发布时间和时长筛选。
- 一键导出 `output/all_video.json`、`output/all_video.csv`、`output/all_video.xlsx`。
- Excel 包含「全部视频」「按年度统计」「每个UP统计」以及按 UP 名称拆分的遍历视频工作表，每个 UP 工作表记录该 UP 实际遍历到的所有视频。

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 使用

1. 登录网页版 B 站，复制请求 Cookie。
2. 找到关注分组 ID（接口参数通常叫 `tagid`）。
3. 运行：

```bash
export BILI_COOKIE='你的 Cookie'
python bili_up_video_rank/main.py --group-id 123456 --sort-by favorite
```

常用参数：

```bash
python bili_up_video_rank/main.py \
  --group-id 123456 \
  --sort-by view \
  --start-date 2024-01-01 \
  --end-date 2024-12-31 \
  --min-duration 60 \
  --max-duration 3600
```

如需重新抓取并清空断点状态：

```bash
python bili_up_video_rank/main.py --group-id 123456 --reset
```

## 配置

可直接编辑 `bili_up_video_rank/config.py`，也可使用环境变量：

- `BILI_COOKIE`
- `BILI_FOLLOW_GROUP_ID`
- `BILI_SORT_BY`
- `BILI_SORT_DESC`
- `BILI_START_DATE`
- `BILI_END_DATE`
- `BILI_MIN_DURATION`
- `BILI_MAX_DURATION`
- `BILI_REQUEST_INTERVAL`
- `BILI_RETRY_TIMES`
- `BILI_CACHE_TTL_SECONDS`

## 注意

请合理设置请求间隔，不要高频请求。Cookie 仅保存在本地环境变量或配置文件中，请勿提交真实 Cookie。
