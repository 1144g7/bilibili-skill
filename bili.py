"""
B站视频字幕提取 + 总结一体化工具

用法:
    # 只要字幕（存本地 TXT + SRT）
    python bili.py BV1eXRhBSE1k
    python bili.py BV1eXRhBSE1k --mode subtitle --output-dir C:\\Users\\14582\\Desktop

    # 总结模式（字幕文本输出到 stdout，由 AI 直接总结）
    python bili.py BV1eXRhBSE1k --mode summarize

    # 完整 URL 也支持
    python bili.py https://www.bilibili.com/video/BV1eXRhBSE1k

默认模式: subtitle
"""
import requests
import json
import time
import hashlib
import urllib.parse
import re
import os
import sys
import shutil
import sqlite3
import glob
import argparse

# ─────────────────────────────────────────────
# 配置
# ─────────────────────────────────────────────
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
                  '(KHTML, like Gecko) Chrome/125.0.0.0 Safari/537.36',
    'Referer': 'https://www.bilibili.com'
}

# WBI 签名所需的混淆表
MIXIN_KEY_ENC_TAB = [
    46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,
    33,9,42,19,29,28,14,39,12,38,41,16,20,36,34,17,6,22,48,44,
    40,21,25,13,4,52,37,11,26,55,1,24,7,51,56,57,30,59,0,61,54,
    60,63,62,7,4,61,22,57,13,34,52,49,20,48,59,26,39,32,24,1,
    11,56,16,35,63,6,17,3,45,55,58,37,44,21,25,33,14,30,53,23,
    2,42,36,19,40,10,38,54,9,5,12,51,15,29,8,60,43,50,31,62,28,
    47,41,18,46,0,27
]


# ─────────────────────────────────────────────
# Cookies
# ─────────────────────────────────────────────
def _read_firefox_cookies(db_path, domain_filter='bilibili'):
    """从 Firefox 类浏览器的 cookies.sqlite 读取（无需管理员）"""
    tmp = '_tmp_bili.sqlite'
    shutil.copy2(db_path, tmp)
    try:
        conn = sqlite3.connect(tmp)
        rows = conn.execute(
            "SELECT name, value FROM moz_cookies WHERE host LIKE ?",
            (f"%{domain_filter}%",)
        ).fetchall()
        conn.close()
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    return {r[0]: r[1] for r in rows}


def _find_firefox_based_cookies(domain_filter='bilibili'):
    """自动检测所有 Firefox 类浏览器，返回第一个有 SESSDATA 的"""
    search_paths = [
        # Zen Browser
        os.path.expanduser(r"~\AppData\Roaming\zen\Profiles"),
        # Firefox
        os.path.expanduser(r"~\AppData\Roaming\Mozilla\Firefox\Profiles"),
        # LibreWolf
        os.path.expanduser(r"~\AppData\Roaming\librewolf\Profiles"),
    ]
    for profile_dir in search_paths:
        dbs = glob.glob(os.path.join(profile_dir, "*", "cookies.sqlite"))
        for db in sorted(dbs, key=os.path.getsize, reverse=True):
            cookies = _read_firefox_cookies(db, domain_filter)
            if cookies.get('SESSDATA'):
                return cookies
    return None


