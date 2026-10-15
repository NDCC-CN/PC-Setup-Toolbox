# -*- coding: utf-8 -*-
"""扫描 packages 目录，计算每个安装包的 SHA-256，生成 src/hashes.py（打包前运行一次）

用法：
    python build_hashes.py

改过 packages 里的安装包（换版本/重下）后，重新跑一次本脚本，再重新打包 exe，
这样 exe 里内置的指纹才会和 packages 里的安装包一致。
"""
import hashlib
import os

HERE = os.path.dirname(os.path.abspath(__file__))
PKG_DIR = os.path.join(HERE, "packages")
OUT = os.path.join(HERE, "src", "hashes.py")


def sha256_file(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def main():
    entries = []
    if os.path.isdir(PKG_DIR):
        for name in sorted(os.listdir(PKG_DIR)):
            full = os.path.join(PKG_DIR, name)
            if os.path.isfile(full):
                entries.append((name, sha256_file(full)))

    lines = [
        "# -*- coding: utf-8 -*-",
        "# 本文件由 build_hashes.py 自动生成，请勿手改。",
        "# 改过 packages 里的安装包后，重新运行 build_hashes.py 再重新打包。",
        "",
        "PACKAGE_HASHES = {",
    ]
    for name, h in entries:
        lines.append('    "{}": "{}",'.format(name, h))
    lines.append("}")
    lines.append("")

    with open(OUT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("已生成 {} （共 {} 个安装包指纹）".format(OUT, len(entries)))


if __name__ == "__main__":
    main()
