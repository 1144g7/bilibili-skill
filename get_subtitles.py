"""
视频字幕提取工具（通用版）

支持: B站 / YouTube / 以及 yt-dlp 支持的所有平台
底层: yt-dlp + 自动 cookies 管理

用法:
    python get_subtitles.py <URL> --mode summarize    # 字幕输出到 stdout，AI 总结
    python get_subtitles.py <URL> --mode subtitle     # 字幕存本地 TXT + SRT
    python get_subtitles.py <URL>                     # 默认 subtitle 模式

首次使用请先运行: python setup_cookies.py
"""
import subprocess
import json
import os
import sys
import re
import argparse

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_DIR = os.path.join(SCRIPT_DIR, 'cookies')


# ─────────────────────────────────────────────
# URL 检测
# ─────────────────────────────────────────────
def detect_platform(url):
    """根据 URL 判断平台，返回 cookies 文件名和域名"""
    url = url.strip()
    if 'bilibili.com' in url or 'b23.tv' in url or re.match(r'^BV[\w]+', url):
        return 'bilibili', 'bilibili'
    elif 'youtube.com' in url or 'youtu.be' in url:
        return 'youtube', 'youtube'
    return None, None


# ─────────────────────────────────────────────
# Cookies 管理
# ─────────────────────────────────────────────
def _find_cookies_netscape(domain):
    """查找 Netscape 格式的 cookies 文件"""
    # 1. 按域名查找: cookies/bilibili.txt, cookies/youtube.txt
    domain_path = os.path.join(COOKIES_DIR, f'{domain}.txt')
    if os.path.exists(domain_path):
        return domain_path

    # 2. 通用 cookies.txt
    generic = os.path.join(COOKIES_DIR, 'cookies.txt')
    if os.path.exists(generic):
        return generic

    return None


def ensure_cookies(domain):
    """确保有 cookies 文件，没有就提示用户运行 setup"""
    os.makedirs(COOKIES_DIR, exist_ok=True)
    path = _find_cookies_netscape(domain)
    if path:
        return path

    # 没找到，尝试自动从 Firefox 类浏览器导出
    auto_path = _auto_export_firefox(domain)
    if auto_path:
        return auto_path

    print(f"⚠️  未找到 {domain} 的 cookies", file=sys.stderr)
    print(f"   请运行: python setup_cookies.py", file=sys.stderr)
    return None


def _auto_export_firefox(domain):
    """尝试从 Firefox 类浏览器自动导出 cookies（无需管理员）"""
    import glob
    import sqlite3
    import shutil

    search_paths = [
        os.path.expanduser(r"~\AppData\Roaming\zen\Profiles"),
        os.path.expanduser(r"~\AppData\Roaming\Mozilla\Firefox\Profiles"),
        os.path.expanduser(r"~\AppData\Roaming\librewolf\Profiles"),
    ]

    for profile_dir in search_paths:
        dbs = glob.glob(os.path.join(profile_dir, "*", "cookies.sqlite"))
        for db in sorted(dbs, key=os.path.getsize, reverse=True):
            try:
                tmp = os.path.join(SCRIPT_DIR, '_tmp_cookies.sqlite')
                shutil.copy2(db, tmp)
                try:
                    conn = sqlite3.connect(tmp)
                    rows = conn.execute(
                        "SELECT host, path, isSecure, expiry, name, value "
                        "FROM moz_cookies WHERE host LIKE ?",
                        (f"%{domain}%",)
                    ).fetchall()
                    conn.close()
                finally:
                    if os.path.exists(tmp):
                        os.remove(tmp)

                if not rows:
                    continue

                # 有 cookies，保存为 Netscape 格式
                out = os.path.join(COOKIES_DIR, f'{domain}.txt')
                with open(out, 'w', encoding='utf-8') as f:
                    f.write("# Netscape HTTP Cookie File\n")
                    for host, path, secure, expiry, name, value in rows:
                        f.write(f"{host}\t{'TRUE' if host.startswith('.') else 'FALSE'}\t"
                                f"{path}\t{'TRUE' if secure else 'FALSE'}\t"
                                f"{expiry or 0}\t{name}\t{value}\n")

                print(f"  自动导出 {domain} cookies: {len(rows)} 条 (from {os.path.basename(os.path.dirname(db))})", file=sys.stderr)
                return out
            except Exception:
                continue

    return None


