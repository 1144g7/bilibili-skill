# bilibili-skill

把视频 URL 发给你的 AI Agent，自动提取字幕并总结。支持 B站、YouTube 及更多平台。

## 安装

把视频链接发给你的 Agent 就行。

如果你想手动安装，以下是步骤：

```bash
pip install yt-dlp rookiepy
python setup_cookies.py    # 导出浏览器 cookies（首次）
```

如果有本地部署的模型，推荐 qwen3.5 4b，可以比较轻松地完成总结任务。

## 手动使用

```bash
python get_subtitles.py <URL> --mode summarize    # 字幕输出到 stdout
python get_subtitles.py <URL> --mode subtitle     # 保存到本地 TXT
```

## Cookies

| 浏览器 | 方式 |
|--------|------|
| Firefox / Zen | 零配置，自动读取 |
| Edge | 首次弹 UAC，之后不管 |
| Chrome | 需手动导出，或用其他浏览器登录 |

## 许可

MIT
