"""
===============================================================================
KSH CHAT ENGINE - UI MODULE (ui.py)
-------------------------------------------------------------------------------
ИЗМЕНЕНИЯ И УЛУЧШЕНИЯ:
1. [Красная тема и логотип KSH]: Отрисовка красного градиентного ASCII логотипа KSH.
2. [Поддержка Windows]: Автоматическая активация режима Virtual Terminal.
3. [Код подключения KSH-XXXX]: Генератор и парсер единого кода подключения.
===============================================================================
"""

import sys
import os
import shutil
import base64
from datetime import datetime

# Windows Virtual Terminal Support
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


class Colors:
    """KSH Red Theme ANSI Palette."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    ITALIC = "\033[3m"
    UNDERLINE = "\033[4m"

    BLOOD_RED = "\033[38;2;255;20;20m"
    BRIGHT_RED = "\033[38;2;255;70;70m"
    CRIMSON = "\033[38;2;190;25;25m"
    DARK_RED = "\033[38;2;130;15;15m"
    CORAL = "\033[38;2;255;120;120m"

    GRAY = "\033[38;2;120;120;120m"
    DARK_GRAY = "\033[38;2;70;70;70m"
    WHITE = "\033[38;2;240;240;240m"
    PURE_WHITE = "\033[38;2;255;255;255m"
    GREEN = "\033[38;2;50;205;50m"
    YELLOW = "\033[38;2;255;215;0m"

    BG_DARK_RED = "\033[48;2;60;5;5m"
    BG_RED_HEADER = "\033[48;2;120;15;15m"


def get_terminal_width() -> int:
    try:
        return shutil.get_terminal_size().columns
    except Exception:
        return 80


def generate_join_code(ip: str, port: int, password: str, room: str = "global") -> str:
    """Encodes server connection parameters into a single shareable Join Code."""
    raw = f"{ip}:{port}:{password}:{room}"
    b64 = base64.urlsafe_b64encode(raw.encode('utf-8')).decode('ascii').rstrip('=')
    return f"KSH-{b64}"


def parse_join_code(code: str) -> tuple:
    """Decodes a shareable Join Code back into (host, port, password, room)."""
    code = code.strip()
    if code.startswith("KSH-"):
        code = code[4:]
    padding = len(code) % 4
    if padding:
        code += "=" * (4 - padding)
    try:
        raw = base64.urlsafe_b64decode(code.encode('ascii')).decode('utf-8')
        parts = raw.split(":", 3)
        if len(parts) == 4:
            return parts[0], int(parts[1]), parts[2], parts[3]
    except Exception:
        pass
    return None


def render_ksh_logo() -> str:
    """Returns the stylized KSH ASCII logo with red gradient coloring."""
    lines = [
        r"  ██╗  ██╗███████╗██╗  ██╗",
        r"  ██║ ██╔╝██╔════╝██║  ██║",
        r"  █████═╝ ███████╗███████║",
        r"  ██╔═██╗ ╚════██║██╔══██║",
        r"  ██║  ██╗███████║██║  ██║",
        r"  ╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝"
    ]
    
    gradient_colors = [
        Colors.BLOOD_RED,
        Colors.BRIGHT_RED,
        Colors.CORAL,
        Colors.BRIGHT_RED,
        Colors.CRIMSON,
        Colors.DARK_RED
    ]

    result = []
    for line, color in zip(lines, gradient_colors):
        result.append(f"{color}{Colors.BOLD}{line}{Colors.RESET}")
    return "\n".join(result)


def render_header(room_name: str, nickname: str, host: str, port: int, is_e2ee: bool = True, join_code: str = "") -> str:
    """Renders the top banner containing KSH logo, server info and join code."""
    width = min(get_terminal_width(), 90)
    logo = render_ksh_logo()
    
    border_color = Colors.CRIMSON
    top_line = border_color + "╔" + "═" * (width - 2) + "╗" + Colors.RESET
    bottom_line = border_color + "╚" + "═" * (width - 2) + "╝" + Colors.RESET

    status_e2ee = f"{Colors.GREEN}🔒 E2E ENCRYPTED{Colors.RESET}" if is_e2ee else f"{Colors.YELLOW}⚠️ UNENCRYPTED{Colors.RESET}"
    info_str = (
        f"{Colors.BOLD}{Colors.WHITE} ROOM:{Colors.RESET} {Colors.CORAL}{room_name}{Colors.RESET}  │  "
        f"{Colors.BOLD}{Colors.WHITE}USER:{Colors.RESET} {Colors.BRIGHT_RED}{nickname}{Colors.RESET}  │  "
        f"{Colors.BOLD}{Colors.WHITE}NODE:{Colors.RESET} {Colors.GRAY}{host}:{port}{Colors.RESET}  │  "
        f"{status_e2ee}"
    )

    out = []
    out.append(top_line)
    for line in logo.split('\n'):
        padding = max(0, (width - 2 - len(strip_ansi(line))) // 2)
        out.append(f"{border_color}║{Colors.RESET}{' ' * padding}{line}{' ' * max(0, width - 2 - padding - len(strip_ansi(line)))}{border_color}║{Colors.RESET}")
    
    # GitHub tagline
    tagline = f"{Colors.DARK_GRAY}github.com/CCGArima/ksh-chat{Colors.RESET}"
    t_pad = max(0, (width - 2 - len(strip_ansi(tagline))) // 2)
    out.append(f"{border_color}║{Colors.RESET}{' ' * t_pad}{tagline}{' ' * max(0, width - 2 - t_pad - len(strip_ansi(tagline)))}{border_color}║{Colors.RESET}")

    out.append(border_color + "╠" + "═" * (width - 2) + "╣" + Colors.RESET)
    
    info_pad = max(0, (width - 2 - len(strip_ansi(info_str))) // 2)
    out.append(f"{border_color}║{Colors.RESET}{' ' * info_pad}{info_str}{' ' * max(0, width - 2 - info_pad - len(strip_ansi(info_str)))}{border_color}║{Colors.RESET}")

    if join_code:
        code_str = f"{Colors.BOLD}{Colors.YELLOW}🔑 SHARE CODE FOR FRIENDS: {Colors.RESET}{Colors.PURE_WHITE}{Colors.BG_DARK_RED} {join_code} {Colors.RESET}"
        code_pad = max(0, (width - 2 - len(strip_ansi(code_str))) // 2)
        out.append(f"{border_color}║{Colors.RESET}{' ' * code_pad}{code_str}{' ' * max(0, width - 2 - code_pad - len(strip_ansi(code_str)))}{border_color}║{Colors.RESET}")

    out.append(bottom_line)

    return "\n".join(out)


def strip_ansi(text: str) -> str:
    """Strips ANSI escape codes to compute visible string length."""
    import re
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    return ansi_escape.sub('', text)


def format_message(sender: str, message: str, is_system: bool = False, is_pm: bool = False, my_nick: str = "") -> str:
    """Formats incoming chat messages with timestamps and red palette."""
    timestamp = datetime.now().strftime("%H:%M:%S")
    time_tag = f"{Colors.DARK_GRAY}[{timestamp}]{Colors.RESET}"

    if is_system:
        return f"{time_tag} {Colors.YELLOW}⚡ {Colors.BOLD}{message}{Colors.RESET}"

    if is_pm:
        return f"{time_tag} {Colors.BG_DARK_RED}{Colors.CORAL}🔒 [PRIVATE] {sender}:{Colors.RESET} {Colors.WHITE}{message}{Colors.RESET}"

    if sender == my_nick:
        sender_tag = f"{Colors.BOLD}{Colors.CORAL}[YOU]{Colors.RESET}"
    else:
        sender_tag = f"{Colors.BOLD}{Colors.BRIGHT_RED}[{sender}]{Colors.RESET}"

    return f"{time_tag} {sender_tag} {Colors.WHITE}{message}{Colors.RESET}"


def format_system_banner(title: str, body: str) -> str:
    """Formats a stylized red notice box."""
    width = min(get_terminal_width(), 80)
    b = Colors.CRIMSON
    top = f"{b}┌─ {Colors.BOLD}{Colors.BLOOD_RED}{title} {b}" + "─" * max(0, width - len(title) - 5) + "┐" + Colors.RESET
    mid = f"{b}│ {Colors.WHITE}{body}" + " " * max(0, width - len(strip_ansi(body)) - 3) + f"{b}│{Colors.RESET}"
    bot = f"{b}└" + "─" * (width - 2) + "┘" + Colors.RESET
    return f"\n{top}\n{mid}\n{bot}\n"