def get_cookies(domain_filter='bilibili'):
    """
    获取 bilibili cookies，按优先级尝试:
    1. cookies.json（setup_cookies.py 导出，支持任何浏览器）
    2. Firefox 类浏览器自动检测（Zen/Firefox/LibreWolf，无需管理员）
    3. 都没有 → 提示用户运行 setup_cookies.py
    """
    # 1. 读已导出的 cookies.json
    json_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.json')
    if os.path.exists(json_path):
        try:
            with open(json_path, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            if cookies.get('SESSDATA'):
                return cookies
        except Exception:
            pass

    # 2. 自动检测 Firefox 类浏览器
    cookies = _find_firefox_based_cookies(domain_filter)
    if cookies:
        return cookies

    # 3. 都没有
    print("⚠️  未找到 bilibili cookies", file=sys.stderr)
    print("   请运行以下命令导出 cookies（Chrome/Edge 需要管理员）:", file=sys.stderr)
    print("     python setup_cookies.py chrome", file=sys.stderr)
    print("   或者安装 Zen Browser 并登录 bilibili.com（免管理员）", file=sys.stderr)
    return {}


# ─────────────────────────────────────────────
# WBI 签名
# ─────────────────────────────────────────────
def get_mixin_key():
    r = requests.get('https://api.bilibili.com/x/web-interface/nav', headers=HEADERS)
    data = r.json().get('data', {})
    img_url = data.get('wbi_img', {}).get('img_url', '')
    sub_url = data.get('wbi_img', {}).get('sub_url', '')
    img_key = re.search(r'([a-f0-9]{32})', img_url)
    sub_key = re.search(r'([a-f0-9]{32})', sub_url)
    if not img_key or not sub_key:
        raise RuntimeError("无法获取 WBI mixin key，B站接口可能有变动")
    mixin_key = img_key.group(1) + sub_key.group(1)
    return ''.join(mixin_key[i] for i in MIXIN_KEY_ENC_TAB)[:32]


def sign_params(params, mixin_key):
    params = dict(params)
    params['wts'] = int(time.time())
    query = urllib.parse.urlencode(sorted(params.items()))
    params['w_rid'] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return params


# ─────────────────────────────────────────────
# 核心：获取字幕
# ─────────────────────────────────────────────
def extract_bvid(url_or_bvid):
    url_or_bvid = url_or_bvid.strip()
    m = re.search(r'(BV[\w]+)', url_or_bvid)
    return m.group(1) if m else url_or_bvid


def fetch_subtitles(bvid):
    """
    获取 B站视频字幕（含 AI 字幕）
    返回: (video_info_dict, subtitles_list) 或 (info, None)
    """
    # 获取视频基本信息
    r = requests.get(
        f'https://api.bilibili.com/x/web-interface/view?bvid={bvid}',
        headers=HEADERS
    )
    video_data = r.json().get('data')
    if not video_data:
        msg = r.json().get('message', 'unknown')
        print(f"❌ 无法获取视频信息: {msg}", file=sys.stderr)
        return None, None

    info = {
        'bvid': bvid,
        'cid': video_data['cid'],
        'title': video_data['title'],
        'duration': video_data['duration'],
        'owner': video_data.get('owner', {}).get('name', ''),
    }
    dur = info['duration']
    print(f"📺 {info['title']}")
    print(f"👤 {info['owner']}  ⏱️  {dur // 60}:{dur % 60:02d}")

    # 带 cookies + WBI 签名请求字幕列表
    cookies = get_cookies('bilibili')
    mixin_key = get_mixin_key()
    params = sign_params({'bvid': bvid, 'cid': info['cid']}, mixin_key)

    r = requests.get(
        'https://api.bilibili.com/x/player/wbi/v2',
        params=params, headers=HEADERS, cookies=cookies
    )
    subtitle_info = r.json().get('data', {}).get('subtitle', {})
    subs = subtitle_info.get('subtitles', [])

    if not subs:
        print("ℹ️  该视频没有任何字幕（包括 AI 字幕）", file=sys.stderr)
        return info, None

    print(f"✅ 找到 {len(subs)} 条字幕轨:")
    results = []
    for sub in subs:
        lang = sub.get('lan', '')
        lang_doc = sub.get('lan_doc', '')
        is_ai = lang.startswith('ai-')
        sub_url = sub.get('subtitle_url', '')
        if sub_url.startswith('//'):
            sub_url = 'https:' + sub_url
        print(f"   {'[AI]' if is_ai else '[手动]'} {lang_doc} ({lang})")
        sub_r = requests.get(sub_url, headers={'Referer': 'https://www.bilibili.com'})
        body = sub_r.json().get('body', [])
        results.append({
            'lang': lang,
            'lang_doc': lang_doc,
            'is_ai': is_ai,
            'segments': body
        })

    return info, results


def pick_best_subtitle(subtitles):
    """优先选中文字幕（ai-zh > zh-Hans > zh-CN > 其他 zh > 第一条）"""
    priority = ['ai-zh', 'zh-Hans', 'zh-CN']
    for p in priority:
        for s in subtitles:
            if s['lang'] == p:
                return s
    for s in subtitles:
        if 'zh' in s['lang']:
            return s
    return subtitles[0]


def segments_to_text(segments):
    """字幕片段列表 → 纯文本（每行一句）"""
    return '\n'.join(seg.get('content', '') for seg in segments)


def segments_to_srt(segments):
    """字幕片段列表 → SRT 格式字符串"""
    lines = []
    for i, seg in enumerate(segments, 1):
        start = seg.get('from', 0)
        end = seg.get('to', 0)
        content = seg.get('content', '')
        lines.append(str(i))
        lines.append(f"{_fmt_srt(start)} --> {_fmt_srt(end)}")
        lines.append(content)
        lines.append('')
    return '\n'.join(lines)


def _fmt_srt(sec):
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = int(sec % 60)
    ms = int((sec % 1) * 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def safe_filename(title, max_len=60):
    name = re.sub(r'[\\/:*?"<>|]', '_', title)
    return name[:max_len] if len(name) > max_len else name


# ─────────────────────────────────────────────
# 模式一：字幕模式（存本地）
# ─────────────────────────────────────────────
def mode_subtitle(info, subtitles, output_dir, prefix='00A'):
    best = pick_best_subtitle(subtitles)
    title_safe = safe_filename(info['title'])
    base = os.path.join(output_dir, f"{prefix}_{title_safe}")

    txt_path = base + '.txt'
    srt_path = base + '.srt'

    text = segments_to_text(best['segments'])
    srt = segments_to_srt(best['segments'])

    with open(txt_path, 'w', encoding='utf-8') as f:
        f.write(text)
    with open(srt_path, 'w', encoding='utf-8') as f:
        f.write(srt)

    lang_label = f"{best['lang_doc']} ({best['lang']})"
    print(f"\n💾 已保存:")
    print(f"   TXT → {txt_path}")
    print(f"   SRT → {srt_path}")
    print(f"   字幕: {lang_label}  {'[AI生成]' if best['is_ai'] else '[人工]'}")
    print(f"   行数: {len(best['segments'])}")


# ─────────────────────────────────────────────
# 模式二：总结模式（输出字幕文本到 stdout，由外部 AI 总结）
# ─────────────────────────────────────────────
def mode_summarize(info, subtitles):
    best = pick_best_subtitle(subtitles)
    text = segments_to_text(best['segments'])
    dur = info['duration']
    lang_label = f"{best['lang_doc']} ({best['lang']})"

    # 打印 metadata header（AI 读取用）
    print("=" * 60)
    print(f"BILIBILI_SUBTITLE_FOR_SUMMARIZATION")
    print(f"标题: {info['title']}")
    print(f"UP主: {info['owner']}")
    print(f"时长: {dur // 60}:{dur % 60:02d}")
    print(f"字幕: {lang_label}  {'[AI生成]' if best['is_ai'] else '[人工]'}")
    print(f"行数: {len(best['segments'])}")
    print("=" * 60)
    print(text)
    print("=" * 60)
    print("END_OF_SUBTITLE")


# ─────────────────────────────────────────────
# 主入口
# ─────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(
        description='B站字幕提取 + 总结一体化工具',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python bili.py BV1eXRhBSE1k                              # 字幕模式（默认）
  python bili.py BV1eXRhBSE1k --mode subtitle              # 字幕模式
  python bili.py BV1eXRhBSE1k --mode summarize             # 总结模式（输出到 stdout）
  python bili.py BV1eXRhBSE1k --output-dir C:\\Desktop     # 指定保存目录
  python bili.py https://www.bilibili.com/video/BV1eXRhBSE1k --mode summarize
        """
    )
    parser.add_argument('url', help='B站视频 URL 或 BV 号')
    parser.add_argument(
        '--mode', choices=['subtitle', 'summarize'], default='subtitle',
        help='subtitle: 字幕存本地 TXT+SRT（默认）  |  summarize: 字幕文本输出到 stdout 供 AI 总结'
    )
    parser.add_argument('--output-dir', default='.', help='字幕文件保存目录（subtitle 模式有效）')
    parser.add_argument('--prefix', default='00A', help='文件名前缀（默认 00A）')
    args = parser.parse_args()

    bvid = extract_bvid(args.url)
    print(f"🔍 BV号: {bvid}  模式: {args.mode}")

    info, subtitles = fetch_subtitles(bvid)
    if info is None:
        sys.exit(1)
    if subtitles is None:
        print("❌ 无字幕可用，建议走 Whisper 转写兜底", file=sys.stderr)
        sys.exit(2)

    if args.mode == 'subtitle':
        os.makedirs(args.output_dir, exist_ok=True)
        mode_subtitle(info, subtitles, args.output_dir, args.prefix)
    elif args.mode == 'summarize':
        mode_summarize(info, subtitles)


if __name__ == '__main__':
    main()
