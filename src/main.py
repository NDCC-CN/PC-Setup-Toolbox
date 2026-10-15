# -*- coding: utf-8 -*-
"""
装机助手 —— 主程序

用法：
    双击运行，或命令行执行：python main.py

说明：
    - 纯 Python + 自带 Tkinter，无需安装任何额外库
    - 最终打包成单个 exe 放 U 盘，用户双击即用
"""

import ctypes
import glob
import hashlib
import json
import os
import shutil
import subprocess
import sys
import threading
import urllib.request
import tkinter as tk
import tkinter.font as tkfont
import zipfile
from datetime import datetime, timedelta, timezone
from tkinter import ttk, scrolledtext, messagebox, filedialog

try:
    from hashes import PACKAGE_HASHES
except ImportError:
    PACKAGE_HASHES = {}


# ==================== 配色（深海军蓝 + 琥珀金） ====================

BG = "#0e1a2b"          # 主背景：深海军蓝
BG_CARD = "#152439"     # 卡片/分区背景：稍亮一层
LOG_BG = "#0a1320"      # 日志背景：最深
BORDER = "#23405c"      # 边框
FG = "#d7e2f0"          # 主文字：浅蓝白
FG_DIM = "#829ab8"      # 次要文字
HEADING = "#eef3fb"     # 顶部大标题：近白
ACCENT = "#8fb7e8"      # 分区名/日志标题：冰蓝
BTN = "#d99a3d"         # 按钮：琥珀金（整套唯一暖色）
BTN_HOVER = "#e8ad52"
BTN_FG = "#26180a"      # 按钮文字：深棕
OK = "#4fd6a8"          # 成功：薄荷绿
ERR = "#ff8080"         # 失败：珊瑚红


# ==================== 通用工具 ====================

def is_admin():
    """当前是否以管理员权限运行"""
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def run_powershell(script):
    """执行 PowerShell 脚本，返回 (输出文本, 返回码)"""
    try:
        proc = subprocess.run(
            ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", script],
            capture_output=True, text=True, encoding="gbk", errors="replace", timeout=60,
        )
        return (proc.stdout + proc.stderr).strip(), proc.returncode
    except Exception as e:
        return "执行出错：{}".format(e), -1


def run_cmd(args):
    """执行一条命令，返回 (输出文本, 返回码)；命令不存在返回码 127"""
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, encoding="gbk", errors="replace", timeout=60,
        )
        return (proc.stdout + proc.stderr).strip(), proc.returncode
    except FileNotFoundError:
        return "", 127
    except Exception as e:
        return "执行出错：{}".format(e), -1


def enable_dark_titlebar(root):
    """把 Windows 窗口标题栏设成深色模式"""
    try:
        root.update_idletasks()
        hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
        if not hwnd:
            hwnd = root.winfo_id()
        DWMWA_USE_IMMERSIVE_DARK_MODE = 20
        val = ctypes.c_int(1)
        ctypes.windll.dwmapi.DwmSetWindowAttribute(
            hwnd, DWMWA_USE_IMMERSIVE_DARK_MODE, ctypes.byref(val), ctypes.sizeof(val))
    except Exception:
        pass


# ==================== 检测功能 ====================

def _exe_path(cmd):
    """返回命令在 PATH 里的完整路径（找不到返回空串），日志里告诉用户「装到哪」用"""
    try:
        p = shutil.which(cmd)
        return p if p else ""
    except Exception:
        return ""


def detect_python():
    out, code = run_cmd(["python", "--version"])
    if code == 0 and out:
        return "√ Python 已安装：{}（{}）".format(out, _exe_path("python"))
    out, code = run_cmd(["py", "--version"])
    if code == 0 and out:
        return "√ Python 已安装：{}（{}）".format(out, _exe_path("py"))
    # PATH 未刷新（刚装完），用绝对路径兜底
    for exe in glob.glob(r"C:\Program Files\Python*\python.exe"):
        # 卸载残留的 python.exe 可能缺核心 DLL（python3xx.dll），运行会弹「找不到 DLL」系统错误框，跳过
        if not glob.glob(os.path.join(os.path.dirname(exe), "python3*.dll")):
            continue
        out, code = run_cmd([exe, "--version"])
        if code == 0 and out:
            return "√ Python 已安装：{}（{}）".format(out, exe)
    return "× Python 未检测到"


def detect_gcc():
    out, code = run_cmd(["gcc", "--version"])
    if code == 0 and out:
        first = out.splitlines()[0] if out.splitlines() else out
        return "√ C 编译器 gcc 已安装：{}（{}）".format(first, _exe_path("gcc"))
    # PATH 未刷新，用绝对路径兜底
    for cand in (os.path.join(devtools_dir(), "mingw", "mingw64", "bin", "gcc.exe"),
                 os.path.join(devtools_dir(), "mingw", "bin", "gcc.exe")):
        if os.path.exists(cand):
            out, code = run_cmd([cand, "--version"])
            if code == 0 and out:
                first = out.splitlines()[0] if out.splitlines() else out
                return "√ C 编译器 gcc 已安装：{}（{}）".format(first, cand)
    return "× C 编译器 gcc 未检测到"


def detect_node():
    out, code = run_cmd(["node", "--version"])
    if code == 0 and out:
        return "√ Node.js 已安装：{}（{}）".format(out, _exe_path("node"))
    node = r"C:\Program Files\nodejs\node.exe"
    if os.path.exists(node):
        out, code = run_cmd([node, "--version"])
        if code == 0 and out:
            return "√ Node.js 已安装：{}（{}）".format(out, node)
    return "× Node.js 未检测到"


def detect_git():
    out, code = run_cmd(["git", "--version"])
    if code == 0 and out:
        return "√ Git 已安装：{}（{}）".format(out, _exe_path("git"))
    git = r"C:\Program Files\Git\cmd\git.exe"
    if os.path.exists(git):
        out, code = run_cmd([git, "--version"])
        if code == 0 and out:
            return "√ Git 已安装：{}（{}）".format(out, git)
    return "× Git 未检测到"


def detect_java():
    out, code = run_cmd(["java", "-version"])
    if code == 0 and out:
        first = out.splitlines()[0] if out.splitlines() else out
        return "√ Java 已安装：{}（{}）".format(first, _exe_path("java"))
    # PATH 未刷新，用绝对路径兜底（我们装在 DevTools\jdk\<版本>\bin）
    for cand in glob.glob(os.path.join(devtools_dir(), "jdk", "*", "bin", "java.exe")):
        out, code = run_cmd([cand, "-version"])
        if code == 0 and out:
            first = out.splitlines()[0] if out.splitlines() else out
            return "√ Java 已安装：{}（{}）".format(first, cand)
    return "× Java 未检测到"


def detect_vscode():
    """检测 VS Code（System Installer 装到 Program Files；也兜底 User 版装到 LOCALAPPDATA）"""
    for exe in (r"C:\Program Files\Microsoft VS Code\Code.exe",
                os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe")):
        if os.path.exists(exe):
            out, code = run_cmd([exe, "--version"])
            if code == 0 and out:
                first = out.splitlines()[0] if out.splitlines() else out
                return "√ VS Code 已安装：{}（{}）".format(first, exe)
    return "× VS Code 未检测到"


def detect_windows():
    """读注册表拿系统名称。Win11 的 ProductName 仍写 Windows 10，需按 build 号修正。"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        try:
            name, _ = winreg.QueryValueEx(key, "ProductName")
            build, _ = winreg.QueryValueEx(key, "CurrentBuildNumber")
        finally:
            winreg.CloseKey(key)
        if name:
            name = str(name)
            try:
                if int(build) >= 22000 and name.startswith("Windows 10"):
                    name = "Windows 11" + name[len("Windows 10"):]
            except (ValueError, TypeError):
                pass
            return "√ 系统：{}".format(name)
    except Exception:
        pass
    # 兜底：platform 拿个大致版本号
    try:
        import platform
        return "√ 系统：Windows {}".format(platform.release())
    except Exception:
        pass
    return "× 系统：检测失败"


def _service_dll():
    """读 TermService 的 ServiceDll 值（判断 RDPWrap 是否已 hook），读不到返回 None"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SYSTEM\CurrentControlSet\Services\TermService\Parameters")
        try:
            val, _ = winreg.QueryValueEx(key, "ServiceDll")
            return val
        except OSError:
            return None
        finally:
            winreg.CloseKey(key)
    except Exception:
        return None


def detect_remote():
    """检测远程桌面是否可用：系统开关 + 3389 监听 + RDPWrap hook"""
    lines = []
    # 1) 系统开关 fDenyTSConnections（0=允许远程连接，1=拒绝）
    deny = None
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SYSTEM\CurrentControlSet\Control\Terminal Server")
        try:
            deny, _ = winreg.QueryValueEx(key, "fDenyTSConnections")
        except OSError:
            pass
        winreg.CloseKey(key)
    except Exception:
        pass
    if deny == 0:
        lines.append("√ 远程桌面：系统开关已开启（允许远程连接）")
    elif deny == 1:
        lines.append("× 远程桌面：系统开关已关闭（拒绝远程连接）")
    else:
        lines.append("- 远程桌面：系统开关读取失败")
    # 2) 3389 是否监听
    out, code = run_cmd(["netstat", "-ano"])
    listening = any(":3389" in ln and "LISTENING" in ln for ln in out.splitlines())
    lines.append("√ 远程端口 3389：正在监听" if listening else "× 远程端口 3389：未监听")
    # 3) RDPWrap hook 是否已装（ServiceDll 指向 rdpwrap.dll）
    sdll = _service_dll()
    if sdll and "rdpwrap" in str(sdll).lower():
        lines.append("√ RDPWrap：已 hook（ServiceDll 指向 rdpwrap.dll）")
    else:
        lines.append("- RDPWrap：未 hook（家庭版需点「一键配置远程桌面」启用）")
    return "\n".join(lines)


def detect_windows_update():
    """检测 Windows 更新当前状态（是否暂停/禁用自动更新）"""
    try:
        import winreg
        # 1) 是否暂停（Win10/11「暂停更新」开关）
        try:
            key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                 r"SOFTWARE\Microsoft\WindowsUpdate\UX\Settings")
            try:
                expiry, _ = winreg.QueryValueEx(key, "PauseUpdatesExpiryTime")
            except OSError:
                expiry = None
            winreg.CloseKey(key)
        except OSError:
            expiry = None
        if expiry:
            return "√ Windows 更新：已暂停（到 {}）".format(expiry)
        # 2) 是否禁用自动更新（组策略）
        try:
            key2 = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                  r"SOFTWARE\Policies\Microsoft\Windows\WindowsUpdate\AU")
            try:
                noauto, _ = winreg.QueryValueEx(key2, "NoAutoUpdate")
            except OSError:
                noauto = None
            winreg.CloseKey(key2)
        except OSError:
            noauto = None
        if noauto == 1:
            return "√ Windows 更新：已禁用自动更新（组策略）"
        return "√ Windows 更新：正常（自动更新开启中）"
    except Exception:
        return "√ Windows 更新：正常（未检测到暂停/禁用）"


def detect_edge_update():
    """检测 Edge 自动更新是否被锁定（对应「停止 Edge 更新」功能）"""
    try:
        import winreg
        for root, path in ((winreg.HKEY_LOCAL_MACHINE,
                            r"SOFTWARE\Policies\Microsoft\EdgeUpdate"),
                           (winreg.HKEY_CURRENT_USER,
                            r"SOFTWARE\Policies\Microsoft\EdgeUpdate")):
            try:
                key = winreg.OpenKey(root, path)
            except OSError:
                continue
            try:
                val, _ = winreg.QueryValueEx(key, "UpdateDefault")
            except OSError:
                val = None
            winreg.CloseKey(key)
            if val is not None:
                if val == 0:
                    return "√ Edge：已停止自动更新（策略锁定）"
                return "√ Edge：自动更新开启（未锁定）"
        return "√ Edge：自动更新开启（未锁定）"
    except Exception:
        return "√ Edge：自动更新开启（未锁定）"


def _termsrv_version():
    """读本机 termsrv.dll 文件版本（如 10.0.22621.4745），失败返回空串"""
    ps = '(Get-Item "$env:SystemRoot\\System32\\termsrv.dll").VersionInfo.FileVersion'
    out, code = run_powershell(ps)
    if code == 0 and out:
        return out.split(" ")[0].strip()
    return ""


def configure_remote():
    """一键配置远程桌面（RDPWrap，纯离线）：读版本→查内置表→装 dll/ini→改注册表→重启服务→验证"""
    if not is_admin():
        return "× 需要管理员权限，请点右上角的「以管理员身份重启」"
    # 已配置则直接返回（避免覆盖正被 TermService 加载占用的 rdpwrap.dll）
    sdll = _service_dll()
    if sdll and "rdpwrap" in str(sdll).lower():
        return "√ 检测到本机已启用远程桌面（RDPWrap 已 hook），无需重复配置。\n{}".format(detect_remote())
    ver = _termsrv_version()
    if not ver:
        return "× 无法读取 termsrv.dll 版本，无法判断是否支持。"
    dll = _resource_path("rdpwrap/rdpwrap.dll")
    ini = _resource_path("rdpwrap/rdpwrap.ini")
    if not os.path.exists(dll) or not os.path.exists(ini):
        return "× 内置的 RDPWrap 文件缺失，无法配置。"
    try:
        with open(ini, "r", encoding="utf-8", errors="replace") as f:
            ini_text = f.read()
    except Exception as e:
        return "× 读取内置 rdpwrap.ini 失败：{}".format(e)
    if "[{}]".format(ver) not in ini_text:
        return (
            "× 本机系统版本 {} 太新，RDPWrap 尚未收录，无法一键配置。\n"
            "（可联网后运行 E:\\RDPWrap-远程桌面\\pdb_autogen.py 生成该版本 offset，再补进表）".format(ver)
        )
    # 复制 dll + ini 到 RDP Wrapper 目录
    dest = r"C:\Program Files\RDP Wrapper"
    try:
        if not os.path.isdir(dest):
            os.makedirs(dest)
        shutil.copy2(dll, os.path.join(dest, "rdpwrap.dll"))
        shutil.copy2(ini, os.path.join(dest, "rdpwrap.ini"))
    except Exception as e:
        return "× 复制 RDPWrap 文件失败：{}".format(e)
    # 改注册表 ServiceDll（原值备份到 ServiceDllBackup），再重启 TermService
    ps = r'''
$ErrorActionPreference = 'Stop'
$p = 'HKLM:\SYSTEM\CurrentControlSet\Services\TermService\Parameters'
$old = (Get-ItemProperty -Path $p -Name 'ServiceDll').ServiceDll
Set-ItemProperty -Path $p -Name 'ServiceDllBackup' -Value $old
Set-ItemProperty -Path $p -Name 'ServiceDll' -Value 'C:\Program Files\RDP Wrapper\rdpwrap.dll'
Restart-Service TermService -Force
Start-Sleep 2
Write-Output 'OK'
'''
    out, code = run_powershell(ps)
    if code != 0:
        return "× 配置失败：\n{}".format(out)
    return "√ 远程桌面已配置完成（RDPWrap，版本 {}）。\n{}".format(ver, detect_remote())


# ==================== 硬件检测 ====================

