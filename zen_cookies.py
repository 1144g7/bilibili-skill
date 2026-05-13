"""
从 Zen Browser 提取 cookies 并生成 Netscape 格式的 cookies.txt
用法: python zen_cookies.py [域名过滤] [输出文件]
示例: python zen_cookies.py bilibili cookies.txt
"""
import sqlite3
import shutil
import os
import sys
import time
import glob

ZEN_PROFILE_DIR = r"C:\Users\14582\AppData\Roaming\zen\Profiles"

def find_cookie_db():
    """找到 Zen 的 cookies.sqlite（选最大的）"""
    dbs = glob.glob(os.path.join(ZEN_PROFILE_DIR, "*", "cookies.sqlite"))
    if not dbs:
        raise FileNotFoundError("未找到 Zen Browser 的 cookies.sqlite")
    return max(dbs, key=os.path.getsize)

def extract_cookies(domain_filter=None):
    """提取 cookies"""
    db_path = find_cookie_db()
    tmp = os.path.join(os.path.dirname(__file__), "_tmp_cookies.sqlite")
    shutil.copy2(db_path, tmp)  # 复制避免锁文件
    
    try:
        conn = sqlite3.connect(tmp)
        if domain_filter:
            rows = conn.execute(
                "SELECT host, path, isSecure, expiry, name, value "
                "FROM moz_cookies WHERE host LIKE ?",
                (f"%{domain_filter}%",)
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT host, path, isSecure, expiry, name, value "
                "FROM moz_cookies"
            ).fetchall()
        conn.close()
    finally:
        os.remove(tmp)
    
    return rows

def write_netscape_cookies(rows, output_path):
    """写入 Netscape 格式 cookies.txt"""
    with open(output_path, "w", encoding="utf-8") as f:
        f.write("# Netscape HTTP Cookie File\n")
        f.write("# This is a generated file!  Do not edit.\n\n")
        for host, path, secure, expiry, name, value in rows:
            secure_str = "TRUE" if secure else "FALSE"
            expiry_str = str(expiry) if expiry else "0"
            # 判断是否为域级 cookie
            h = host.lstrip(".")
            domain = host
            if domain.startswith("."):
                domain_tail = "TRUE"
            else:
                domain_tail = "FALSE"
            f.write(f"{domain}\t{domain_tail}\t{path}\t{secure_str}\t{expiry_str}\t{name}\t{value}\n")
    
    return len(rows)

def main():
    domain_filter = sys.argv[1] if len(sys.argv) > 1 else None
    output = sys.argv[2] if len(sys.argv) > 2 else "cookies.txt"
    
    print(f"[1/3] 查找 Zen Browser cookies 数据库...")
    db_path = find_cookie_db()
    print(f"  找到: {db_path}")
    
    print(f"[2/3] 提取 cookies{' (过滤: ' + domain_filter + ')' if domain_filter else ''}...")
    rows = extract_cookies(domain_filter)
    print(f"  找到 {len(rows)} 条 cookies")
    
    if not rows:
        print(f"  ⚠️ 没有 cookies！请先在 Zen Browser 中登录 {domain_filter or '目标网站'}")
        sys.exit(1)
    
    print(f"[3/3] 写入 {output}...")
    count = write_netscape_cookies(rows, output)
    print(f"  ✅ 已写入 {count} 条 cookies 到 {output}")
    
    # 显示前几条
    for r in rows[:5]:
        print(f"  {r[0]} | {r[4]}")

if __name__ == "__main__":
    main()
