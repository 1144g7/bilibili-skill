"""
视频字幕工具 - Cookies 导出

导出浏览器 cookies 供 yt-dlp 使用（Netscape 格式）
支持 bilibili 和 youtube 两个平台

用法:
    python setup_cookies.py            # 自动检测所有浏览器，导出 bilibili + youtube
    python setup_cookies.py bilibili   # 只导出 bilibili
    python setup_cookies.py youtube    # 只导出 youtube
    python setup_cookies.py all        # 导出全部

Cookie 获取方式:
    Firefox / Zen:  零配置，直接读取（推荐）
    Edge:          需要管理员权限（弹 UAC，一次即可）
    Chrome:        需手动导出（安装 Cookie-Editor 插件），
                   或使用 Edge / Firefox / Zen 登录对应网站
"""
import sys
import os
import glob
import shutil
import sqlite3

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
COOKIES_DIR = os.path.join(SCRIPT_DIR, 'cookies')

DOMAINS = {
    'bilibili': 'bilibili.com',
    'youtube': 'youtube.com',
}


# ─────────────────────────────────────────────
# Firefox 类浏览器（不需要管理员）
# ─────────────────────────────────────────────
def _read_firefox_sqlite(db_path, domain):
    """从 Firefox 类 cookies.sqlite 读取"""
    tmp = os.path.join(SCRIPT_DIR, '_tmp_setup.sqlite')
    shutil.copy2(db_path, tmp)
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
    return rows


def _save_netscape(rows, domain_key):
    """保存为 Netscape 格式"""
    os.makedirs(COOKIES_DIR, exist_ok=True)
    out = os.path.join(COOKIES_DIR, f'{domain_key}.txt')
    with open(out, 'w', encoding='utf-8') as f:
        f.write("# Netscape HTTP Cookie File\n")
        for host, path, secure, expiry, name, value in rows:
            f.write(f"{host}\t{'TRUE' if host.startswith('.') else 'FALSE'}\t"
                    f"{path}\t{'TRUE' if secure else 'FALSE'}\t"
                    f"{expiry or 0}\t{name}\t{value}\n")
    return out, len(rows)


def try_firefox_based(domain):
    """尝试从所有 Firefox 类浏览器读取"""
    search_paths = [
        ('Zen', os.path.expanduser(r"~\AppData\Roaming\zen\Profiles")),
        ('Firefox', os.path.expanduser(r"~\AppData\Roaming\Mozilla\Firefox\Profiles")),
        ('LibreWolf', os.path.expanduser(r"~\AppData\Roaming\librewolf\Profiles")),
    ]

    for name, profile_dir in search_paths:
        dbs = glob.glob(os.path.join(profile_dir, "*", "cookies.sqlite"))
        for db in sorted(dbs, key=os.path.getsize, reverse=True):
            try:
                rows = _read_firefox_sqlite(db, domain)
                if rows:
                    return name, rows
            except Exception:
                continue
    return None, []


# ─────────────────────────────────────────────
# Edge（需要管理员）
# ─────────────────────────────────────────────
def try_edge(domain, force_admin=False):
    """尝试从 Edge 读取 cookies"""
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        if force_admin:
            return None, []
        # 弹 UAC 提权，重新运行自己
        import subprocess
        script = os.path.abspath(__file__)
        subprocess.run(
            ['powershell', '-Command',
             f'Start-Process python -ArgumentList \'{script} {domain}\' -Verb RunAs'],
            check=True
        )
        return None, None  # 新窗口处理

    import rookiepy
    cookies = rookiepy.edge(domains=[domain])
    # 转为 Netscape 行格式
    rows = []
    for c in cookies:
        host = c.get('domain', '')
        if not host:
            continue
        rows.append((
            host, c.get('path', '/'),
            c.get('secure', False), c.get('expires', 0),
            c.get('name', ''), c.get('value', '')
        ))
    return 'Edge', rows


# ─────────────────────────────────────────────
# 主流程
# ─────────────────────────────────────────────
def export_domain(domain_key):
    """导出某个域名的 cookies"""
    domain = DOMAINS[domain_key]
    print(f"\n📡 {domain_key} ({domain})")

    # 1. Firefox 类
    print(f"  尝试 Firefox/Zen...", end=' ')
    browser, rows = try_firefox_based(domain)
    if rows:
        print(f"✅ {browser} 找到 {len(rows)} 条")
        path, count = _save_netscape(rows, domain_key)
        print(f"  保存到: {path} ({count} 条)")
        return True
    print("未找到")

    # 2. Edge
    print(f"  尝试 Edge（可能弹 UAC）...", end=' ')
    browser, rows = try_edge(domain)
    if rows is None:
        print("请在弹出的管理员窗口中完成导出")
        return None  # UAC 弹窗中
    if rows:
        print(f"✅ Edge 找到 {len(rows)} 条")
        path, count = _save_netscape(rows, domain_key)
        print(f"  保存到: {path} ({count} 条)")
        return True
    print("未找到")

    print(f"  ⚠️ {domain_key} cookies 导出失败")
    print(f"     请在浏览器中登录 {domain} 后重试")
    print(f"     Chrome 用户: 请手动导出或使用 Edge/Firefox/Zen")
    return False


def main():
    target = sys.argv[1] if len(sys.argv) > 1 else 'auto'

    print("视频字幕工具 - Cookies 导出")
    print("=" * 40)

    if target == 'auto':
        targets = list(DOMAINS.keys())
    elif target in DOMAINS:
        targets = [target]
    elif target == 'all':
        targets = list(DOMAINS.keys())
    else:
        print(f"用法: python setup_cookies.py [auto|bilibili|youtube|all]")
        sys.exit(1)

    results = {}
    for t in targets:
        results[t] = export_domain(t)

    print("\n" + "=" * 40)
    for t, ok in results.items():
        if ok is None:
            print(f"  {t}: 请在管理员窗口中完成")
        elif ok:
            print(f"  {t}: ✅")
        else:
            print(f"  {t}: ❌ 失败")


if __name__ == '__main__':
    main()
