---
name: bilibili-skill
description: B站视频字幕提取 + 总结（自动读取浏览器 cookies，零配置）
---

## 首次使用：配置 Cookies

B站需要登录态才能获取 AI 字幕。首次使用运行一次：

```bash
python setup_cookies.py
```

自动检测浏览器 cookies：
- **Firefox / Zen** → 零配置，直接读取
- **Edge** → 弹一次 UAC 提权，之后不再需要
- **Chrome** → 需手动导出 cookies（安装 Cookie-Editor 插件导出为 JSON），或用其他浏览器登录 B站

导出成功后生成 `cookies.json`，后续自动使用，无需重复配置。

## 触发词

"帮我总结 B站视频"、"B站视频讲了什么"、"提取 B站字幕"、"下载字幕"、"这个视频"、"bilibili"

## 使用方式

```bash
# 总结模式（字幕输出到 stdout，AI 直接总结）
python bili.py <URL或BV号> --mode summarize

# 字幕模式（存本地 TXT + SRT）
python bili.py <URL或BV号> --mode subtitle --output-dir ~/Desktop
```

| 模式 | 用户意图 | 输出 |
|------|----------|------|
| `summarize` | "总结"、"讲了什么"、"帮我看看" | 字幕文本到 stdout，AI 读取后总结 |
| `subtitle`（默认） | "下载字幕"、"只要字幕" | 本地 TXT + SRT 文件 |

## 总结模式流程

1. Agent 调用 `python bili.py <URL> --mode summarize`
2. bili.py 自动读取 cookies → 调用 B站 API → 获取字幕（含 AI 字幕）
3. 字幕文本输出到 stdout
4. **Agent 直接在对话里总结**（不调本地模型，不调外部 API）

## 字幕优先级

自动选择最佳字幕轨：ai-zh > zh-Hans > zh-CN > 其他中文 > 第一条

## 无字幕时

exit code = 2，提示"无字幕可用"。可配合 Whisper 转写兜底。

## URL 格式支持

- `https://www.bilibili.com/video/BVxxxxxx`
- `https://b23.tv/xxxxx`
- `BVxxxxxx`（直接传 BV 号）

## 依赖

```bash
pip install requests rookiepy
```

无其他依赖。不需要 yt-dlp、不需要 ffmpeg、不需要本地模型。
