# bilibili-skill

视频字幕提取工具。给 AI 总结用——输入 URL，输出纯文本字幕，无时间戳。

基于 yt-dlp，支持 B站、YouTube 以及 yt-dlp 支持的所有平台。

## 一行安装

```bash
pip install yt-dlp rookiepy
```

Whisper 兜底（可选）：`pip install openai-whisper`

## 首次配置

导出浏览器 cookies（B站/YouTube 需要登录态）：

```bash
python setup_cookies.py
```

自动检测浏览器：
- **Firefox / Zen** — 零配置，直接读取
- **Edge** — 弹一次 UAC，之后不再需要
- **Chrome** — 需手动导出 cookies，或用其他浏览器登录

## 使用

```bash
# 总结模式：字幕输出到 stdout，AI 直接总结
python get_subtitles.py <URL> --mode summarize

# 字幕模式：保存到本地 TXT
python get_subtitles.py <URL> --mode subtitle --output-dir ~/Desktop

# B站短格式也支持
python get_subtitles.py BV1dqkZBhEz3 --mode summarize
```

## 工作流程

```
输入 URL
  ↓
yt-dlp 获取字幕（B站 AI字幕 / YouTube 中文字幕 / 通用）
  ↓
有字幕 → 纯文本输出（无时间戳）
无字幕 → Whisper 转写兜底（需安装 openai-whisper）
```

## 字幕优先级

| 平台 | 优先级 |
|------|--------|
| B站 | ai-zh > zh-Hans > zh-CN > zh |
| YouTube | zh-CN > zh-Hans > zh > en |
| 其他 | zh-CN > zh-Hans > zh > en |

## 作为 Claude Code Skill 使用

将 `SKILL.md` 放到 `~/.claude/skills/bilibili-skill/` 即可。Agent 调用 `get_subtitles.py --mode summarize`，读取 stdout 输出直接总结。

## Cookies 说明

| 浏览器 | 方式 | 需要 |
|--------|------|------|
| Firefox / Zen | 自动读取 cookies.sqlite | 无 |
| Edge | rookiepy + UAC 提权 | 管理员一次 |
| Chrome | 手动导出或使用其他浏览器 | 用户自行处理 |

Chrome v130+ 使用 App-Bound Encryption，第三方工具即使管理员也无法解密 cookies。

## 许可

MIT
