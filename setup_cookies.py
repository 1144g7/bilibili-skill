"""
一次性导出浏览器 cookies → cookies.json

支持:
  - edge:   需要管理员权限（弹 UAC 自动提权）
  - firefox: 不需要管理员
  - zen:    不需要管理员（Firefox 内核）

注意: Chrome v130+ App-Bound Encryption 导致第三方无法解密 cookies，
      Chrome 用户请使用 Edge 或安装 Firefox/Zen 登录 bilibili.com

用法:
    python setup_cookies.py            # 自动检测
    python setup_cookies.py edge       # 指定 Edge
    python setup_cookies.py firefox    # 指定 Firefox
    python setup_cookies.py zen        # 指定 Zen Browser
"""
import sys
import os
import json
import glob


def _save_cookies(cookie_dict):
    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cookies.json')
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(cookie_dict, f, ensure_ascii=False, indent=2)
    return out


def _to_dict(cookies_list):
    d = {}
    for c in cookies_list:
        name = c.get('name', '')
        value = c.get('value', '')
        if name and value:
            d[name] = value
    return d


def try_edge():
    """Edge: 需要管理员，弹 UAC"""
    import ctypes
    if not ctypes.windll.shell32.IsUserAnAdmin():
        # 不是管理员，重新以管理员启动自己
        import subprocess
        script = os.path.abspath(__file__)
        subprocess.run(
            ['powershell', '-Command',
             f'Start-Process python -ArgumentList \'{script} edge\' -Verb RunAs'],
            check=True
        )
        return None  # 新窗口处理，这里返回 None

    import rookiepy
    cookies = rookiepy.edge(domains=['bilibili.com'])
    return _to_dict(cookies)


def try_firefox():
    """Firefox: 不需要管理员"""
    import rookiepy
    cookies = rookiepy.firefox(domains=['bilibili.com'])
    return _to_dict(cookies)


def try_zen():
    """Zen Browser (Firefox 内核): 不需要管理员"""
    import rookiepy
    dbs = glob.glob(os.path.expanduser(
        r"~\AppData\Roaming\zen\Profiles\*\cookies.sqlite"
    ))
    if not dbs:
        return {}
    db = max(dbs, key=os.path.getsize)
    cookies = rookiepy.firefox_based(db)
    d = _to_dict(cookies)
    # 只保留 bilibili 相关
    return {k: v for k, v in d.items()} if d.get('SESSDATA') else {}


def auto_detect():
    """按优先级自动检测: Zen → Firefox → Edge"""
    # 1. Firefox 类（不需要管理员，优先尝试）
    for name, fn in [('Zen', try_zen), ('Firefox', try_firefox)]:
        print(f"  尝试 {name}...", end=' ')
        try:
            d = fn()
            if d.get('SESSDATA'):
                print(f"找到 {len(d)} 条 cookies")
                return d
            print("无 B站登录")
        except Exception as e:
            print(f"失败 ({e})")

    # 2. Edge（需要管理员，弹 UAC）
    print("  尝试 Edge（需要管理员权限）...")
    result = try_edge()
    if result is not None and result.get('SESSDATA'):
        return result

    return {}


def main():
    browser = sys.argv[1] if len(sys.argv) > 1 else 'auto'

    print("B站 cookies 导出工具")
    print("=" * 40)

    cookie_dict = {}

    if browser == 'auto':
        cookie_dict = auto_detect()
    elif browser == 'edge':
        result = try_edge()
        if result is not None:
            cookie_dict = result
        else:
            print("已在管理员窗口中运行，请查看弹出的窗口")
            return
    elif browser == 'firefox':
        cookie_dict = try_firefox()
    elif browser == 'zen':
        cookie_dict = try_zen()
    else:
        print(f"不支持: {browser}")
        print("用法: python setup_cookies.py [auto|edge|firefox|zen]")
        return

    if not cookie_dict.get('SESSDATA'):
        print("\n未找到 B站登录信息 (SESSDATA)")
        print("请确保在浏览器中已登录 bilibili.com")
        if browser == 'edge':
            print("提示: Chrome 不支持自动导出，请使用 Edge/Firefox/Zen")
        sys.exit(1)

    out = _save_cookies(cookie_dict)
    print(f"\n导出成功: {len(cookie_dict)} 条 cookies")
    print(f"保存到: {out}")
    print("后续运行 bili.py 将自动使用此文件，无需再次导出")


if __name__ == '__main__':
    main()