# ─────────────────────────────────────────────
# yt-dlp 调用
# ─────────────────────────────────────────────
def get_video_info(url, cookies_path=None):
    """获取视频标题和时长"""
    cmd = [sys.executable, '-m', 'yt_dlp', '--print', '%(title)s|||%(duration)s', '--no-warnings']
    if cookies_path:
        cmd += ['--cookies', cookies_path]
    cmd.append(url)

    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8')
        if r.returncode != 0:
            # 网络波动重试一次
            import time; time.sleep(2)
            r = subprocess.run(cmd, capture_output=True, text=True, timeout=30, encoding='utf-8')
        if r.returncode != 0:
            print(f"❌ 获取视频信息失败: {r.stderr.strip()}", file=sys.stderr)
            return None, None
        line = r.stdout.strip().split('\n')[0]
        parts = line.split('|||')
        title = parts[0] if len(parts) > 0 else 'unknown'
        duration = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
        return title, duration
    except subprocess.TimeoutExpired:
        print("❌ 获取视频信息超时", file=sys.stderr)
        return None, None


def list_subs(url, cookies_path=None):
    """列出可用字幕"""
    cmd = [sys.executable, '-m', 'yt_dlp', '--list-subs', '--no-warnings']
    if cookies_path:
        cmd += ['--cookies', cookies_path]
    cmd.append(url)

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding='utf-8')
    return r.stdout, r.returncode


def download_sub(url, lang, fmt, output_path, cookies_path=None):
    """下载指定语言的字幕"""
    cmd = [
        sys.executable, '-m', 'yt_dlp',
        '--write-subs',       # 手动字幕（B站 ai-zh 也走这个）
        '--write-auto-subs',  # 自动字幕（YouTube auto-generated）
        '--sub-langs', lang,
        '--sub-format', fmt,
        '--skip-download',
        '-o', output_path,
        '--no-warnings',
    ]
    if cookies_path:
        cmd += ['--cookies', cookies_path]
    cmd.append(url)

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding='utf-8')
    if r.returncode != 0:
        import time; time.sleep(3)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=60, encoding='utf-8')
    return r.returncode, r.stderr


def _parse_srt_to_text(srt_path):
    """SRT → 纯文本（每行一句）"""
    with open(srt_path, 'r', encoding='utf-8') as f:
        content = f.read()
    lines = []
    for line in content.split('\n'):
        line = line.strip()
        # 跳过序号、时间戳、空行
        if not line or line.isdigit() or '-->' in line:
            continue
        lines.append(line)
    return '\n'.join(lines)


def _find_downloaded_srt(base_path):
    """找 yt-dlp 下载的字幕文件（后缀不确定）"""
    import glob as g
    patterns = [
        f"{base_path}.*.srt",
        f"{base_path}.*.vtt",
        f"{base_path}.srt",
        f"{base_path}.vtt",
    ]
    for p in patterns:
        files = g.glob(p)
        if files:
            return files[0]
    return None


# ─────────────────────────────────────────────
# 字幕语言优先级
# ─────────────────────────────────────────────
LANG_PRIORITY = {
    'bilibili': ['ai-zh', 'zh-Hans', 'zh-CN', 'zh'],
    'youtube': ['zh-CN', 'zh-Hans', 'zh', 'en'],
    'default': ['zh-CN', 'zh-Hans', 'zh', 'en'],
}


# ─────────────────────────────────────────────
# Whisper 兜底
# ─────────────────────────────────────────────
def _download_audio(url, cookies_path=None):
    """用 yt-dlp 下载音频"""
    import glob as _g
    base = os.path.join('.', '_tmp_audio')
    # 清理旧文件
    for old in _g.glob(f"{base}.*"):
        try: os.remove(old)
        except: pass

    cmd = [
        sys.executable, '-m', 'yt_dlp',
        '-f', 'bestaudio[ext=m4a]',
        '-x', '--audio-format', 'mp3',
        '-o', f'{base}.%(ext)s',
        '--no-warnings',
    ]
    if cookies_path:
        cmd += ['--cookies', cookies_path]
    cmd.append(url)

    r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding='utf-8')
    if r.returncode != 0:
        import time; time.sleep(3)
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=120, encoding='utf-8')

    # 找下载的文件
    for ext in ['mp3', 'm4a', 'webm', 'opus']:
        path = f"{base}.{ext}"
        if os.path.exists(path):
            print(f"  📥 音频下载完成: {ext}", file=sys.stderr)
            return path
    return None


def _whisper_transcribe(audio_path):
    """调用 Whisper 转写"""
    try:
        import whisper
    except ImportError:
        print("  Whisper 未安装，跳过转写", file=sys.stderr)
        return None

    print(f"  🎤 Whisper 转写中...", file=sys.stderr)
    try:
        model = whisper.load_model("base")
        result = model.transcribe(audio_path, fp16=False)
        text = result.get('text', '').strip()
        if text:
            print(f"  ✅ 转写完成: {len(text)} 字", file=sys.stderr)
            return text
    except Exception as e:
        print(f"  ❌ Whisper 失败: {e}", file=sys.stderr)
    return None