def _cpu_name():
    """读注册表拿 CPU 名称（Win7~Win11 通用，不依赖 PowerShell）"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"HARDWARE\DESCRIPTION\System\CentralProcessor\0")
        try:
            name, _ = winreg.QueryValueEx(key, "ProcessorNameString")
        finally:
            winreg.CloseKey(key)
        if name:
            return name.strip()
    except Exception:
        pass
    return ""


_VIDEO_CLASS = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"


def _list_gpus_reg():
    """注册表枚举显示适配器（DriverDesc），返回 [dict]，只有 name，无分辨率信息"""
    import winreg
    gpus = []
    try:
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, _VIDEO_CLASS)
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(key, i)
            except OSError:
                break
            i += 1
            if not sub.isdigit():
                continue
            try:
                sk = winreg.OpenKey(key, sub)
                try:
                    desc, _ = winreg.QueryValueEx(sk, "DriverDesc")
                except OSError:
                    desc = ""
                finally:
                    winreg.CloseKey(sk)
                if desc:
                    gpus.append({"name": desc, "compat": "",
                                 "hres": "", "vres": "", "refresh": ""})
            except OSError:
                continue
        winreg.CloseKey(key)
    except OSError:
        pass
    # 去重（同一块卡可能在注册表出现多次）
    seen, uniq = set(), []
    for g in gpus:
        if g["name"] not in seen:
            seen.add(g["name"])
            uniq.append(g)
    return uniq


def _list_gpus():
    """列出所有显卡：优先 WMI（含分辨率/刷新率），失败则读注册表（只有型号）"""
    ps = (
        'Get-WmiObject Win32_VideoController | ForEach-Object { '
        '"{0}`t{1}`t{2}`t{3}`t{4}`t{5}" -f '
        '$_.Name, $_.AdapterCompatibility, [int64]$_.AdapterRAM, '
        '$_.CurrentHorizontalResolution, $_.CurrentVerticalResolution, $_.CurrentRefreshRate }'
    )
    out, code = run_powershell(ps)
    gpus = []
    if code == 0 and out:
        for line in out.splitlines():
            parts = line.split("\t")
            if len(parts) < 6:
                continue
            gpus.append({
                "name": parts[0].strip(),
                "compat": parts[1].strip(),
                "ram": parts[2].strip(),
                "hres": parts[3].strip(),
                "vres": parts[4].strip(),
                "refresh": parts[5].strip(),
            })
    if gpus:
        return gpus
    return _list_gpus_reg()


def _is_dgpu(name, compat):
    """启发式判断某张卡是不是独立显卡（Intel 一律算核显）"""
    import re
    s = "{} {}".format(name, compat).lower()
    if "nvidia" in s or "geforce" in s:
        return True
    if "radeon" in s or "amd" in s:
        # AMD 独显名带 "RX + 数字"（如 RX 6600）；核显是 "Radeon Graphics"/"Vega"
        if re.search(r"rx\s*\d{3,4}", s):
            return True
        if "radeon pro" in s or "firepro" in s:
            return True
        return False
    return False


def _res_active(g):
    """该显卡当前是否在往屏幕输出画面（分辨率 > 0）"""
    try:
        return int(g["hres"]) > 0
    except (ValueError, TypeError):
        return False


def _fmt_res(g):
    """分辨率 + 刷新率文本，如 1920x1080 @ 144Hz"""
    try:
        h, v = int(g["hres"]), int(g["vres"])
        if h <= 0 or v <= 0:
            return ""
        txt = "{}×{}".format(h, v)
        try:
            r = int(g["refresh"])
            if r > 0:
                txt += " @ {}Hz".format(r)
        except (ValueError, TypeError):
            pass
        return txt
    except (ValueError, TypeError):
        return ""


# ---- 色域检测（读显示器 EDID，算 sRGB/NTSC/DCI-P3 覆盖率）----

_SRGB = [(0.640, 0.330), (0.300, 0.600), (0.150, 0.060)]
_NTSC = [(0.670, 0.330), (0.210, 0.710), (0.140, 0.080)]
_DCIP3 = [(0.680, 0.320), (0.265, 0.690), (0.150, 0.060)]


def _polygon_area(points):
    """鞋带公式求多边形面积（顶点顺序无关）"""
    n = len(points)
    if n < 3:
        return 0.0
    s = 0.0
    for i in range(n):
        x1, y1 = points[i]
        x2, y2 = points[(i + 1) % n]
        s += x1 * y2 - x2 * y1
    return abs(s) / 2.0


def _cross(o, a, b):
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _ensure_ccw(points):
    if _cross(points[0], points[1], points[2]) < 0:
        return list(reversed(points))
    return list(points)


def _clip(poly, a, b):
    """用边 a->b（裁剪多边形逆时针）裁剪 poly，保留左侧"""
    out = []
    n = len(poly)
    if n == 0:
        return out
    for i in range(n):
        cur = poly[i]
        nxt = poly[(i + 1) % n]
        cur_in = _cross(a, b, cur) >= 0
        nxt_in = _cross(a, b, nxt) >= 0
        if cur_in:
            out.append(cur)
        if cur_in != nxt_in:
            dx = nxt[0] - cur[0]
            dy = nxt[1] - cur[1]
            ex = b[0] - a[0]
            ey = b[1] - a[1]
            denom = dx * ey - dy * ex
            if abs(denom) > 1e-12:
                t = ((a[0] - cur[0]) * ey - (a[1] - cur[1]) * ex) / denom
                out.append((cur[0] + t * dx, cur[1] + t * dy))
    return out


def _intersect_polygons(poly_a, poly_b):
    result = _ensure_ccw(poly_a)
    b = _ensure_ccw(poly_b)
    for i in range(len(b)):
        result = _clip(result, b[i], b[(i + 1) % len(b)])
        if not result:
            break
    return result


def _gamut_coverage(src, target):
    """源 RGB 三角形与目标三角形交集面积 / 目标三角形面积"""
    inter = _intersect_polygons(src, target)
    if not inter:
        return 0.0
    ta = _polygon_area(target)
    if ta <= 0:
        return 0.0
    return _polygon_area(inter) / ta


def _read_edid():
    """从注册表枚举显示器 EDID，返回第一个有效 EDID（bytes）"""
    import winreg
    found = None
    try:
        disp = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                              r"SYSTEM\CurrentControlSet\Enum\DISPLAY")
    except OSError:
        return None
    i = 0
    while found is None:
        try:
            monitor = winreg.EnumKey(disp, i)
        except OSError:
            break
        i += 1
        try:
            mkey = winreg.OpenKey(disp, monitor)
        except OSError:
            continue
        j = 0
        try:
            while found is None:
                try:
                    inst = winreg.EnumKey(mkey, j)
                except OSError:
                    break
                j += 1
                try:
                    ikey = winreg.OpenKey(mkey, inst)
                except OSError:
                    continue
                try:
                    try:
                        dk = winreg.OpenKey(ikey, "Device Parameters")
                    except OSError:
                        winreg.CloseKey(ikey)
                        continue
                    try:
                        edid, _ = winreg.QueryValueEx(dk, "EDID")
                        if edid and len(edid) >= 128:
                            found = bytes(edid)
                    except OSError:
                        pass
                    finally:
                        winreg.CloseKey(dk)
                finally:
                    winreg.CloseKey(ikey)
        finally:
            winreg.CloseKey(mkey)
    winreg.CloseKey(disp)
    return found


def _parse_edid(edid):
    """解析 EDID：屏幕尺寸（英寸）、面板厂商、RGB 色度坐标"""
    info = {}
    h_cm = edid[21]
    v_cm = edid[22]
    if h_cm and v_cm:
        info["size_inch"] = round(((h_cm * h_cm + v_cm * v_cm) ** 0.5) / 2.54, 1)

    def _letter(v):
        return chr(ord('A') + v - 1) if 1 <= v <= 26 else '?'

    m1 = (edid[8] >> 2) & 0x1F
    m2 = ((edid[8] & 0x03) << 3) | (edid[9] >> 5)
    m3 = edid[9] & 0x1F
    info["mfg"] = _letter(m1) + _letter(m2) + _letter(m3)

    def _coord(msb, lsb):
        return ((msb << 2) | lsb) / 1024.0

    info["rgb"] = {
        "R": (_coord(edid[27], (edid[25] >> 6) & 3), _coord(edid[28], (edid[25] >> 4) & 3)),
        "G": (_coord(edid[29], (edid[25] >> 2) & 3), _coord(edid[30], edid[25] & 3)),
        "B": (_coord(edid[31], (edid[26] >> 6) & 3), _coord(edid[32], (edid[26] >> 4) & 3)),
    }

    # 首选（原生）分辨率：第一个 DTD（offset 54~71）
    try:
        h = edid[56] | ((edid[58] >> 4) << 8)
        v = edid[59] | ((edid[61] >> 4) << 8)
        if 0 < h < 10000 and 0 < v < 10000:
            info["native"] = (h, v)
    except IndexError:
        pass
    return info


def _detect_screen():
    """检测屏幕 EDID，返回 dict（size/mfg/s/n/p）或 None（无 EDID / 数据无效）"""
    edid = _read_edid()
    if not edid:
        return None
    info = _parse_edid(edid)
    rgb = info.get("rgb")
    if not rgb:
        return None
    src = [rgb["R"], rgb["G"], rgb["B"]]
    # 色度坐标无效（三点几乎共线/重合）则视为无数据
    if _polygon_area(src) < 1e-4:
        return None
    return {
        "size": info.get("size_inch"),
        "mfg": info.get("mfg", "").strip("?"),
        "native": info.get("native"),
        "s": _gamut_coverage(src, _SRGB),
        "n": _gamut_coverage(src, _NTSC),
        "p": _gamut_coverage(src, _DCIP3),
    }


def detect_hardware():
    """检测 CPU / 显卡 / 屏幕，并推断独显直连 / 混合模式 / 只核显。

    每一项检测无论成功与否都输出一行：成功用 √，没检测到用 -（并说明原因），
    避免静默跳过，让用户明确知道哪一项没数据。
    """
    lines = []

    # CPU
    cpu = _cpu_name()
    lines.append("√ CPU：{}".format(cpu) if cpu else "× CPU：检测失败")

    # 显卡列表
    gpus = _list_gpus()
    dgpus = [g for g in gpus if _is_dgpu(g["name"], g["compat"])]
    igpus = [g for g in gpus if not _is_dgpu(g["name"], g["compat"])]

    if gpus:
        if igpus:
            for g in igpus:
                lines.append("√ 核显：{}".format(g["name"]))
        else:
            lines.append("- 核显：未检测到（独显直连会禁用核显，属正常）")
        if dgpus:
            for g in dgpus:
                lines.append("√ 独显：{}".format(g["name"]))
        else:
            lines.append("- 独显：未检测到（本机可能只有核显，无独立显卡）")
    else:
        lines.append("× 显卡：检测失败")

    # 分辨率（WMI；Win7 上 WMI 不可用会拿不到）
    if gpus:
        active = [g for g in gpus if _res_active(g)]
        if active:
            res = _fmt_res(active[0])
            if res:
                src = "独显" if _is_dgpu(active[0]["name"], active[0]["compat"]) else "核显"
                lines.append("√ 分辨率：{}（{}输出）".format(res, src))
            else:
                lines.append("- 分辨率：未检测到（WMI 不可用）")
        else:
            lines.append("- 分辨率：未检测到（WMI 不可用）")
    else:
        lines.append("- 分辨率：未检测到（WMI 不可用）")

    # 屏幕尺寸/厂商 + 色域（EDID 注册表）
    scr = _detect_screen()
    if scr:
        if scr.get("size"):
            desc = "{} 英寸".format(scr["size"])
            if scr.get("mfg"):
                desc += "（{} 面板）".format(scr["mfg"])
            lines.append("√ 屏幕：{}".format(desc))
        high = scr["s"] >= 0.95 or scr["p"] >= 0.90
        lines.append("√ 色域：sRGB {:.0%} / NTSC {:.0%} / DCI-P3 {:.0%}（{}）".format(
            scr["s"], scr["n"], scr["p"], "高色域" if high else "低色域"))
    else:
        lines.append("- 屏幕/色域：未检测到（无 EDID 数据）")

    # 显卡模式
    if not gpus:
        lines.append("× 显卡模式：未检测到（显卡检测失败）")
    elif not dgpus:
        lines.append("√ 显卡模式：只使用核显（本机未检测到独立显卡）")
    elif not igpus:
        lines.append("√ 显卡模式：独显直连（本机无核显，或核显已被禁用）")
    else:
        has_res = any(_res_active(g) for g in gpus)
        if not has_res:
            lines.append("√ 显卡模式：检测到核显 + 独显，但无法判断直连/混合（缺少分辨率信息）")
        elif any(_res_active(g) for g in dgpus):
            lines.append("√ 显卡模式：独显直连（独显正在输出画面）")
        else:
            lines.append("√ 显卡模式：混合模式（核显输出画面，独显待命 = Optimus 混合输出）")

    return "\n".join(lines)


# ==================== 问题诊断 ====================

# 设备管理器错误码常见含义（ConfigManagerErrorCode）
_ERR_CODE_MEANING = {
    1: "设备配置不正确",
    3: "驱动损坏",
    10: "设备无法启动",
    12: "资源冲突",
    14: "需重启生效",
    18: "需重新安装驱动",
    22: "设备被禁用",
    24: "设备不存在",
    28: "驱动未安装",
    31: "驱动加载失败",
    32: "驱动被禁用",
    43: "设备报告问题（常见于显卡驱动异常）",
}


def _gpu_status():
    """查显卡在设备管理器里的错误码，返回 [{name, code}]；WMI 不可用返回空列表"""
    ps = (
        'Get-WmiObject Win32_VideoController | ForEach-Object { '
        '"{0}`t{1}" -f $_.Name, $_.ConfigManagerErrorCode }'
    )
    out, code = run_powershell(ps)
    result = []
    if code != 0 or not out:
        return result
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        try:
            err = int(parts[1].strip())
        except (ValueError, TypeError):
            err = -1
        result.append({"name": parts[0].strip(), "code": err})
    return result


def _bad_devices():
    """查设备管理器里所有报错（感叹号）的设备，返回 [(name, code)]"""
    ps = (
        'Get-WmiObject Win32_PnPEntity | '
        'Where-Object { $_.ConfigManagerErrorCode -ne 0 } | '
        'ForEach-Object { "{0}`t{1}" -f $_.Name, $_.ConfigManagerErrorCode }'
    )
    out, code = run_powershell(ps)
    bads = []
    if code != 0 or not out:
        return bads
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 2:
            continue
        name = parts[0].strip()
        try:
            err = int(parts[1].strip())
        except (ValueError, TypeError):
            continue
        if name:
            bads.append((name, err))
    return bads


def _computer_info():
    """查物理内存总量 + 系统位数，返回 dict 或 None（WMI 不可用）"""
    ps = (
        'Get-WmiObject Win32_ComputerSystem | ForEach-Object { '
        '"{0}`t{1}" -f $_.TotalPhysicalMemory, $_.SystemType }'
    )
    out, code = run_powershell(ps)
    if code != 0 or not out:
        return None
    parts = out.splitlines()[0].split("\t")
    if len(parts) < 2:
        return None
    try:
        total = int(parts[0].strip())
    except (ValueError, TypeError):
        total = 0
    return {"total_bytes": total, "system_type": parts[1].strip()}


def _disks_status():
    """查硬盘 SMART 状态，返回 [{model, status, predict}]；WMI 不可用返回空列表"""
    ps = (
        'Get-WmiObject Win32_DiskDrive | ForEach-Object { '
        '"{0}`t{1}`t{2}" -f $_.Model, $_.Status, $_.PredictFailure }'
    )
    out, code = run_powershell(ps)
    disks = []
    if code != 0 or not out:
        return disks
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) < 3:
            continue
        disks.append({
            "model": parts[0].strip(),
            "status": parts[1].strip(),
            "predict": parts[2].strip(),
        })
    return disks


def _conclusion(issues):
    """根据问题列表生成一行结论（供三个分类诊断各自用）"""
    if issues:
        return "× 发现 {} 个问题：{}".format(len(issues), "；".join(issues))
    return "√ 未发现问题"


def _diagnose_gpu_screen():
    """单独检测显卡 & 屏幕，返回 (文本, 问题列表)"""
    lines = ["—— 显卡 & 屏幕 ——"]
    issues = []

    gpus = _list_gpus()

    # 显卡驱动是否报错
    statuses = _gpu_status()
    if statuses:
        bad_gpus = [s for s in statuses if s["code"] not in (0, -1)]
        if bad_gpus:
            for s in bad_gpus:
                meaning = _ERR_CODE_MEANING.get(s["code"], "错误码 {}".format(s["code"]))
                lines.append("× 显卡驱动异常：{}（{}）".format(s["name"], meaning))
                issues.append("显卡驱动异常：{}".format(s["name"]))
        else:
            lines.append("√ 显卡驱动：正常（无报错）")
    else:
        lines.append("- 显卡驱动状态：未检测到（WMI 不可用）")

    # 屏幕 EDID（有 EDID 才能拿到原生分辨率）
    scr = _detect_screen()
    native = scr.get("native") if scr else None
    if scr is None:
        lines.append("× 屏幕 EDID：缺失（读不到显示器信息）")
        issues.append("显示器 EDID 缺失")
    else:
        desc = "√ 屏幕 EDID：正常"
        if scr.get("size"):
            desc += "（{} 英寸".format(scr["size"])
            if scr.get("mfg"):
                desc += "，{} 面板".format(scr["mfg"])
            desc += "）"
        lines.append(desc)

    # 当前分辨率
    active = [g for g in gpus if _res_active(g)] if gpus else []
    cur_wh = None
    if active:
        try:
            cur_wh = (int(active[0]["hres"]), int(active[0]["vres"]))
        except (ValueError, TypeError):
            cur_wh = None

    # 分辨率是否异常（当前明显低于屏幕原生 → 显卡驱动没装好）
    if cur_wh is None:
        lines.append("- 当前分辨率：未检测到（WMI 不可用）")
    elif native and cur_wh[0] * cur_wh[1] < native[0] * native[1] * 0.55:
        lines.append("× 分辨率异常：屏幕原生 {}×{}，当前仅 {}×{}（显卡驱动很可能没装好，在用标准 VGA 驱动）".format(
            native[0], native[1], cur_wh[0], cur_wh[1]))
        issues.append("分辨率异常（原生 {}×{}，当前 {}×{}）".format(native[0], native[1], cur_wh[0], cur_wh[1]))
    elif native:
        lines.append("√ 分辨率：{}×{}（屏幕原生 {}×{}，正常）".format(cur_wh[0], cur_wh[1], native[0], native[1]))
    else:
        lines.append("√ 分辨率：{}×{}".format(cur_wh[0], cur_wh[1]))

    lines.append(_conclusion(issues))
    return "\n".join(lines), issues


def _diagnose_devices():
    """单独检测设备驱动，返回 (文本, 问题列表)"""
    lines = ["—— 设备驱动 ——"]
    issues = []

    bads = _bad_devices()
    if bads:
        for name, err in bads[:5]:
            meaning = _ERR_CODE_MEANING.get(err, "错误码 {}".format(err))
            lines.append("× {}（{}）".format(name, meaning))
        if len(bads) > 5:
            lines.append("… 另有 {} 个设备报错，未全部列出".format(len(bads) - 5))
        issues.append("设备管理器里有 {} 个设备报错（如显卡、网卡、声卡等）".format(len(bads)))
    else:
        lines.append("√ 设备驱动：正常（无报错设备）")

    lines.append(_conclusion(issues))
    return "\n".join(lines), issues


def _diagnose_memory_disk():
    """单独检测内存 & 硬盘，返回 (文本, 问题列表)"""
    lines = ["—— 内存 & 硬盘 ——"]
    issues = []

    info = _computer_info()
    if info:
        total_gb = info["total_bytes"] / (1024 ** 3)
        arch = "x86" if "x86" in info["system_type"].lower() else "x64"
        if arch == "x86" and total_gb >= 4:
            lines.append("× 内存浪费：本机是 32 位系统，插了 {:.1f}GB 内存，但 32 位最多只能用到约 3.25GB（浪费约 {:.1f}GB），建议装 64 位系统".format(
                total_gb, total_gb - 3.25))
            issues.append("32 位系统认不全内存（插了 {:.1f}GB）".format(total_gb))
        else:
            lines.append("√ 内存：{:.1f}GB（{}）".format(
                total_gb, "32 位系统，未超上限" if arch == "x86" else "64 位系统"))
    else:
        lines.append("- 内存：未检测到（WMI 不可用）")

    disks = _disks_status()
    if disks:
        bad_disks = [d for d in disks if d["status"] == "Pred Fail" or d["predict"] == "True"]
        if bad_disks:
            for d in bad_disks:
                lines.append("× 硬盘故障预警：{}（SMART 报告预测性故障，请尽快备份数据并更换）".format(d["model"]))
                issues.append("硬盘 {} 故障预警".format(d["model"]))
        else:
            lines.append("√ 硬盘：{} 块，健康正常".format(len(disks)))
    else:
        lines.append("- 硬盘健康：未检测到（WMI 不可用）")

    lines.append(_conclusion(issues))
    return "\n".join(lines), issues


def diagnose_gpu_screen():
    """检测显卡 & 屏幕（按钮用，返回文本）"""
    return _diagnose_gpu_screen()[0]


def diagnose_devices():
    """检测设备驱动（按钮用，返回文本）"""
    return _diagnose_devices()[0]


def diagnose_memory_disk():
    """检测内存 & 硬盘（按钮用，返回文本）"""
    return _diagnose_memory_disk()[0]


def diagnose():
    """一键诊断：显卡&屏幕、设备驱动、内存&硬盘 全查一遍，结尾汇总问题总数。

    正常用 √、有问题用 ×、检测不到用 -，让机房老师/运维一眼看出这台机子哪里有问题。
    """
    all_issues = []
    parts = []
    for fn in (_diagnose_gpu_screen, _diagnose_devices, _diagnose_memory_disk):
        text, issues = fn()
        parts.append(text)
        all_issues.extend(issues)

    lines = []
    for text in parts:
        lines.append(text)
        lines.append("")  # 各分类之间空一行

    # ---- 总结论 ----
    lines.append("—— 总结论 ——")
    if all_issues:
        lines.append("× 共发现 {} 个问题：".format(len(all_issues)))
        for it in all_issues:
            lines.append("  · {}".format(it))
    else:
        lines.append("√ 未发现明显问题（已检测显卡/屏幕、设备驱动、内存/硬盘）")

    return "\n".join(lines)


# ==================== 系统优化 ====================

def pause_windows_update(days):
    """暂停 Windows 更新到指定天数后（改注册表）"""
    if not is_admin():
        return "× 需要管理员权限，请点右上角的「以管理员身份重启」"
    expiry = (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")
    ps = (
        '$p = "HKLM:\\SOFTWARE\\Microsoft\\WindowsUpdate\\UX\\Settings"; '
        '$e = "{expiry}"; '
        '$n = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ"); '
        'Set-ItemProperty -Path $p -Name "PauseUpdatesExpiryTime" -Value $e; '
        'Set-ItemProperty -Path $p -Name "PauseFeatureUpdatesExpiryTime" -Value $e; '
        'Set-ItemProperty -Path $p -Name "PauseQualityUpdatesExpiryTime" -Value $e; '
        'Set-ItemProperty -Path $p -Name "PauseUpdatesStartTime" -Value $n; '
        'Write-Output "OK"'
    ).format(expiry=expiry)
    out, code = run_powershell(ps)
    if code == 0:
        return "√ Windows 更新已暂停（{} 天）".format(days)
    return "× 操作失败：\n{}".format(out)


def resume_windows_update():
    """恢复 Windows 更新（需管理员）"""
    if not is_admin():
        return "× 需要管理员权限，请点右上角的「以管理员身份重启」"
    ps = (
        '$p = "HKLM:\\SOFTWARE\\Microsoft\\WindowsUpdate\\UX\\Settings"; '
        'Remove-ItemProperty -Path $p -Name "PauseUpdatesExpiryTime" -ErrorAction SilentlyContinue; '
        'Remove-ItemProperty -Path $p -Name "PauseFeatureUpdatesExpiryTime" -ErrorAction SilentlyContinue; '
        'Remove-ItemProperty -Path $p -Name "PauseQualityUpdatesExpiryTime" -ErrorAction SilentlyContinue; '
        'Remove-ItemProperty -Path $p -Name "PauseUpdatesStartTime" -ErrorAction SilentlyContinue; '
        'Write-Output "OK"'
    )
    out, code = run_powershell(ps)
    if code == 0:
        return "√ Windows 更新已恢复"
    return "× 操作失败：\n{}".format(out)


def show_file_extensions():
    """显示文件扩展名和隐藏文件（重启资源管理器后生效）"""
    ps = r'''
$p = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced'
Set-ItemProperty -Path $p -Name 'HideFileExt' -Value 0
Set-ItemProperty -Path $p -Name 'Hidden' -Value 1
Write-Output 'OK'
'''
    out, code = run_powershell(ps)
    if code != 0:
        return "× 操作失败：\n{}".format(out)
    run_powershell('Stop-Process -Name explorer -Force; Start-Sleep 1; Start-Process explorer')
    return "√ 已显示文件扩展名和隐藏文件（桌面会闪一下，正常）"


def clean_temp_files():
    """清理用户临时文件、系统临时文件，并清空回收站"""
    ps = r'''
$paths = @($env:TEMP, "$env:SystemRoot\Temp")
foreach ($p in $paths) {
  if (Test-Path $p) {
    Get-ChildItem -Path $p -Recurse -Force -ErrorAction SilentlyContinue | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
  }
}
Clear-RecycleBin -Force -ErrorAction SilentlyContinue
Write-Output 'OK'
'''
    out, code = run_powershell(ps)
    if code == 0:
        return "√ 临时文件和回收站已清理"
    return "× 操作失败：\n{}".format(out)


# 可移动的用户文件夹：key -> (User Shell Folders 里的注册表键, D 盘下的目标文件夹名)
_MOVE_FOLDERS = {
    "downloads": ("{374DE290-123F-4565-9164-39C4925E467B}", "Downloads"),
    "desktop": ("Desktop", "Desktop"),
    "documents": ("Personal", "Documents"),
}


def move_folders_to_d(which="all"):
    """把下载/桌面/文档（可单个，也可全部）完整搬到 D 盘。

    先用 robocopy 搬文件，搬成功才改路径；被占用/失败的文件保留在 C 盘原处，不会丢。
    which: "downloads" / "desktop" / "documents" / "all"
    """
    keys = ["downloads", "desktop", "documents"] if which == "all" else [which]
    entries = ["  '{}' = '{}'".format(_MOVE_FOLDERS[k][0], _MOVE_FOLDERS[k][1]) for k in keys]
    map_str = "@{\n" + "\n".join(entries) + "\n}"
    ps = r'''
$reg = 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
$map = __MAP__
$lines = @()
foreach ($k in $map.Keys) {
  $raw = (Get-ItemProperty -Path $reg -Name $k -ErrorAction SilentlyContinue).$k
  if (-not $raw) { continue }
  $src = [Environment]::ExpandEnvironmentVariables($raw)
  if (-not (Test-Path $src)) { $lines += ($map[$k] + ': source missing, skip'); continue }
  $target = Join-Path 'D:' $map[$k]
  $srcFull = (Resolve-Path $src).Path.TrimEnd('\')
  $targetFull = $target.TrimEnd('\')
  if ($srcFull -eq $targetFull) { $lines += ($map[$k] + ': already on D, skip'); continue }

  New-Item -ItemType Directory -Path $target -Force | Out-Null
  # /MOVE 复制成功后删源文件；被占用/失败的文件保留在源，不会丢。返回码 >=8 才算失败。
  robocopy $srcFull $targetFull /MOVE /COPY:DAT /R:1 /W:1 /NFL /NDL /NJH /NJS /NP | Out-Null
  $rc = $LASTEXITCODE
  if ($rc -ge 8) {
    $lines += ($map[$k] + ': copy FAILED (rc=' + $rc + '), path unchanged')
  } else {
    # 保险：搬完再验证目标目录确实有内容，才改路径（防止「返回码正常但实际没搬/没搬干净」时悄悄改了路径）
    $n = @(Get-ChildItem -Path $targetFull -Force -ErrorAction SilentlyContinue).Count
    if ($n -eq 0) {
      $lines += ($map[$k] + ': moved nothing (target empty, rc=' + $rc + '), path unchanged')
    } else {
      Set-ItemProperty -Path $reg -Name $k -Value $targetFull
      $lines += ($map[$k] + ': moved to ' + $targetFull)
    }
  }
}
Write-Output ($lines -join "`n")
'''.replace("__MAP__", map_str)
    out, code = run_powershell(ps)
    run_powershell('Stop-Process -Name explorer -Force; Start-Sleep 1; Start-Process explorer')
    if code != 0:
        return "× 操作失败：\n{}".format(out)
    return "√ 已搬到 D 盘（文件先搬完才改路径）：\n" + (out or "（无变化）")


def stop_edge_update():
    """一键停止 Edge 自动更新：注册表策略 + 禁用服务 + 禁用计划任务 三重锁定"""
    if not is_admin():
        return "× 需要管理员权限，请点右上角的「以管理员身份重启」"
    ps = r'''
$ErrorActionPreference = 'SilentlyContinue'
# 1. 注册表策略（HKLM + HKCU 都设）
foreach ($p in @('HKLM:\SOFTWARE\Policies\Microsoft\EdgeUpdate', 'HKCU:\SOFTWARE\Policies\Microsoft\EdgeUpdate')) {
  New-Item -Path $p -Force | Out-Null
  Set-ItemProperty -Path $p -Name 'UpdateDefault' -Value 0
  Set-ItemProperty -Path $p -Name 'AutoUpdateCheckPeriodMinutes' -Value 0
  Set-ItemProperty -Path $p -Name 'UpdatesSuppressed' -Value 1
}
# 2. 禁用 Edge 更新服务
foreach ($s in @('edgeupdate', 'edgeupdatem')) {
  Stop-Service -Name $s -Force
  Set-Service -Name $s -StartupType Disabled
}
# 3. 禁用 Edge 更新计划任务
foreach ($t in @('MicrosoftEdgeUpdateTaskMachineCore', 'MicrosoftEdgeUpdateTaskMachineUA')) {
  Get-ScheduledTask -TaskName $t | Disable-ScheduledTask
}
Write-Output 'OK'
'''
    out, code = run_powershell(ps)
    if code == 0:
        return "√ Edge 自动更新已停止（注册表策略 + 服务 + 计划任务 三重锁定）"
    return "× 操作失败：\n{}".format(out)


def resume_edge_update():
    """一键恢复 Edge 自动更新：撤销策略 + 启用服务 + 启用计划任务"""
    if not is_admin():
        return "× 需要管理员权限，请点右上角的「以管理员身份重启」"
    ps = r'''
$ErrorActionPreference = 'SilentlyContinue'
# 1. 撤销注册表策略
foreach ($p in @('HKLM:\SOFTWARE\Policies\Microsoft\EdgeUpdate', 'HKCU:\SOFTWARE\Policies\Microsoft\EdgeUpdate')) {
  Remove-ItemProperty -Path $p -Name 'UpdateDefault'
  Remove-ItemProperty -Path $p -Name 'AutoUpdateCheckPeriodMinutes'
  Remove-ItemProperty -Path $p -Name 'UpdatesSuppressed'
}
# 2. 启用 Edge 更新服务
foreach ($s in @('edgeupdate', 'edgeupdatem')) {
  Set-Service -Name $s -StartupType Automatic
  Start-Service -Name $s
}
# 3. 启用 Edge 更新计划任务
foreach ($t in @('MicrosoftEdgeUpdateTaskMachineCore', 'MicrosoftEdgeUpdateTaskMachineUA')) {
  Get-ScheduledTask -TaskName $t | Enable-ScheduledTask
}
Write-Output 'OK'
'''
    out, code = run_powershell(ps)
    if code == 0:
        return "√ Edge 自动更新已恢复"
    return "× 操作失败：\n{}".format(out)


# ==================== 离线安装（开发环境） ====================

def _config_file():
    """配置文件路径：跟 exe 同目录（便携，随 exe 走）。记录用户选的安装包文件夹等设置。"""
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "config.json")


def _load_config():
    """读配置文件，失败返回空 dict（不打断主流程）"""
    try:
        with open(_config_file(), "r", encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_config(cfg):
    """写配置文件（失败静默，不影响主流程）"""
    try:
        with open(_config_file(), "w", encoding="utf-8") as f:
            json.dump(cfg, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def packages_dir():
    """安装包目录：优先用用户配置的路径（U 盘/其他盘）；否则 exe 旁边的 packages/（开发时 = 项目根目录）"""
    p = _load_config().get("packages_path")
    if p and os.path.isdir(p):
        return p
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, "packages")


def _resource_path(rel):
    """内置资源（打进 exe）的路径：打包后 = PyInstaller 临时解压目录，开发时 = 项目根目录"""
    if getattr(sys, 'frozen', False):
        base = sys._MEIPASS
    else:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel)


def devtools_dir():
    """开发环境安装根目录：优先 D:/DevTools（D 盘存在且可写），否则 C:/DevTools

    光驱/U 盘也可能占 D 盘符但只读，光靠 os.path.exists 会误判，所以补一个写测试。
    """
    if os.path.exists("D:\\"):
        try:
            probe = os.path.join("D:\\", ".__wtest")
            with open(probe, "w") as f:
                f.write("")
            os.remove(probe)
            return "D:\\DevTools"
        except OSError:
            pass
    return "C:\\DevTools"


def sha256_file(path):
    """计算文件 SHA-256，返回 64 位小写十六进制字符串"""
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def _verify_pkg(path):
    """校验安装包 SHA-256 是否和 exe 内置指纹一致，返回 (是否通过, 提示文本)。

    没有内置指纹的安装包一律拒绝（fail-closed）——防止有人往 packages 里放
    一个没登记的恶意文件，被旧的「跳过校验」逻辑直接放行安装。
    """
    name = os.path.basename(path)
    expected = PACKAGE_HASHES.get(name)
    if not expected:
        return False, (
            "× 安装包 {} 没有内置指纹，为安全起见已停止安装。\n"
            "请从官网下载对应版本，并用 build_hashes.py 重新登记指纹后再试。".format(name)
        )
    actual = sha256_file(path)
    if actual.lower() == expected.lower():
        return True, "√ 安装包指纹校验通过（SHA-256 一致）"
    return False, (
        "× 安装包指纹校验失败！文件可能已被篡改，已停止安装。\n"
        "请删除 packages\\{} 后，从官网重新下载原版再试。".format(name)
    )


def _run_installer(args, timeout=900):
    """运行安装器并等待完成（安装耗时较长，超时放宽到 15 分钟）"""
    try:
        proc = subprocess.run(
            args, capture_output=True, text=True, encoding="gbk", errors="replace", timeout=timeout,
        )
        return (proc.stdout + proc.stderr).strip(), proc.returncode
    except FileNotFoundError:
        return "", 127
    except Exception as e:
        return "执行出错：{}".format(e), -1


def _run_shell(cmd, timeout=600):
    """用 shell 运行一条完整命令字符串（注册表 UninstallString 是带引号路径+参数，需 shell 解析引号）"""
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, encoding="gbk", errors="replace",
            timeout=timeout, shell=True,
        )
        return (proc.stdout + proc.stderr).strip(), proc.returncode
    except Exception as e:
        return "执行出错：{}".format(e), -1


def _add_to_path(bin_dir):
    """把 bin 目录追加到当前用户 PATH（注册表写入，避免 setx 的 1024 字符截断）"""
    ps = (
        '$old = [Environment]::GetEnvironmentVariable("Path","User"); '
        '$new = $old.TrimEnd(";") + ";" + "{bin}"; '
        '[Environment]::SetEnvironmentVariable("Path", $new, "User"); '
        'Write-Output "OK"'
    ).format(bin=bin_dir)
    out, code = run_powershell(ps)
    return code == 0


def _verify_installed(kind):
    """装完后用绝对路径重新检测（PATH 要重开终端才刷新，这里直接找安装目录）"""
    if kind == "python":
        for exe in glob.glob(r"C:\Program Files\Python*\python.exe"):
            out, code = run_cmd([exe, "--version"])
            if code == 0:
                return "√ Python 安装成功：{}".format(out)
        return "√ Python 已安装（PATH 需重开终端/程序后生效）"
    if kind == "gcc":
        gcc = os.path.join(devtools_dir(), "mingw", "mingw64", "bin", "gcc.exe")
        if os.path.exists(gcc):
            out, code = run_cmd([gcc, "--version"])
            if code == 0:
                first = out.splitlines()[0] if out.splitlines() else out
                return "√ gcc 安装成功：{}".format(first)
        return "√ gcc 已解压（PATH 需重开终端后生效）"
    if kind == "node":
        node = r"C:\Program Files\nodejs\node.exe"
        if os.path.exists(node):
            out, code = run_cmd([node, "--version"])
            if code == 0:
                return "√ Node.js 安装成功：{}".format(out)
        return "√ Node.js 已安装（PATH 需重开终端后生效）"
    if kind == "git":
        git = r"C:\Program Files\Git\cmd\git.exe"
        if os.path.exists(git):
            out, code = run_cmd([git, "--version"])
            if code == 0:
                return "√ Git 安装成功：{}".format(out)
        return "√ Git 已安装（PATH 需重开终端后生效）"
    if kind == "java":
        for cand in glob.glob(os.path.join(devtools_dir(), "jdk", "*", "bin", "java.exe")):
            out, code = run_cmd([cand, "-version"])
            if code == 0:
                first = out.splitlines()[0] if out.splitlines() else out
                return "√ Java（JDK）安装成功：{}".format(first)
        return "√ Java（JDK）已解压（PATH 需重开终端后生效）"
    if kind == "vscode":
        for exe in (r"C:\Program Files\Microsoft VS Code\Code.exe",
                    os.path.expandvars(r"%LOCALAPPDATA%\Programs\Microsoft VS Code\Code.exe")):
            if os.path.exists(exe):
                out, code = run_cmd([exe, "--version"])
                if code == 0:
                    first = out.splitlines()[0] if out.splitlines() else out
                    return "√ VS Code 安装成功：{}".format(first)
        return "√ VS Code 已安装（PATH 需重开终端后生效）"
    return ""


# ==================== Win7 前置补丁（KB2533623） ====================
# Win7 装 Python 3.8 的前置条件：SP1 + KB2533623 补丁，否则安装器报缺补丁退出码 0x1。
# 微软已下架原补丁，这里内置 x64 版（微软数字签名已验证），装 Python 时自动补齐，用户无需手动打补丁。

KB_PATCH = "Windows6.1-KB2533623-x64.msu"


def _is_win7():
    """是否 Windows 7（KB2533623 只对 Win7 装 Python 3.8 有意义）"""
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                             r"SOFTWARE\Microsoft\Windows NT\CurrentVersion")
        try:
            ver, _ = winreg.QueryValueEx(key, "CurrentVersion")
        finally:
            winreg.CloseKey(key)
        return str(ver).startswith("6.1")
    except Exception:
        return False


def _kb2533623_installed():
    """查注册表是否已装 KB2533623 补丁"""
    try:
        import winreg
        key = winreg.OpenKey(
            winreg.HKEY_LOCAL_MACHINE,
            r"SOFTWARE\Microsoft\Windows\CurrentVersion\Component Based Servicing\Packages")
        i = 0
        while True:
            try:
                name = winreg.EnumKey(key, i)
            except OSError:
                break
            if "KB2533623" in name:
                winreg.CloseKey(key)
                return True
            i += 1
        winreg.CloseKey(key)
    except OSError:
        pass
    return False


def _install_kb2533623():
    """自动安装 KB2533623 补丁（wusa 静默装）。成功返回 None，失败返回错误文本。

    补丁已内置进 exe（打包时只把 packages/ 里这一个 2.3MB 小文件塞进去），优先用内置的；
    找不到再回退 packages 目录（开发时 / 老版本 exe 的场景）。
    """
    pkg = _resource_path(os.path.join("packages", KB_PATCH))
    if not os.path.exists(pkg):
        pkg = os.path.join(packages_dir(), KB_PATCH)
    if not os.path.exists(pkg):
        return "× 未找到前置补丁 {}。".format(KB_PATCH)
    ok, msg = _verify_pkg(pkg)
    if not ok:
        return msg
    # wusa.exe 返回码：0=成功，3010=成功但需重启，2359302=已安装
    out, code = _run_installer(["wusa.exe", pkg, "/quiet", "/norestart"], timeout=600)
    if code not in (0, 3010, 2359302):
        return "× 补丁 KB2533623 安装失败（返回码 {}）：\n{}".format(code, out)
    return None


# 每个软件两个版本的安装包：文件名用于在 packages\ 精确查找，标签用于版本菜单显示
INSTALL_VARIANTS = {
    # 每项 (安装包文件名, 面板按钮文字, 日志标题用的版本名)
    "python": {
        "win7":   ("python-3.8.10-amd64.exe",  "Win7 适配版（Python 3.8）", "Python 3.8"),
        "modern": ("python-3.13.15-amd64.exe", "Win10/11 高版本（Python 3.13）", "Python 3.13"),
    },
    "gcc": {
        "win7":   ("winlibs-gcc-16.2.0-msvcrt.zip", "Win7 适配版（MSVCRT 运行时）", "C/C++（MSVCRT）"),
        "modern": ("winlibs-gcc-16.2.0-ucrt.zip",    "Win10/11 高版本（UCRT 运行时）", "C/C++（UCRT）"),
    },
    "node": {
        "win7":   ("node-v13.14.0-x64.msi", "Win7 适配版（Node 13）", "Node.js 13"),
        "modern": ("node-v26.10.0-x64.msi", "Win10/11 高版本（Node 26）", "Node.js 26"),
    },
    "git": {
        "win7":   ("Git-2.46.2-64-bit.exe", "Win7 适配版（Git 2.46）", "Git 2.46"),
        "modern": ("Git-2.55.0.5-64-bit.exe", "Win10/11 高版本（Git 2.55）", "Git 2.55"),
    },
    "java": {
        "win7":   ("OpenJDK8U-jdk_x64_windows_hotspot_8u262b10.zip", "Win7 适配版（JDK 8）", "JDK 8"),
        "modern": ("OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip", "Win10/11 高版本（JDK 21）", "JDK 21"),
    },
    "vscode": {
        "win7":   ("VSCodeSetup-x64-1.85.2.exe",  "Win7 适配版（VS Code 1.85）", "VS Code 1.85"),
        "modern": ("VSCodeSetup-x64-1.139.0.exe", "Win10/11 高版本（VS Code 1.139）", "VS Code 1.139"),
    },
}

# kind → 中文名（菜单/日志标题用）
KIND_TITLES = {"python": "Python", "gcc": "C/C++", "java": "Java", "node": "Node.js", "git": "Git", "vscode": "VS Code"}


# ==================== 联网下载安装包 ====================

# 每个安装包：显示名、官方下载 URL、国内镜像 URL（无镜像为 None）。
# key 即 packages 里的文件名（也是 hashes.py 的指纹键）。
DOWNLOAD_SOURCES = {
    "python-3.8.10-amd64.exe": {
        "label": "Python 3.8（Win7 适配版）",
        "url": "https://www.python.org/ftp/python/3.8.10/python-3.8.10-amd64.exe",
        "mirror": "https://npmmirror.com/mirrors/python/3.8.10/python-3.8.10-amd64.exe",
    },
    "python-3.13.15-amd64.exe": {
        "label": "Python 3.13（Win10/11 版）",
        "url": "https://www.python.org/ftp/python/3.13.15/python-3.13.15-amd64.exe",
        "mirror": "https://npmmirror.com/mirrors/python/3.13.15/python-3.13.15-amd64.exe",
    },
    "node-v13.14.0-x64.msi": {
        "label": "Node.js 13（Win7 适配版）",
        "url": "https://nodejs.org/dist/v13.14.0/node-v13.14.0-x64.msi",
        "mirror": "https://npmmirror.com/mirrors/node/v13.14.0/node-v13.14.0-x64.msi",
    },
    "node-v26.10.0-x64.msi": {
        "label": "Node.js 26（Win10/11 版）",
        "url": "https://nodejs.org/dist/v26.10.0/node-v26.10.0-x64.msi",
        "mirror": "https://npmmirror.com/mirrors/node/v26.10.0/node-v26.10.0-x64.msi",
    },
    "Git-2.46.2-64-bit.exe": {
        "label": "Git 2.46（Win7 适配版）",
        "url": "https://github.com/git-for-windows/git/releases/download/v2.46.2.windows.1/Git-2.46.2-64-bit.exe",
        "mirror": "https://npmmirror.com/mirrors/git-for-windows/v2.46.2.windows.1/Git-2.46.2-64-bit.exe",
    },
    "Git-2.55.0.5-64-bit.exe": {
        "label": "Git 2.55（Win10/11 版）",
        "url": "https://github.com/git-for-windows/git/releases/download/v2.55.0.windows.5/Git-2.55.0.5-64-bit.exe",
        "mirror": "https://npmmirror.com/mirrors/git-for-windows/v2.55.0.windows.5/Git-2.55.0.5-64-bit.exe",
    },
    "winlibs-gcc-16.2.0-msvcrt.zip": {
        "label": "C/C++（MSVCRT，Win7 版）",
        "url": "https://github.com/brechtsanders/winlibs_mingw/releases/download/16.2.0posix-14.0.0-msvcrt-r1/winlibs-x86_64-posix-seh-gcc-16.2.0-mingw-w64msvcrt-14.0.0-r1.zip",
        "mirror": None,
    },
    "winlibs-gcc-16.2.0-ucrt.zip": {
        "label": "C/C++（UCRT，Win10/11 版）",
        "url": "https://github.com/brechtsanders/winlibs_mingw/releases/download/16.2.0posix-14.0.0-ucrt-r1/winlibs-x86_64-posix-seh-gcc-16.2.0-mingw-w64ucrt-14.0.0-r1.zip",
        "mirror": None,
    },
    "OpenJDK8U-jdk_x64_windows_hotspot_8u262b10.zip": {
        "label": "JDK 8（Win7 适配版）",
        "url": "https://github.com/AdoptOpenJDK/openjdk8-binaries/releases/download/jdk8u262-b10/OpenJDK8U-jdk_x64_windows_hotspot_8u262b10.zip",
        "mirror": None,
    },
    "OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip": {
        "label": "JDK 21（Win10/11 版）",
        "url": "https://github.com/adoptium/temurin21-binaries/releases/download/jdk-21.0.12.1%2B1/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip",
        "mirror": "https://mirrors.tuna.tsinghua.edu.cn/Adoptium/21/jdk/x64/windows/OpenJDK21U-jdk_x64_windows_hotspot_21.0.12.1_1.zip",
    },
    "VSCodeSetup-x64-1.85.2.exe": {
        "label": "VS Code 1.85（Win7 适配版）",
        "url": "https://update.code.visualstudio.com/1.85.2/win32-x64/stable",
        "mirror": None,  # 微软 CDN 国内可直连
    },
    "VSCodeSetup-x64-1.139.0.exe": {
        "label": "VS Code 1.139（Win10/11 版）",
        "url": "https://update.code.visualstudio.com/1.139.0/win32-x64/stable",
        "mirror": None,  # 微软 CDN 国内可直连
    },
}

# 下载失败时提示「国内可能下不了」的包（官方在 GitHub、无国内镜像）
_MIRRORLESS_HINT = "（此包官方放在 GitHub，国内网络通常直连失败，可能需要开代理）"


def _url_reachable(url, timeout=8):
    """探测 URL 能否连通（HEAD 请求，2xx/3xx 视为通）"""
    try:
        req = urllib.request.Request(url, method="HEAD", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status in (200, 206, 301, 302, 303, 307, 308)
    except Exception:
        return False


def _download_to(url, dest, progress_cb=None, cancel_event=None):
    """下载 url 到 dest（先写 .part 临时文件，成功后再原子替换）。返回 (成功, 消息)"""
    part = dest + ".part"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=60) as r:
            total = int(r.headers.get("Content-Length") or 0)
            done = 0
            with open(part, "wb") as f:
                while True:
                    if cancel_event is not None and cancel_event.is_set():
                        return False, "已取消"
                    chunk = r.read(256 * 1024)
                    if not chunk:
                        break
                    f.write(chunk)
                    done += len(chunk)
                    if progress_cb is not None:
                        progress_cb(done, total)
        os.replace(part, dest)
        return True, "OK"
    except Exception as e:
        if os.path.exists(part):
            try:
                os.remove(part)
            except OSError:
                pass
        return False, str(e)


def fetch_package(filename, progress_cb=None, cancel_event=None):
    """下载单个安装包：官方源优先、失败换镜像，下载后 SHA-256 校验。返回消息字符串。"""
    info = DOWNLOAD_SOURCES.get(filename)
    if not info:
        return "× 未知安装包：{}".format(filename)
    label = info["label"]
    dest = os.path.join(packages_dir(), filename)
    # 已存在且指纹一致：跳过下载
    if os.path.exists(dest):
        ok, _ = _verify_pkg(dest)
        if ok:
            return "√ {} 已存在且校验通过，跳过下载。".format(label)
    candidates = [("官方源", info["url"])]
    if info.get("mirror"):
        candidates.append(("国内镜像", info["mirror"]))
    last_err = ""
    for src, url in candidates:
        ok, msg = _download_to(url, dest, progress_cb=progress_cb, cancel_event=cancel_event)
        if ok:
            break
        if cancel_event is not None and cancel_event.is_set():
            return "× {} 下载已取消。".format(label)
        last_err = msg
    else:
        hint = _MIRRORLESS_HINT if info.get("mirror") is None else ""
        return "× {} 下载失败：{}{}".format(label, last_err, hint)
    # 下载后校验（保证下到的是原版、没被篡改）
    vok, vmsg = _verify_pkg(dest)
    if not vok:
        try:
            os.remove(dest)
        except OSError:
            pass
        return "× {} 下载后校验失败（文件可能不完整或被篡改）：{}".format(label, vmsg)
    return "√ {} 下载完成，SHA-256 校验通过。".format(label)


def fetch_all_packages(progress_cb=None, cancel_event=None):
    """一键下载全部安装包。返回汇总消息。"""
    results = []
    total = len(DOWNLOAD_SOURCES)
    for i, filename in enumerate(DOWNLOAD_SOURCES, 1):
        if cancel_event is not None and cancel_event.is_set():
            results.append("× 已取消，剩余 {} 个未下载。".format(total - i + 1))
            break
        msg = fetch_package(filename, progress_cb=progress_cb, cancel_event=cancel_event)
        results.append("[{}/{}] {}".format(i, total, msg))
    return "\n".join(results)


def install_python(variant):
    if "√" in detect_python():
        return "【注意】检测到本机已有 Python，本次没有执行安装：\n{}\n（如需换版本，请先卸载现有的再装）".format(detect_python())
    # 安装前清一次 MSI 产品注册残留：上次卸载若残留 exe.msi 等内部 MSI 的产品注册，
    # 这次 Burn 会误判「已安装」跳过不装，dev.msi 找不到 python.exe 组件就死循环（1603）。
    _clear_python_product_keys()
    filename = INSTALL_VARIANTS["python"][variant][0]
    pkg = os.path.join(packages_dir(), filename)
    if not os.path.exists(pkg):
        return "× 未找到 Python 安装包 {}。\n请下载该文件放到 packages\\ 目录后重试。".format(filename)
    ok, msg = _verify_pkg(pkg)
    if not ok:
        return msg
    # Win7 装 Python 3.8 需要先打 KB2533623 补丁，否则安装器报缺补丁退出码 0x1
    if _is_win7() and not _kb2533623_installed():
        err = _install_kb2533623()
        if err:
            return err
        return (
            "√ 已自动安装前置补丁 KB2533623（Win7 装 Python 3.8 必需）。\n"
            "这个补丁要重启电脑才生效，请重启后再点一次「安装 Python」，这次就能直接装好了。"
        )
    log = os.path.join(os.environ.get("TEMP", r"C:\Windows\Temp"), "python_setup.log")
    out, code = _run_installer([
        pkg, "/quiet", "/log", log, "InstallAllUsers=1", "PrependPath=1",
        "Include_launcher=0", "Include_test=0", "Include_doc=0",
    ])
    if code != 0:
        return "× Python 安装失败（返回码 {}）：\n{}\n（安装日志：{}，请把日志末尾几行发我）".format(code, out, log)
    return "{}\n√ Python 安装完成。\n{}".format(_pkg_note("python", pkg), _verify_installed("python"))


def install_gcc(variant):
    if "√" in detect_gcc():
        return "【注意】检测到本机已有 C/C++ 编译器，本次没有执行安装：\n{}\n（如需换版本，请先卸载现有的再装）".format(detect_gcc())
    filename = INSTALL_VARIANTS["gcc"][variant][0]
    pkg = os.path.join(packages_dir(), filename)
    if not os.path.exists(pkg):
        return "× 未找到 C/C++ 编译器压缩包 {}。\n请下载 WinLibs 的该 zip 放到 packages\\ 目录后重试。".format(filename)
    ok, msg = _verify_pkg(pkg)
    if not ok:
        return msg
    target = os.path.join(devtools_dir(), "mingw")
    try:
        if os.path.exists(target):
            return ("× 检测到 {} 目录已存在（说明本机已装过 C/C++ 编译器）。\n"
                    "本工具无法同时装两个 C/C++ 版本。\n"
                    "要换版本，请先在「卸载」里卸掉旧的（会自动清理 PATH），再装新的。").format(target)
        with zipfile.ZipFile(pkg) as z:
            for info in z.infolist():
                parts = info.filename.replace("\\", "/").split("/")
                if info.filename.startswith("/") or ".." in parts:
                    return "× 压缩包内含非法路径，已停止解压（文件可能被篡改）。"
            z.extractall(target)
    except Exception as e:
        return "× 解压失败：{}".format(e)
    added = False
    for sub in ["mingw64\\bin", "bin"]:
        bin_dir = os.path.join(target, sub)
        if os.path.isdir(bin_dir):
            _add_to_path(bin_dir)
            added = True
            break
    if not added:
        return "× 解压完成，但没找到 bin 目录，请检查压缩包结构。"
    return "{}\n√ C/C++ 编译器已解压到 {}。\n{}".format(_pkg_note("gcc", pkg), target, _verify_installed("gcc"))


def install_node(variant):
    if "√" in detect_node():
        return "【注意】检测到本机已有 Node.js，本次没有执行安装：\n{}\n（如需换版本，请先卸载现有的再装）".format(detect_node())
    filename = INSTALL_VARIANTS["node"][variant][0]
    pkg = os.path.join(packages_dir(), filename)
    if not os.path.exists(pkg):
        return "× 未找到 Node.js 安装包 {}。\n请下载该文件放到 packages\\ 目录后重试。".format(filename)
    ok, msg = _verify_pkg(pkg)
    if not ok:
        return msg
    out, code = _run_installer(["msiexec", "/i", pkg, "/quiet", "/norestart"])
    if code != 0:
        return "× Node.js 安装失败（返回码 {}）：\n{}".format(code, out)
    return "{}\n√ Node.js 安装完成。\n{}".format(_pkg_note("node", pkg), _verify_installed("node"))


def install_git(variant):
    if "√" in detect_git():
        return "【注意】检测到本机已有 Git，本次没有执行安装：\n{}\n（如需换版本，请先卸载现有的再装）".format(detect_git())
    filename = INSTALL_VARIANTS["git"][variant][0]
    pkg = os.path.join(packages_dir(), filename)
    if not os.path.exists(pkg):
        return "× 未找到 Git 安装包 {}。\n请下载该文件放到 packages\\ 目录后重试。".format(filename)
    ok, msg = _verify_pkg(pkg)
    if not ok:
        return msg
    out, code = _run_installer([pkg, "/VERYSILENT", "/NORESTART", "/SP-"])
    if code != 0:
        return "× Git 安装失败（返回码 {}）：\n{}".format(code, out)
    return "{}\n√ Git 安装完成。\n{}".format(_pkg_note("git", pkg), _verify_installed("git"))


def install_java(variant):
    if "√" in detect_java():
        return "【注意】检测到本机已有 Java，本次没有执行安装：\n{}\n（如需换版本，请先卸载现有的再装）".format(detect_java())
    filename = INSTALL_VARIANTS["java"][variant][0]
    pkg = os.path.join(packages_dir(), filename)
    if not os.path.exists(pkg):
        return "× 未找到 Java（JDK）压缩包 {}。\n请下载该 zip 放到 packages\\ 目录后重试。".format(filename)
    ok, msg = _verify_pkg(pkg)
    if not ok:
        return msg
    target = os.path.join(devtools_dir(), "jdk")
    try:
        if os.path.exists(target):
            return ("× 检测到 {} 目录已存在（说明本机已装过 Java）。\n"
                    "本工具无法同时装两个 Java 版本。\n"
                    "要换版本，请先在「卸载」里卸掉旧的（会自动清理 PATH），再装新的。").format(target)
        with zipfile.ZipFile(pkg) as z:
            for info in z.infolist():
                parts = info.filename.replace("\\", "/").split("/")
                if info.filename.startswith("/") or ".." in parts:
                    return "× 压缩包内含非法路径，已停止解压（文件可能被篡改）。"
            z.extractall(target)
    except Exception as e:
        return "× 解压失败：{}".format(e)
    # JDK 解压后是 jdk8u262-b10/ 或 jdk-21.0.12.1+1/ 这类子目录，往里找 bin\java.exe
    bin_dir = ""
    for cand in glob.glob(os.path.join(target, "*", "bin")):
        if os.path.isdir(cand) and os.path.exists(os.path.join(cand, "java.exe")):
            bin_dir = cand
            break
    if not bin_dir:
        return "× 解压完成，但没找到 JDK 的 bin 目录，请检查压缩包结构。"
    _add_to_path(bin_dir)
    return "{}\n√ Java（JDK）已解压到 {}。\n{}".format(_pkg_note("java", pkg), target, _verify_installed("java"))


def install_vscode(variant):
    if "√" in detect_vscode():
        return "【注意】检测到本机已有 VS Code，本次没有执行安装：\n{}\n（如需换版本，请先卸载现有的再装）".format(detect_vscode())
    filename = INSTALL_VARIANTS["vscode"][variant][0]
    pkg = os.path.join(packages_dir(), filename)
    if not os.path.exists(pkg):
        return "× 未找到 VS Code 安装包 {}。\n请下载该文件放到 packages\\ 目录后重试。".format(filename)
    ok, msg = _verify_pkg(pkg)
    if not ok:
        return msg
    # VS Code 是 Inno Setup（System Installer）装到 Program Files；
    # /VERYSILENT 静默装，/MERGETASKS=!runcode 装完不自动打开编辑器
    out, code = _run_installer([pkg, "/VERYSILENT", "/NORESTART", "/MERGETASKS=!runcode"])
    if code != 0:
        return "× VS Code 安装失败（返回码 {}）：\n{}".format(code, out)
    return "{}\n√ VS Code 安装完成。\n{}".format(_pkg_note("vscode", pkg), _verify_installed("vscode"))


# ==================== 手动安装（用户自己选路径） ====================

# zip 类没有安装向导，需弹目录选择框解压；exe/msi 有图形向导，直接打开让用户选路径
_ZIP_KINDS = {"gcc", "java"}


def manual_install(kind, variant, target_dir=None):
    """非一键安装：让用户自己动手装、自己选安装路径。

    variant 指定版本（"win7"/"modern"）；exe/msi（Python/Node/Git/VS Code）打开安装包图形向导，
    用户在向导里选路径（我们不碰路径参数）；zip（C/C++/Java）没有向导，解压到用户选的 target_dir 并配 PATH。
    """
    entry = INSTALL_VARIANTS.get(kind, {}).get(variant)
    if not entry:
        return "× 未知的安装项：{}".format(kind)
    filename = entry[0]
    pkg = os.path.join(packages_dir(), filename)
    if not os.path.exists(pkg):
        return "× 未找到安装包 {}。\n请下载该文件放到 packages\\ 目录后重试。".format(filename)
    ok, msg = _verify_pkg(pkg)
    if not ok:
        return msg
    title = KIND_TITLES.get(kind, kind)
    if kind in _ZIP_KINDS:
        if not target_dir:
            return "× 未选择安装目录。"
        return _manual_unzip(kind, pkg, target_dir)
    try:
        os.startfile(pkg)
    except Exception as e:
        return "× 无法打开安装包：{}\n请到 packages\\{} 手动双击运行。".format(e, filename)
    return (
        "√ 已打开 {} 安装器。\n"
        "请按向导点「下一步」，遇到「选择安装位置/目标目录」的步骤时，改成你想装的路径即可。\n"
        "装完后点本面板里的「检测」看是否成功；若提示未检测到，重开一次本程序或终端即可。".format(title)
    )


def _manual_unzip(kind, pkg, target_dir):
    """把 zip 类（C/C++、Java）解压到用户选的目录，并配 PATH"""
    title = KIND_TITLES.get(kind, kind)
    try:
        with zipfile.ZipFile(pkg) as z:
            for info in z.infolist():
                parts = info.filename.replace("\\", "/").split("/")
                if info.filename.startswith("/") or ".." in parts:
                    return "× 压缩包内含非法路径，已停止解压（文件可能被篡改）。"
            z.extractall(target_dir)
    except Exception as e:
        return "× 解压失败：{}".format(e)
    bin_dir = ""
    if kind == "gcc":
        for sub in ["mingw64\\bin", "bin"]:
            c = os.path.join(target_dir, sub)
            if os.path.isdir(c):
                bin_dir = c
                break
    else:  # java
        for cand in glob.glob(os.path.join(target_dir, "*", "bin")):
            if os.path.isdir(cand) and os.path.exists(os.path.join(cand, "java.exe")):
                bin_dir = cand
                break
    if not bin_dir:
        return "× 解压完成，但没找到 bin 目录，请检查压缩包结构。"
    _add_to_path(bin_dir)
    return (
        "{}\n√ {} 已解压到 {}。\n"
        "已把 {} 加入用户 PATH（重开终端/程序后生效）。".format(
            _pkg_note(kind, pkg), title, target_dir, bin_dir)
    )


# ==================== 卸载（开发环境） ====================

def _find_uninstall_key(keywords):
    """遍历注册表 Uninstall 键，按 DisplayName 关键词匹配，返回 (名称, 卸载命令, 静默命令) 或 None"""
    import winreg
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    for root, path in roots:
        try:
            key = winreg.OpenKey(root, path)
        except OSError:
            continue
        i = 0
        while True:
            try:
                sub = winreg.EnumKey(key, i)
            except OSError:
                break
            i += 1
            try:
                sk = winreg.OpenKey(key, sub)
            except OSError:
                continue
            display = un = quiet = ""
            try:
                display = str(winreg.QueryValueEx(sk, "DisplayName")[0])
            except OSError:
                pass
            if display and all(k.lower() in display.lower() for k in keywords):
                try:
                    un = str(winreg.QueryValueEx(sk, "UninstallString")[0])
                except OSError:
                    pass
                try:
                    quiet = str(winreg.QueryValueEx(sk, "QuietUninstallString")[0])
                except OSError:
                    pass
                winreg.CloseKey(sk)
                winreg.CloseKey(key)
                return display, un, quiet
            winreg.CloseKey(sk)
        winreg.CloseKey(key)
    return None


def _uninstall_entry(display, quiet, un):
    """按给定的卸载命令静默卸载一个软件项，返回结果文本。

    卸载候选（按优先级）：Python 这类 WiX Burn bundle 必须走它自己的
    exe /uninstall /quiet 才能把内部 MSI 全卸干净，用 msiexec /x {bundle_guid} 会残留。
    """
    import re
    candidates = []
    if quiet:
        candidates.append(quiet)
    if un:
        candidates.append(un + " /quiet")
    m = re.search(r"\{[0-9A-Fa-f\-]{36}\}", (quiet or un) or "")
    if m:
        candidates.append('msiexec /x "{}" /qn /norestart'.format(m.group(0)))

    last_out, last_code = "", -1
    for cmd in candidates:
        out, code = _run_shell(cmd)
        last_out, last_code = out, code
        if code in (0, 3010):
            return "√ 已静默卸载 {}。".format(display)
    return "× 卸载 {} 失败（返回码 {}）：\n{}".format(display, last_code, last_out)


def _uninstall_msi(keywords):
    """通用静默卸载：按 DisplayName 关键词找卸载项，再静默卸载。返回结果文本。"""
    info = _find_uninstall_key(keywords)
    if not info:
        return "× 未检测到已安装（注册表无卸载项），可能未安装或已经卸载。"
    display, un, quiet = info
    return _uninstall_entry(display, quiet, un)


def _clear_python_uninstall_keys():
    """删除注册表里所有 DisplayName 含 'Python' 的 Uninstall 项。

    Python 的 Burn bundle 卸载后常残留顶层 Uninstall 项（{guid}），导致重装时安装器误判
    「已安装」→ 进 Modify 修复模式 → dev.msi 报 1603。这里手动删掉兜底。
    """
    import winreg
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    removed = []
    for root, path in roots:
        try:
            key = winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WRITE)
        except OSError:
            continue
        subs = []
        try:
            i = 0
            while True:
                try:
                    subs.append(winreg.EnumKey(key, i))
                    i += 1
                except OSError:
                    break
        except Exception:
            winreg.CloseKey(key)
            continue
        for sub in subs:
            display = ""
            try:
                sk = winreg.OpenKey(key, sub, 0, winreg.KEY_READ)
                try:
                    display = str(winreg.QueryValueEx(sk, "DisplayName")[0])
                except OSError:
                    pass
                winreg.CloseKey(sk)
            except OSError:
                continue
            if display and "python" in display.lower():
                try:
                    winreg.DeleteKey(key, sub)
                    removed.append(display)
                except OSError:
                    pass
        winreg.CloseKey(key)
    return removed


def _delete_reg_tree(root, path):
    """递归删除注册表键 path（连同所有子键）。Software\Python 有多层子键，DeleteKey 只能删空键。"""
    import winreg
    try:
        key = winreg.OpenKey(root, path, 0, winreg.KEY_READ | winreg.KEY_WRITE)
    except OSError:
        return False
    subs = []
    try:
        i = 0
        while True:
            try:
                subs.append(winreg.EnumKey(key, i))
                i += 1
            except OSError:
                break
    except Exception:
        pass
    winreg.CloseKey(key)
    for sub in subs:
        _delete_reg_tree(root, path + "\\" + sub)
    try:
        winreg.DeleteKey(root, path)
        return True
    except OSError:
        return False


def _clear_python_product_keys():
    """删除 MSI 产品注册库里 ProductName 含 Python 的残留项。

    Python 3.13 的 Burn bundle 卸载后常残留内部 MSI（尤其 exe.msi）的产品注册
    （Installer\\Products\\{ProductCode}），导致重装时 Burn 误判该包「已安装」而跳过、
    不重装。而 dev.msi 的 AppSearch 用 CompLocator 按组件 ID 找 python.exe（exe.msi 的
    组件 {543B1949-...}），找不到就走进它 DrLocator 表里一对互为 parent 的死循环
    （PythonExe_Directory ⇄ PythonExe_DirectoryFile），栈溢出 0xc00000fd 报 1603。
    删掉产品注册，让 Burn 重装时把 exe 等包重新装齐，dev 就能找到 python.exe 组件。
    """
    import winreg
    removed = []
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Classes\Installer\Products"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Classes\WOW6432Node\Installer\Products"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Classes\Installer\Products"),
    ]
    for root, path in roots:
        try:
            key = winreg.OpenKey(root, path, 0, winreg.KEY_READ)
        except OSError:
            continue
        subs = []
        try:
            i = 0
            while True:
                try:
                    subs.append(winreg.EnumKey(key, i))
                    i += 1
                except OSError:
                    break
        except Exception:
            winreg.CloseKey(key)
            continue
        winreg.CloseKey(key)
        for sub in subs:
            name = ""
            try:
                sk = winreg.OpenKey(root, path + "\\" + sub, 0, winreg.KEY_READ)
                try:
                    name = str(winreg.QueryValueEx(sk, "ProductName")[0])
                except OSError:
                    pass
                winreg.CloseKey(sk)
            except OSError:
                continue
            if name and "python" in name.lower():
                if _delete_reg_tree(root, path + "\\" + sub):
                    removed.append(name)
    # UserData\S-1-5-18\Products 才是 Burn 用 MsiQueryProductState(ALLUSERMANAGED)
    # 判「已安装」的关键（键名也是压缩 GUID，但 DisplayName 挂在 InstallProperties 子键下）。
    # 之前只删 Installer\Products 漏了这里，导致重装时 Burn 仍判 exe Present、跳过不装、
    # dev.msi 找不到 python.exe 组件就走 DrLocator 环死循环 1603。
    for root, path in [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Installer\UserData\S-1-5-18\Products"),
    ]:
        try:
            key = winreg.OpenKey(root, path, 0, winreg.KEY_READ)
        except OSError:
            continue
        subs = []
        try:
            i = 0
            while True:
                try:
                    subs.append(winreg.EnumKey(key, i))
                    i += 1
                except OSError:
                    break
        except Exception:
            winreg.CloseKey(key)
            continue
        winreg.CloseKey(key)
        for sub in subs:
            name = ""
            try:
                sk = winreg.OpenKey(root, path + "\\" + sub + r"\InstallProperties", 0, winreg.KEY_READ)
                try:
                    name = str(winreg.QueryValueEx(sk, "DisplayName")[0])
                except OSError:
                    pass
                winreg.CloseKey(sk)
            except OSError:
                continue
            if name and "python" in name.lower():
                if _delete_reg_tree(root, path + "\\" + sub):
                    removed.append(name)
    return removed


def _list_python_installs():
    """枚举已安装的 Python 主版本（过滤 Burn bundle 的内部 MSI 组件）。

    Python 3.13 是 WiX Burn bundle，注册表 Uninstall 里除主安装项（"Python 3.13.15 (64-bit)"）
    外还有一堆内部组件（Core Interpreter / Documentation / ...），DisplayName 都含 "Python"。
    这些内部组件不能单独卸载，必须过滤掉，只留主安装项。
    返回 [(DisplayName, DisplayVersion, QuietUninstallString, UninstallString)]。
    """
    import winreg
    _COMPONENT_WORDS = (
        "core interpreter", "documentation", "development libraries",
        "executables", "standard library", "tcl", "pip", "launcher",
        "test suite", "utilities",
    )
    roots = [
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
        (winreg.HKEY_CURRENT_USER, r"SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall"),
    ]
    found = []
    for root, path in roots:
        try:
            key = winreg.OpenKey(root, path)
        except OSError:
            continue
        subs = []
        try:
            i = 0
            while True:
                try:
                    subs.append(winreg.EnumKey(key, i))
                    i += 1
                except OSError:
                    break
        finally:
            winreg.CloseKey(key)
        for sub in subs:
            try:
                sk = winreg.OpenKey(root, path + "\\" + sub)
            except OSError:
                continue
            display = version = un = quiet = ""
            try:
                display = str(winreg.QueryValueEx(sk, "DisplayName")[0])
            except OSError:
                pass
            dl = display.lower()
            if "python" not in dl or any(w in dl for w in _COMPONENT_WORDS):
                winreg.CloseKey(sk)
                continue
            try:
                version = str(winreg.QueryValueEx(sk, "DisplayVersion")[0])
            except OSError:
                pass
            try:
                quiet = str(winreg.QueryValueEx(sk, "QuietUninstallString")[0])
            except OSError:
                pass
            try:
                un = str(winreg.QueryValueEx(sk, "UninstallString")[0])
            except OSError:
                pass
            winreg.CloseKey(sk)
            found.append((display, version, quiet, un))
    return found


def uninstall_python(display=None):
    """卸载 Python。display 指定要卸的主版本 DisplayName；None 表示卸唯一已装的。

    只卸载/清理指定版本，不影响其他 Python 版本；只在「仅一个版本」时才做全量残留清理
    （多版本时全量清理会误删其他版本的产品注册）。
    """
    import shutil
    import winreg
    installs = _list_python_installs()
    target = None
    if display:
        for item in installs:
            if item[0] == display:
                target = item
                break
        if target is None:
            return "× 未找到要卸载的版本：{}".format(display)
    else:
        if not installs:
            return ("× 没找到可以一键卸载的 Python。\n"
                    "· 如果你是用「手动安装（自己选路径）」装的、选了自定义位置，一键卸载找不到它，需要你自己到装的位置手动删除。\n"
                    "· 如果 Python 没装在默认位置，本工具也查不到，无法帮你卸载。\n"
                    "请到「控制面板 → 程序和功能」或你当初选的安装目录手动处理。")
        if len(installs) > 1:
            return "× 检测到多个 Python 版本，请在「卸载」里选择要卸载的版本。"
        target = installs[0]

    display_name, version, quiet, un = target
    result = _uninstall_entry(display_name, quiet, un)
    if "√" not in result:
        return result

    msgs = []
    # 只删这个版本对应的目录（如 Python313），不碰其他版本
    import re
    m = re.search(r"(\d+)\.(\d+)", version or display_name)
    if m:
        dir_name = "Python{}{}".format(m.group(1), m.group(2))
        for d in glob.glob(os.path.join(r"C:\Program Files", dir_name + "*")):
            if os.path.isdir(d):
                try:
                    shutil.rmtree(d)
                    msgs.append("目录 " + os.path.basename(d))
                except OSError:
                    pass

    # 只有「这是唯一版本」时才做全量注册表残留清理（防 1603）；多版本时全量清理会误删其他版本
    if len(installs) == 1:
        for name in _clear_python_uninstall_keys():
            msgs.append("注册表 " + name)
        for root, pykey in [
            (winreg.HKEY_CURRENT_USER, r"Software\Python"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Python"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Python"),
        ]:
            if _delete_reg_tree(root, pykey):
                msgs.append("注册表 " + pykey)
        for name in _clear_python_product_keys():
            msgs.append("产品 " + name)

    if msgs:
        result += "\n（已清理卸载残留：{}）".format("、".join(msgs))
    return result


def uninstall_node():
    result = _uninstall_msi(["Node.js"])
    # Node.js MSI 卸载常残留 C:\Program Files\nodejs 目录（node.exe 等），
    # detect_node 用绝对路径兜底会误报「已安装」。不管注册表项在不在，都顺手删目录 + 清 PATH。
    import shutil
    msgs = []
    for d in glob.glob(r"C:\Program Files\nodejs"):
        if os.path.isdir(d):
            try:
                shutil.rmtree(d)
                msgs.append("目录 " + os.path.basename(d))
            except OSError:
                pass
    if _remove_from_path("nodejs"):
        msgs.append("PATH 中的 nodejs 条目")
    if msgs:
        result += "\n（已清理卸载残留：{}）".format("、".join(msgs))
    return result


def uninstall_git():
    """Git 是 Inno Setup 安装，用 unins000.exe /VERYSILENT 静默卸载（卸载器会自我删除）"""
    info = _find_uninstall_key(["Git"])
    if not info:
        return "× 未检测到 Git 已安装（注册表无卸载项）。"
    display, un, quiet = info
    exe = (quiet or un).strip()
    if not exe:
        return "× 未找到 Git 卸载程序，请到控制面板「程序和功能」手动卸载。"
    # UninstallString 形如 "C:\Program Files\Git\unins000.exe"，去掉首尾引号
    if exe.startswith('"'):
        exe = exe[1:].split('"')[0]
    out, code = _run_installer(
        [exe, "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES", "/SP-"], timeout=600)
    if code != 0:
        return "× 卸载 Git 失败（返回码 {}）：\n{}".format(code, out)
    # Inno 卸载器返回 0 后会异步自我删除 unins000.exe，立刻查 os.path.exists 会误判「仍在」。
    # 改以「注册表卸载项已消失」为准，等 2 秒让删除落盘再查。
    import time
    time.sleep(2)
    if _find_uninstall_key(["Git"]):
        return "× 卸载 Git 未完成：注册表卸载项仍存在。"
    return "√ 已静默卸载 {}。".format(display)


def uninstall_vscode():
    """VS Code 是 Inno Setup（System Installer），用 unins000.exe /VERYSILENT 静默卸载"""
    info = _find_uninstall_key(["Visual Studio Code"])
    if not info:
        return "× 未检测到 VS Code 已安装（注册表无卸载项）。"
    display, un, quiet = info
    exe = (quiet or un).strip()
    if not exe:
        return "× 未找到 VS Code 卸载程序，请到控制面板「程序和功能」手动卸载。"
    # UninstallString 形如 "C:\Program Files\Microsoft VS Code\unins000.exe"，去掉首尾引号
    if exe.startswith('"'):
        exe = exe[1:].split('"')[0]
    out, code = _run_installer(
        [exe, "/VERYSILENT", "/NORESTART", "/SUPPRESSMSGBOXES", "/SP-"], timeout=600)
    if code != 0:
        return "× 卸载 VS Code 失败（返回码 {}）：\n{}".format(code, out)
    # 同 Git：Inno 卸载器返回 0 后异步自我删除，等 2 秒再以「注册表卸载项消失」为准
    import time
    time.sleep(2)
    if _find_uninstall_key(["Visual Studio Code"]):
        return "× 卸载 VS Code 未完成：注册表卸载项仍存在。"
    return "√ 已静默卸载 {}。".format(display)


def _remove_from_path(fragment):
    """从当前用户 PATH 中移除含 fragment 的条目（卸载 gcc 时清理 PATH）"""
    ps = (
        '$p = [Environment]::GetEnvironmentVariable("Path","User"); '
        '$parts = $p -split ";" | Where-Object { $_ -and ($_ -notmatch [regex]::Escape("{frag}")) }; '
        '[Environment]::SetEnvironmentVariable("Path", ($parts -join ";"), "User"); '
        'Write-Output "OK"'
    ).replace("{frag}", fragment)
    out, code = run_powershell(ps)
    return code == 0


def uninstall_gcc():
    """C/C++ 是我们自己解压的，卸载 = 删除 mingw 目录 + 清理 PATH"""
    import shutil
    target = os.path.join(devtools_dir(), "mingw")
    if not os.path.exists(target):
        return "× 未检测到 C/C++ 编译器（{} 不存在），可能未安装或已卸载。".format(target)
    try:
        shutil.rmtree(target)
    except OSError as e:
        return "× 删除 {} 失败：{}".format(target, e)
    _remove_from_path("mingw")
    return "√ 已删除 C/C++ 编译器目录 {}（PATH 中的 mingw 条目已清理，重开终端后生效）。".format(target)


def uninstall_java():
    """Java 是我们自己解压的，卸载 = 删除 jdk 目录 + 清理 PATH"""
    import shutil
    target = os.path.join(devtools_dir(), "jdk")
    if not os.path.exists(target):
        return "× 未检测到 Java（{} 不存在），可能未安装或已卸载。".format(target)
    try:
        shutil.rmtree(target)
    except OSError as e:
        return "× 删除 {} 失败：{}".format(target, e)
    _remove_from_path("DevTools\\jdk")
    return "√ 已删除 Java 目录 {}（PATH 中的 jdk 条目已清理，重开终端后生效）。".format(target)


ENV_INFO = {
    "python": {"win7": True,  "note": ""},
    "gcc":    {"win7": False, "note": "此版本不支持 Win7（需 Win10 及以上）"},
    "java":   {"win7": False, "note": "新版 JDK 不支持 Win7（需 Win10 及以上）"},
    "node":   {"win7": False, "note": "此版本不支持 Win7（需 Win10 及以上）"},
    "git":    {"win7": False, "note": "新版不支持 Win7（需 Win10 及以上）"},
    "vscode": {"win7": True,  "note": ""},
}


def _pkg_note(kind, pkg):
    """生成安装包信息行：文件名 + （不支持 Win7 时）注意提示"""
    name = os.path.basename(pkg)
    info = ENV_INFO.get(kind, {})
    if not info.get("win7", True):
        return "安装包：{}（注意：{}）".format(name, info["note"])
    return "安装包：{}".format(name)


INSTALLERS = {
    "python": install_python,
    "gcc": install_gcc,
    "java": install_java,
    "node": install_node,
    "git": install_git,
    "vscode": install_vscode,
}

UNINSTALLERS = {
    "python": uninstall_python,
    "gcc": uninstall_gcc,
    "java": uninstall_java,
    "node": uninstall_node,
    "git": uninstall_git,
    "vscode": uninstall_vscode,
}


# ==================== 界面 ====================

class ToolboxApp:
    def __init__(self, root):
        self.root = root
        root.title("装机助手")
        # 窗口尺寸自适应屏幕：低分辨率屏（如 Win7 虚拟机 1024x768）不被裁剪
        sw = root.winfo_screenwidth()
        sh = root.winfo_screenheight()
        w = max(900, min(1200, sw - 40))
        h = max(620, min(760, sh - 90))
        root.geometry("{}x{}".format(w, h))
        root.minsize(900, 620)
        root.configure(bg=BG)

        self.admin = is_admin()
        self._busy = False  # 执行互斥标志：检测/安装进行中禁止重复点击
        self._downloading = False  # 下载互斥标志：下载进行中禁止重复触发
        self._setup_style()

        # 网格布局：0=顶部，1=主区，2=底部提示
        root.columnconfigure(0, weight=0)
        root.columnconfigure(1, weight=1)
        root.rowconfigure(1, weight=1)

        # ---- 顶部：标题 + 状态 + 按钮（窄屏时可横向滚动，拖出被遮住的按钮） ----
        top = ttk.Frame(root, padding=(16, 12, 16, 4))
        top.grid(row=0, column=0, columnspan=2, sticky="ew")

        top_canvas = tk.Canvas(top, height=48, bg=BG, highlightthickness=0)
        top_inner = ttk.Frame(top_canvas)
        top_canvas.create_window((0, 0), window=top_inner, anchor="nw")
        top_canvas.pack(side="top", fill="x", expand=True)

        # 横向滚动条：仅当顶部内容超宽（按钮被遮住）时才显示；原生样式，明显可拖
        self.top_hbar = tk.Scrollbar(top, orient="horizontal", command=top_canvas.xview)
        top_canvas.configure(xscrollcommand=self.top_hbar.set)

        def _update_top_scroll(event=None):
            top_canvas.configure(scrollregion=top_canvas.bbox("all"))
            region = top_canvas.bbox("all")
            if region:
                # 画布高度贴合内容，避免标题/按钮被竖向裁切
                content_h = region[3] - region[1]
                if content_h != top_canvas.winfo_height():
                    top_canvas.configure(height=content_h)
                if region[2] - region[0] > top_canvas.winfo_width():
                    self.top_hbar.pack(side="top", fill="x")
                else:
                    self.top_hbar.pack_forget()

        top_inner.bind("<Configure>", _update_top_scroll)
        top_canvas.bind("<Configure>", _update_top_scroll)

        ttk.Label(top_inner, text="装机助手",
                  font=("微软雅黑", 18, "bold"), foreground=HEADING).pack(side="left")

        if self.admin:
            status_text = "  ·  已用管理员身份运行"
            status_color = OK
        else:
            status_text = "  ·  未用管理员身份（部分功能受限）"
            status_color = ERR
        ttk.Label(top_inner, text=status_text, foreground=status_color,
                  font=("微软雅黑", 11, "bold")).pack(side="left", padx=(16, 0))

        top_right = ttk.Frame(top_inner)
        top_right.pack(side="left", padx=(24, 0))
        ttk.Button(top_right, text="检测环境与安装位置",
                   command=lambda: self._run("检测环境与安装位置", self._detect_all)).pack(side="left", padx=4)
        if not self.admin:
            ttk.Button(top_right, text="以管理员身份重启", command=self._relaunch).pack(side="left", padx=4)

        # ---- 左侧：按钮面板（可滚动，低分辨率屏幕放不下时可滚）----
        left_outer = ttk.Frame(root, padding=(16, 4, 4, 4))
        left_outer.grid(row=1, column=0, sticky="ns")
        left_outer.rowconfigure(0, weight=1)
        left_outer.columnconfigure(0, weight=1)

        canvas = tk.Canvas(left_outer, bg=BG, highlightthickness=0, width=280)
        vbar = tk.Scrollbar(left_outer, orient="vertical", command=canvas.yview)
        left = ttk.Frame(canvas)
        win_id = canvas.create_window((0, 0), window=left, anchor="nw")
        canvas.configure(yscrollcommand=vbar.set)

        def _on_left_conf(event):
            canvas.configure(scrollregion=canvas.bbox("all"))
        left.bind("<Configure>", _on_left_conf)

        def _on_canvas_conf(event):
            canvas.itemconfigure(win_id, width=event.width)
        canvas.bind("<Configure>", _on_canvas_conf)

        def _on_mousewheel(event):
            canvas.yview_scroll(int(-event.delta / 120), "units")
        canvas.bind("<Enter>", lambda e: canvas.bind_all("<MouseWheel>", _on_mousewheel))
        canvas.bind("<Leave>", lambda e: canvas.unbind_all("<MouseWheel>"))

        canvas.grid(row=0, column=0, sticky="nsew")
        vbar.grid(row=0, column=1, sticky="ns")

        # 开发环境安装区（每个按钮弹出「Win7 适配版 / Win10+ 高版本」选择菜单）
        # 超过 4 个按钮自动折叠：默认显示前 4 个，点栏底小箭头展开全部
        self._add_fold_section(left, "① 开发环境（离线安装）", [
            ("联网获取安装包", lambda b: b.configure(command=lambda bb=b: self._show_download_panel(bb))),
            ("安装 / 卸载 Python",  lambda b: self._bind_variant(b, "python")),
            ("安装 / 卸载 C/C++",   lambda b: self._bind_variant(b, "gcc")),
            ("安装 / 卸载 Java",    lambda b: self._bind_variant(b, "java")),
            ("安装 / 卸载 Node.js", lambda b: self._bind_variant(b, "node")),
            ("安装 / 卸载 Git",     lambda b: self._bind_variant(b, "git")),
            ("安装 / 卸载 VS Code", lambda b: self._bind_variant(b, "vscode")),
        ])

        # 系统优化区（「移动文件夹」上移到「恢复更新」下面；超过 4 个自动折叠）
        self._add_fold_section(left, "② 系统优化", [
            ("暂停 Windows 更新", lambda b: self._set_pause_btn(b)),
            ("恢复 Windows 更新", lambda b: b.configure(command=lambda: self._run("恢复更新", resume_windows_update))),
            ("下载/桌面/文档 移到 D 盘", lambda b: self._set_move_btn(b)),
            ("停止 Edge 自动更新", lambda b: b.configure(command=lambda: self._run("停止 Edge 更新", stop_edge_update))),
            ("恢复 Edge 自动更新", lambda b: b.configure(command=lambda: self._run("恢复 Edge 更新", resume_edge_update))),
            ("一键配置远程桌面", lambda b: b.configure(command=self._do_config_remote)),
            ("显示扩展名 / 隐藏文件", lambda b: b.configure(command=lambda: self._run("显示扩展名/隐藏文件", show_file_extensions))),
            ("清理临时文件 / 回收站", lambda b: b.configure(command=self._do_clean_temp)),
        ])

        # 硬件检测区
        self._add_section(left, "③ 硬件检测", [
            ("检测硬件信息", lambda: self._run("硬件检测", detect_hardware)),
            ("屏幕坏点检测", lambda: self._dead_pixel_test()),
        ])

        # 问题诊断区（三个分类各自给结论，底部一键诊断汇总）
        self._add_section(left, "④ 问题诊断", [
            ("显卡 / 屏幕", lambda: self._run("问题诊断·显卡屏幕", diagnose_gpu_screen)),
            ("设备驱动", lambda: self._run("问题诊断·设备驱动", diagnose_devices)),
            ("内存 / 硬盘", lambda: self._run("问题诊断·内存硬盘", diagnose_memory_disk)),
            ("一键诊断这台电脑", lambda: self._run("问题诊断", diagnose)),
        ])

        # ---- 右侧：日志 ----
        right = ttk.Frame(root, padding=(4, 4, 16, 4))
        right.grid(row=1, column=1, sticky="nsew")
        right.rowconfigure(1, weight=1)
        right.columnconfigure(0, weight=1)

        ttk.Label(right, text="执行日志（点按钮后，结果显示在这里）",
                  font=("微软雅黑", 10, "bold"), foreground=ACCENT).grid(row=0, column=0, sticky="w", pady=(0, 4))

        self.log_box = scrolledtext.ScrolledText(right, state="disabled", font=("微软雅黑", 10),
                                                 wrap="word", bg=LOG_BG, fg=FG, insertbackground=FG)
        self.log_box.grid(row=1, column=0, sticky="nsew")

        # 日志颜色
        self.log_box.tag_configure("head", foreground=ACCENT, font=("微软雅黑", 10, "bold"))
        self.log_box.tag_configure("ok", foreground=OK)
        self.log_box.tag_configure("err", foreground=ERR)

        # ---- 底部：提示条 ----
        tip = tk.Label(
            root,
            text="提示：暂停/恢复更新、安装到系统目录 需要管理员权限（点上方「以管理员身份重启」）；检测环境不需要。",
            font=("微软雅黑", 9), fg=FG_DIM, bg=BG_CARD, anchor="w", padx=12, pady=8,
        )
        tip.grid(row=2, column=0, columnspan=2, sticky="ew", padx=16, pady=(4, 12))

        # 作者水印「NDCC」：place 定位到日志区底部居中（沉在日志深色背景上，不参与 grid 不挤占任何控件），
        # 颜色只比背景亮一点，像背景像素被“抠掉”形成的字，极淡不显眼
        wm = tk.Label(right, text="NDCC", font=("微软雅黑", 8),
                      fg="#1a2b40", bg=LOG_BG)
        wm.place(in_=self.log_box, relx=0.5, rely=1.0, anchor="s", y=-2)

        self._log("欢迎使用装机助手！点击左侧按钮开始。", "head")
        self._log(detect_windows())

    def _setup_style(self):
        """深海军蓝 + 琥珀金主题"""
        style = ttk.Style()
        style.theme_use("clam")
        style.configure(".", background=BG, foreground=FG)
        style.configure("TFrame", background=BG)
        style.configure("TLabel", background=BG, foreground=FG)
        style.configure("TButton", background=BTN, foreground=BTN_FG,
                        font=("微软雅黑", 9, "bold"), padding=(6, 4), borderwidth=0)
        style.map("TButton",
                  background=[("active", BTN_HOVER), ("pressed", "#c0822a")],
                  foreground=[("active", BTN_FG)])
        style.configure("TLabelframe", background=BG, bordercolor=BORDER)
        style.configure("TLabelframe.Label", background=BG, foreground=ACCENT,
                        font=("微软雅黑", 10, "bold"))
        # 滚动条：深色轨道 + 亮蓝滑块，深色背景下也能一眼看到、知道能拖
        style.configure("TScrollbar", troughcolor=BG_CARD, background="#6b8cb8",
                        arrowcolor="#cfe0f0", bordercolor=BG_CARD,
                        lightcolor=BG_CARD, darkcolor=BG_CARD)
        style.map("TScrollbar",
                  background=[("active", "#8aa7c9"), ("pressed", "#9db9dd")])

    def _add_section(self, parent, title, buttons):
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(fill="x", pady=4)
        for text, cmd in buttons:
            btn = ttk.Button(frame, text=text, command=cmd)
            btn.pack(fill="x", pady=2)
            self._fit_button(btn, text)

    def _add_fold_section(self, parent, title, items, limit=4):
        """可折叠分区：默认显示前 limit 个按钮，超出时栏底出现小箭头（默认▼），
        点一下展开全部（箭头▲），再点收回（回到前 limit 个、箭头▼）。

        items 是 [(text, maker), ...]，maker(btn) 用来给按钮绑定命令
        （这样既能绑命令，又能在需要时拿到 btn 引用定位弹窗）。
        """
        frame = ttk.LabelFrame(parent, text=title, padding=8)
        frame.pack(fill="x", pady=4)

        widgets = []
        for text, maker in items:
            btn = ttk.Button(frame, text=text)
            if maker is not None:
                maker(btn)
            widgets.append(btn)

        # 不超过 limit：直接全部显示，无箭头
        if len(widgets) <= limit:
            for btn in widgets:
                btn.pack(fill="x", pady=2)
                self._fit_button(btn, btn.cget("text"))
            return

        # 超过 limit：先全部 pack 以便测宽度，再收起超出的部分
        for btn in widgets:
            btn.pack(fill="x", pady=2)
            self._fit_button(btn, btn.cget("text"))
        for btn in widgets[limit:]:
            btn.pack_forget()

        # 折叠小箭头：横向长条，居中一个 ▼/▲
        arrow = tk.Label(frame, text="▼", fg=ACCENT, bg=BG_CARD,
                         font=("微软雅黑", 12, "bold"), cursor="hand2",
                         anchor="center", pady=2)
        arrow.pack(fill="x", pady=(2, 0))

        expanded = [False]

        def _toggle(event=None):
            if expanded[0]:
                for btn in widgets[limit:]:
                    btn.pack_forget()
                arrow.configure(text="▼")
            else:
                for btn in widgets[limit:]:
                    btn.pack(fill="x", pady=2, before=arrow)
                arrow.configure(text="▲")
            expanded[0] = not expanded[0]

        arrow.bind("<Button-1>", _toggle)

    def _bind_variant(self, btn, kind):
        """给开发环境安装按钮绑定「Win7 / Win10+ / 卸载」弹窗命令"""
        btn.configure(command=lambda k=kind, b=btn: self._show_variant_menu(k, b))

    def _set_pause_btn(self, btn):
        """记录「暂停更新」按钮引用（弹窗要定位在它下面），并绑定命令"""
        self.pause_btn = btn
        btn.configure(command=self._show_pause_menu)

    def _set_move_btn(self, btn):
        """记录「移到 D 盘」按钮引用（弹窗定位），并绑定命令"""
        self.move_btn = btn
        btn.configure(command=self._show_move_menu)

    def _fit_button(self, btn, text):
        """布局完成后测按钮实际宽度，文字放不下就自动缩小字号（9→8→7）。

        用 <Configure> 触发（按钮宽度稳定后），宽度还没就绪时延迟重试；
        不写死宽度，按每台机器实际渲染（DPI 缩放）来，中文短按钮保持 9 号，
        长按钮或未来的英文版自动缩到能放下为止。
        """
        tries = [0]

        def _fit(event=None):
            try:
                avail = btn.winfo_width() - 16  # 减去按钮左右内边距，留余量
            except Exception:
                return
            if avail <= 0:
                if tries[0] < 10:
                    tries[0] += 1
                    self.root.after(120, _fit)
                return
            size = 9
            f = tkfont.Font(family="微软雅黑", size=size, weight="bold")
            while f.measure(text) > avail and size > 7:
                size -= 1
                f.configure(size=size)
            if size != 9:
                btn.configure(font=("微软雅黑", size, "bold"))
        btn.bind("<Configure>", _fit)
        self.root.after(120, _fit)

    def _log(self, text, tag=None):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", text + "\n", tag)
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    def _run(self, name, func, *args):
        """后台线程执行（避免 PowerShell 检测/操作卡死界面），并加互斥防重复点击"""
        if self._busy:
            self._log("（上一项还在执行中，请稍候，勿重复点击…）", "err")
            return
        self._busy = True
        self._log("\n▶ {} ...".format(name), "head")
        self._log("（正在执行，请稍候…）")
        def worker():
            try:
                result = func(*args)
            except Exception as e:
                result = "× 执行出错：{}".format(e)
            self.root.after(0, self._finish_run, result)
        threading.Thread(target=worker, daemon=True).start()

    def _run_install(self, name, func, *args):
        """后台线程跑安装（避免解压/安装卡死界面），并加互斥防重复点击"""
        if self._busy:
            self._log("（上一项还在执行中，请稍候，勿重复点击…）", "err")
            return
        self._busy = True
        self._log("\n▶ {} ...".format(name), "head")
        self._log("（正在后台执行，界面可继续操作，完成后此处显示结果）")
        def worker():
            try:
                result = func(*args)
            except Exception as e:
                result = "× 安装过程出错：{}".format(e)
            self.root.after(0, self._finish_run, result)
        threading.Thread(target=worker, daemon=True).start()

    def _finish_run(self, result):
        """结果回到主线程后写日志，并解除互斥"""
        try:
            for line in result.split("\n"):
                if line.startswith("√"):
                    self._log(line, "ok")
                elif line.startswith("×"):
                    self._log(line, "err")
                else:
                    self._log(line)
        finally:
            self._busy = False

    def _relaunch(self):
        """以管理员身份重启本程序（UAC 点「否」时不关程序，继续当前模式运行）"""
        try:
            params = subprocess.list2cmdline(sys.argv)
            ret = ctypes.windll.shell32.ShellExecuteW(None, "runas", sys.executable, params, None, 1)
            # ShellExecuteW 返回 >32 表示成功启动了提权进程；<=32 是失败
            # （点「否」= 5 拒绝、1223 取消），此时不关当前程序，让用户继续用。
            if ret > 32:
                self.root.destroy()
            else:
                self._log("已取消提权（UAC 点了「否」），继续以当前模式运行。")
        except Exception as e:
            self._log("提权失败：{}".format(e), "err")

    def _pick_item(self, win, cb):
        """面板里点某一项：先关面板，再执行该项动作"""
        win.destroy()
        cb()

    def _popup_panel(self, btn, title, items):
        """在按钮下方弹出带右上角 × 的自绘深色面板。

        items: [(label, callback), ...] 每项一行，点击执行 callback 并关闭面板。
        关闭方式：点右上角 ×、点面板外空白处、按 Esc。
        """
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg=BG_CARD)

        # 标题栏：左标题 + 右 ×
        bar = tk.Frame(win, bg=BG_CARD)
        bar.pack(fill="x")
        tk.Label(bar, text=title, bg=BG_CARD, fg=ACCENT,
                 font=("微软雅黑", 10, "bold")).pack(side="left", padx=10, pady=4)
        close = tk.Label(bar, text="✕", bg=BG_CARD, fg=FG_DIM,
                         font=("微软雅黑", 11), cursor="hand2")
        close.pack(side="right", padx=8, pady=2)
        close.bind("<Button-1>", lambda e: win.destroy())
        close.bind("<Enter>", lambda e: close.configure(fg=ERR))
        close.bind("<Leave>", lambda e: close.configure(fg=FG_DIM))

        tk.Frame(win, bg=BORDER, height=1).pack(fill="x")

        # 选项按钮（takefocus=False 不抢焦点，避免点项时误触发 FocusOut 关面板）
        for label, cb in items:
            b = tk.Button(win, text=label, bg=BG_CARD, fg=FG,
                          activebackground=BTN, activeforeground=BTN_FG,
                          relief="flat", bd=0, anchor="w", padx=12, pady=5,
                          font=("微软雅黑", 10), takefocus=False,
                          command=lambda c=cb: self._pick_item(win, c))
            b.pack(fill="x")
            b.bind("<Enter>", lambda e, w=b: w.configure(bg="#1d3150"))
            b.bind("<Leave>", lambda e, w=b: w.configure(bg=BG_CARD))

        # 定位在按钮下方（先 update 拿实际宽高）
        win.update_idletasks()
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        pos = "+{}+{}".format(x, y)
        win.geometry(pos)
        # overrideredirect 无边框窗口首次映射时可能被重置到左上角，映射后强制一次位置
        win.after(0, lambda: win.geometry(pos))
        win.bind("<Map>", lambda e: win.geometry(pos))

        win.attributes("-topmost", True)
        win.focus_force()
        win.grab_set()
        win.bind("<FocusOut>", lambda e: win.destroy())
        win.bind("<Escape>", lambda e: win.destroy())

    def _show_download_panel(self, btn):
        """「联网获取安装包」面板：列出 12 个包（可单个下/一键全下），显示进度、可取消"""
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.configure(bg=BG_CARD)

        # 标题栏
        bar = tk.Frame(win, bg=BG_CARD)
        bar.pack(fill="x")
        tk.Label(bar, text="联网获取安装包", bg=BG_CARD, fg=ACCENT,
                 font=("微软雅黑", 10, "bold")).pack(side="left", padx=10, pady=4)
        close = tk.Label(bar, text="✕", bg=BG_CARD, fg=FG_DIM, font=("微软雅黑", 11), cursor="hand2")
        close.pack(side="right", padx=8, pady=2)
        close.bind("<Button-1>", lambda e: win.destroy())
        close.bind("<Enter>", lambda e: close.configure(fg=ERR))
        close.bind("<Leave>", lambda e: close.configure(fg=FG_DIM))
        tk.Frame(win, bg=BORDER, height=1).pack(fill="x")

        # 安装包文件夹：显示当前路径 + 更改位置（手动指认 U 盘/其他盘的已有安装包）
        path_row = tk.Frame(win, bg=BG_CARD)
        path_row.pack(fill="x", padx=10, pady=(8, 4))
        tk.Label(path_row, text="安装包文件夹：", bg=BG_CARD, fg=FG_DIM, font=("微软雅黑", 9)).pack(side="left")
        path_var = tk.StringVar(value=packages_dir())
        tk.Label(path_row, textvariable=path_var, bg=BG_CARD, fg=FG, font=("微软雅黑", 9),
                 anchor="w").pack(side="left", fill="x", expand=True, padx=(0, 6))

        def _choose_dir():
            d = filedialog.askdirectory(parent=self.root, title="选择安装包文件夹（下载会存到这里）",
                                        initialdir=path_var.get())
            if d:
                cfg = _load_config()
                cfg["packages_path"] = d
                _save_config(cfg)
                path_var.set(d)
                self._log("安装包文件夹已改为：{}".format(d))

        tk.Button(path_row, text="更改位置", bg=BTN, fg=BTN_FG, activebackground=BTN_HOVER,
                  relief="flat", font=("微软雅黑", 9, "bold"), padx=8, command=_choose_dir).pack(side="right")

        tk.Label(win, text="Win7 补丁（KB2533623）已内置无需下载；下面 12 个包可单个下、也可一键全下。",
                 bg=BG_CARD, fg=FG_DIM, font=("微软雅黑", 8), anchor="w", justify="left",
                 wraplength=360).pack(fill="x", padx=10, pady=(0, 6))

        # 12 个包列表（滚动）
        list_frame = tk.Frame(win, bg=BG_CARD)
        list_frame.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        canvas = tk.Canvas(list_frame, bg=BG_CARD, highlightthickness=0, height=230)
        scroll = tk.Scrollbar(list_frame, orient="vertical", command=canvas.yview)
        inner = tk.Frame(canvas, bg=BG_CARD)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))
        canvas.create_window((0, 0), window=inner, anchor="nw")
        canvas.configure(yscrollcommand=scroll.set)
        canvas.pack(side="left", fill="both", expand=True)
        scroll.pack(side="right", fill="y")

        marks = {}

        def _refresh_marks():
            for fn, lbl in marks.items():
                has = os.path.exists(os.path.join(packages_dir(), fn))
                lbl.configure(text="●" if has else "○", fg=OK if has else FG_DIM)

        for filename in DOWNLOAD_SOURCES:
            info = DOWNLOAD_SOURCES[filename]
            row = tk.Frame(inner, bg=BG_CARD)
            row.pack(fill="x", pady=1)
            mark = tk.Label(row, text="○", bg=BG_CARD, fg=FG_DIM, font=("微软雅黑", 9))
            mark.pack(side="left", padx=(0, 4))
            marks[filename] = mark
            tk.Label(row, text=info["label"], bg=BG_CARD, fg=FG, font=("微软雅黑", 9),
                     anchor="w").pack(side="left", fill="x", expand=True)
            tk.Button(row, text="下载", bg=BG_CARD, fg=ACCENT, activebackground="#1d3150",
                      relief="flat", font=("微软雅黑", 9), padx=8,
                      command=lambda fn=filename: self._start_download(
                          win, fn, progressbar, status_var, cancel_btn, all_btn)).pack(side="right")

        # 底部：进度条 + 状态 + 一键全下 + 取消
        bottom = tk.Frame(win, bg=BG_CARD)
        bottom.pack(fill="x", padx=10, pady=(0, 8))
        progressbar = ttk.Progressbar(bottom, mode="determinate", maximum=100)
        progressbar.pack(fill="x", pady=(0, 4))
        status_var = tk.StringVar(value="就绪")
        tk.Label(bottom, textvariable=status_var, bg=BG_CARD, fg=FG_DIM, font=("微软雅黑", 8),
                 anchor="w").pack(fill="x")
        btn_row = tk.Frame(bottom, bg=BG_CARD)
        btn_row.pack(fill="x", pady=(6, 0))
        all_btn = tk.Button(btn_row, text="一键下载全部", bg=BTN, fg=BTN_FG, activebackground=BTN_HOVER,
                            relief="flat", font=("微软雅黑", 10, "bold"), padx=12,
                            command=lambda: self._start_download(
                                win, None, progressbar, status_var, cancel_btn, all_btn))
        all_btn.pack(side="left", expand=True, fill="x", padx=(0, 4))
        cancel_btn = tk.Button(btn_row, text="取消", bg=BG_CARD, fg=FG, activebackground="#1d3150",
                               relief="flat", font=("微软雅黑", 10), padx=12, state="disabled")
        cancel_btn.pack(side="right", expand=True, fill="x", padx=(4, 0))

        _refresh_marks()

        # 定位在按钮下方 + 关闭方式
        win.update_idletasks()
        x = btn.winfo_rootx()
        y = btn.winfo_rooty() + btn.winfo_height()
        pos = "+{}+{}".format(x, y)
        win.geometry(pos)
        win.after(0, lambda: win.geometry(pos))
        win.bind("<Map>", lambda e: win.geometry(pos))
        win.attributes("-topmost", True)
        win.focus_force()
        win.grab_set()
        win.bind("<FocusOut>", lambda e: win.destroy())
        win.bind("<Escape>", lambda e: win.destroy())

    def _start_download(self, win, filename, progressbar, status_var, cancel_btn, all_btn):
        """启动下载（filename=None 表示全部）。后台线程跑，进度/状态回主线程更新"""
        if self._downloading:
            self._log("（已有下载在进行中，请稍候…）", "err")
            return
        self._downloading = True
        cancel_event = threading.Event()
        cancel_btn.configure(state="normal", command=cancel_event.set)
        all_btn.configure(state="disabled")

        # 进度节流：百分比/每 MB 变化才回主线程更新，避免刷屏
        last = [None]

        def on_progress(done, total):
            key = (done * 100 // total) if total else (done // (1024 * 1024))
            if key != last[0]:
                last[0] = key
                self.root.after(0, lambda d=done, t=total: self._set_dl_progress(progressbar, status_var, d, t))

        def worker():
            try:
                if filename is None:
                    result = fetch_all_packages(progress_cb=on_progress, cancel_event=cancel_event)
                else:
                    result = fetch_package(filename, progress_cb=on_progress, cancel_event=cancel_event)
            except Exception as e:
                result = "× 下载出错：{}".format(e)
            self.root.after(0, self._finish_download, win, result, status_var, cancel_btn, all_btn)

        threading.Thread(target=worker, daemon=True).start()

    def _set_dl_progress(self, progressbar, status_var, done, total):
        """更新下载面板的进度条和状态文字"""
        def fmt(n):
            if n < 1024 * 1024:
                return "{:.0f} KB".format(n / 1024)
            return "{:.1f} MB".format(n / (1024 * 1024))
        if total:
            progressbar.configure(value=done * 100 // total)
            status_var.set("已下载 {} / {}（{}%）".format(fmt(done), fmt(total), done * 100 // total))
        else:
            status_var.set("已下载 {}".format(fmt(done)))

    def _finish_download(self, win, result, status_var, cancel_btn, all_btn):
        """下载结束：重置按钮、写日志（面板可能已被用户关闭，UI 操作要容错）"""
        self._downloading = False
        try:
            cancel_btn.configure(state="disabled")
            all_btn.configure(state="normal")
            status_var.set("下载结束（结果见右侧日志）")
        except Exception:
            pass  # 面板已关闭，忽略
        for line in result.split("\n"):
            if line.startswith("√"):
                self._log(line, "ok")
            elif line.startswith("×"):
                self._log(line, "err")
            else:
                self._log(line)

    def _dead_pixel_test(self):
        """屏幕坏点检测：全屏铺纯色（红/绿/蓝/白/黑），把坏点衬出来让肉眼找。

        软件读不到每个像素的物理状态，只能靠纯色背景把「常亮/常灭」的坏点显出来，
        这是所有坏点检测工具的通用做法。单击/空格/→ 换色，Esc 或右键退出。
        """
        win = tk.Toplevel(self.root)
        win.overrideredirect(True)
        win.attributes("-topmost", True)
        win.geometry("{}x{}+0+0".format(win.winfo_screenwidth(), win.winfo_screenheight()))

        # (颜色名, 背景色, 提示文字色) —— 黑底用白字，其余用黑字，保证角落提示始终看得清
        states = [
            ("红", "#ff0000", "#ffffff"),
            ("绿", "#00ff00", "#000000"),
            ("蓝", "#0000ff", "#ffffff"),
            ("白", "#ffffff", "#000000"),
            ("黑", "#000000", "#ffffff"),
        ]
        idx = [0]

        lbl = tk.Label(win, font=("微软雅黑", 15, "bold"), padx=14, pady=8)
        lbl.place(x=24, y=24)

        def show(i):
            name, bg, fg = states[i]
            win.configure(bg=bg)
            lbl.configure(bg=bg, fg=fg,
                          text="{} {}/{}　单击换色　Esc 退出".format(name, i + 1, len(states)))

        def next_color(event=None):
            idx[0] = (idx[0] + 1) % len(states)
            show(idx[0])

        show(0)
        win.bind("<Button-1>", next_color)
        win.bind("<space>", next_color)
        win.bind("<Right>", next_color)
        win.bind("<Escape>", lambda e: win.destroy())
        win.bind("<Button-3>", lambda e: win.destroy())
        win.focus_force()

    def _show_pause_menu(self):
        """在「暂停更新」按钮旁弹出时长列表（带右上角 ×）"""
        options = [
            ("7 天", 7), ("30 天", 30), ("90 天", 90),
            ("1 年", 365), ("10 年", 3650), ("100 年", 36500), ("500 年", 182500),
        ]
        items = [("{}".format(lbl), lambda d=d: self._do_pause(d)) for lbl, d in options]
        self._popup_panel(self.pause_btn, "暂停更新时长", items)

    def _show_variant_menu(self, kind, btn):
        """点安装按钮后弹出「Win7 适配版 / Win10+ 高版本 / 手动安装 / 卸载」面板"""
        title = KIND_TITLES.get(kind, kind)
        items = []
        for variant, (filename, label, version_label) in INSTALL_VARIANTS.get(kind, {}).items():
            items.append((label, lambda v=variant, vl=version_label: self._run_install(
                "安装 {}".format(vl), self._todo_install, kind, v)))
        items.append(("手动安装（自己选版本和路径）", lambda k=kind, b=btn: self._do_manual_install(k, None, b)))
        if kind == "python":
            # Python 能装多个版本，卸载要能选版本
            items.append(("卸载 Python（选版本）", lambda b=btn: self._do_uninstall_python(b)))
        else:
            items.append(("卸载 {}".format(title), lambda k=kind: self._confirm_uninstall(k)))
        self._popup_panel(btn, title, items)

    def _do_manual_install(self, kind, variant=None, anchor_btn=None):
        """非一键安装：先选版本，再自己选路径（zip）或打开安装器（exe/msi）。"""
        title = KIND_TITLES.get(kind, kind)
        if variant is None:
            # 第一步：选版本
            options = []
            for v, (fn, label, vl) in INSTALL_VARIANTS.get(kind, {}).items():
                options.append((label, (lambda vv=v: self._do_manual_install(kind, vv, anchor_btn))))
            self._popup_panel(anchor_btn, "选择要手动安装的 {} 版本".format(title), options)
            return
        version_label = INSTALL_VARIANTS[kind][variant][2]
        if kind in _ZIP_KINDS:
            target = filedialog.askdirectory(
                parent=self.root,
                title="选择 {}（{}）的安装目录（将解压到这个文件夹里）".format(title, version_label))
            if not target:
                return
            self._run("手动安装 {}（{}，解压到 {}）".format(title, version_label, target),
                      manual_install, kind, variant, target)
        else:
            self._run("手动安装 {}（{}）".format(title, version_label), manual_install, kind, variant)

    def _do_pause(self, days):
        label_map = {7: "7 天", 30: "30 天", 90: "90 天", 365: "1 年",
                     3650: "10 年", 36500: "100 年", 182500: "500 年"}
        label = label_map.get(days, "{} 天".format(days))
        self._run("暂停更新（{}）".format(label), pause_windows_update, days)

    def _show_move_menu(self):
        """在「移到 D 盘」按钮旁弹出分项面板：下载 / 桌面 / 文档 / 全部"""
        options = [
            ("下载 移到 D 盘", "downloads"),
            ("桌面 移到 D 盘", "desktop"),
            ("文档 移到 D 盘", "documents"),
            ("全部 移到 D 盘", "all"),
        ]
        items = [(lbl, lambda w=which: self._do_move(w)) for lbl, which in options]
        self._popup_panel(self.move_btn, "移到 D 盘（选一项）", items)

    def _do_move(self, which):
        label = {"downloads": "下载", "desktop": "桌面",
                 "documents": "文档", "all": "下载+桌面+文档"}.get(which, which)
        # 危险操作先警告：说明后果，让用户确认后再执行
        if not messagebox.askyesno(
                "危险操作确认",
                "「{} 移到 D 盘」会移动 Windows 用户文件夹并改注册表路径，存在风险：\n\n"
                "· 若文件正被占用（游戏、浏览器等开着），可能搬不干净；\n"
                "· 移动后桌面图标可能重排，部分程序会找不到原路径；\n"
                "· 若没搬干净，本工具会保留原路径、不会强行改，但建议先关掉占用这些文件夹的程序再操作。\n\n"
                "确定要继续吗？".format(label),
                parent=self.root):
            return
        self._run("{} 移到 D 盘".format(label), move_folders_to_d, which)

    def _do_clean_temp(self):
        """清理临时文件/回收站前先警告（清空回收站不可逆）"""
        if not messagebox.askyesno(
                "危险操作确认",
                "将清理系统临时文件并清空回收站：\n\n"
                "· 清空回收站后，回收站里的文件无法恢复；\n"
                "· 临时文件清理一般安全，但个别正在用的程序可能暂时报错。\n\n"
                "确定要继续吗？",
                parent=self.root):
            return
        self._run("清理临时文件", clean_temp_files)

    def _do_config_remote(self):
        """配置远程桌面前先警告（会修改系统服务 TermService 的配置）"""
        if not messagebox.askyesno(
                "危险操作确认",
                "将用 RDPWrap 修改系统「远程桌面」服务（TermService）的配置：\n\n"
                "· 需要匹配当前 Windows 的 termsrv.dll 版本，版本不符可能导致远程桌面异常；\n"
                "· 若检测到本机已有远程配置，会自动跳过、不做改动。\n\n"
                "确定要继续吗？",
                parent=self.root):
            return
        self._run("配置远程桌面", configure_remote)

    def _detect_all(self):
        return "\n".join([
            detect_windows(),
            detect_windows_update(),
            detect_edge_update(),
            detect_remote(),
            detect_python(),
            detect_gcc(),
            detect_java(),
            detect_node(),
            detect_git(),
            detect_vscode(),
        ])

    def _todo_install(self, kind, variant):
        installer = INSTALLERS.get(kind)
        if installer is None:
            return "× 未知的安装项：{}".format(kind)
        if not is_admin():
            return "× 需要管理员权限，请点右上角的「以管理员身份重启」后再安装。"
        return installer(variant)

    def _confirm_uninstall(self, kind):
        """卸载前弹确认框（卸载不可逆），确认后后台执行"""
        title = KIND_TITLES.get(kind, kind)
        if not messagebox.askyesno(
                "确认卸载", "确定要卸载 {} 吗？\n此操作会移除已安装的 {}，且不可撤销。".format(title, title),
                parent=self.root):
            return
        self._run_install("卸载 {}".format(title), self._todo_uninstall, kind)

    def _todo_uninstall(self, kind):
        uninstaller = UNINSTALLERS.get(kind)
        if uninstaller is None:
            return "× 未知的卸载项：{}".format(kind)
        if not is_admin():
            return "× 需要管理员权限，请点右上角的「以管理员身份重启」后再卸载。"
        return uninstaller()

    def _do_uninstall_python(self, anchor_btn):
        """卸载 Python：先枚举已装版本，0 个提示 / 1 个直接确认卸 / 多个弹菜单选"""
        installs = _list_python_installs()
        if not installs:
            messagebox.showinfo(
                "卸载 Python",
                "没找到可以一键卸载的 Python。\n\n"
                "如果你是用「手动安装（自己选路径）」装的、选了自定义位置，"
                "一键卸载找不到它，需要你自己到装的位置手动删除。\n\n"
                "请到「控制面板 → 程序和功能」或你当初选的安装目录手动处理。",
                parent=self.root)
            return
        if len(installs) == 1:
            self._confirm_uninstall_python(installs[0][0])
        else:
            options = [(d or v or "Python", (lambda dd=d: self._confirm_uninstall_python(dd)))
                       for d, v, q, u in installs]
            self._popup_panel(anchor_btn, "选择要卸载的 Python 版本", options)

    def _confirm_uninstall_python(self, display):
        """卸载指定 Python 版本前弹确认框"""
        if not messagebox.askyesno(
                "确认卸载", "确定要卸载 {} 吗？\n此操作会移除该版本的 Python，且不可撤销。".format(display),
                parent=self.root):
            return
        self._run_install("卸载 {}".format(display), uninstall_python, display)


def main():
    # 高分屏清晰化
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception:
        pass
    root = tk.Tk()
    ToolboxApp(root)
    enable_dark_titlebar(root)
    root.mainloop()


if __name__ == "__main__":
    main()