def _output_text(text, title, dur_str, source, args):
    """统一输出（字幕和 Whisper 共用）"""
    lines = text.count('\n') + 1
    if args.mode == 'summarize':
        print("=" * 60)
        print(f"SUBTITLE_FOR_SUMMARIZATION")
        print(f"标题: {title}")
        print(f"时长: {dur_str}")
        print(f"来源: {source}")
        print(f"行数: {lines}")
        print("=" * 60)
        print(text)
        print("=" * 60)
        print("END_OF_SUBTITLE")
    else:
        import re as _re, shutil
        safe = _re.sub(r'[\\/:*?"<>|]', '_', title)[:60]
        txt_path = os.path.join(args.output_dir, f"{safe}.txt")
        with open(txt_path, 'w', encoding='utf-8') as f:
            f.write(text)
        print(f"\n💾 已保存:")
        print(f"   TXT → {txt_path}")
        print(f"   来源: {source}")
        print(f"   行数: {lines}")


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='视频字幕提取工具（支持 B站/YouTube/通用）',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python get_subtitles.py https://www.bilibili.com/video/BVxxxxx --mode summarize
  python get_subtitles.py https://www.youtube.com/watch?v=xxxxx --mode summarize
  python get_subtitles.py BVxxxxx                              # 字幕模式（默认）
  python get_subtitles.py <URL> --mode subtitle --output-dir ~/Desktop
        """
    )
    parser.add_argument('url', help='视频 URL（B站/YouTube/通用）')
    parser.add_argument(
        '--mode', choices=['subtitle', 'summarize'], default='subtitle',
        help='subtitle: 存本地 TXT+SRT | summarize: 输出到 stdout 供 AI 总结'
    )
    parser.add_argument('--output-dir', default='.', help='字幕保存目录')
    parser.add_argument('--lang', default=None, help='指定字幕语言（如 zh-CN, en）')
    args = parser.parse_args()

    # 补全 B站短格式
    url = args.url.strip()
    if re.match(r'^BV[\w]+$', url):
        url = f'https://www.bilibili.com/video/{url}'

    # 检测平台
    platform, domain = detect_platform(url)
    print(f"🔍 平台: {platform or '通用'}  模式: {args.mode}")

    # 准备 cookies
    cookies_path = ensure_cookies(domain) if domain else None

    # 获取视频信息
    title, duration = get_video_info(url, cookies_path)
    if not title:
        sys.exit(1)
    dur_str = f"{duration // 60}:{duration % 60:02d}" if duration else "?"
    print(f"📺 {title}  ⏱️ {dur_str}")

    # 确定字幕语言
    if args.lang:
        lang = args.lang
    else:
        priority = LANG_PRIORITY.get(platform, LANG_PRIORITY['default'])
        lang = ','.join(priority)

    # 下载字幕
    base = os.path.join(args.output_dir if args.mode == 'subtitle' else '.', '_tmp_sub')
    # 清理旧临时文件
    import glob as _g
    for old in _g.glob(f"{base}.*"):
        try: os.remove(old)
        except: pass

    if cookies_path:
        print(f"🔑 使用 cookies: {os.path.basename(cookies_path)}", file=sys.stderr)

    code, stderr = download_sub(url, lang, 'srt', base, cookies_path)

    srt_file = _find_downloaded_srt(base)

    # ── Whisper 兜底：没字幕 → 下载音频 → 转写 ──
    if not srt_file:
        print("ℹ️  无字幕，尝试 Whisper 转写兜底...", file=sys.stderr)
        audio_file = _download_audio(url, cookies_path)
        if audio_file:
            text = _whisper_transcribe(audio_file)
            if text:
                _output_text(text, title, dur_str, 'Whisper', args)
                try: os.remove(audio_file)
                except: pass
                return
            try: os.remove(audio_file)
            except: pass

        print("❌ 字幕获取失败（无字幕 + Whisper 不可用）", file=sys.stderr)
        print("   安装 Whisper: pip install openai-whisper", file=sys.stderr)
        sys.exit(2)

    # 正常路径：有字幕
    text = _parse_srt_to_text(srt_file)

    # 输出
    source = os.path.basename(srt_file)
    _output_text(text, title, dur_str, source, args)

    # 清理临时文件
    try:
        os.remove(srt_file)
    except:
        pass


if __name__ == '__main__':
    main()
