"""
Clipboard Integration — Copy refined prompts to clipboard.
"""

from __future__ import annotations

import subprocess
import sys
from typing import Optional


def copy_to_clipboard(text: str) -> bool:
    """Copy text to system clipboard.

    Works on macOS, Linux (X11/Wayland), and Windows.
    """
    try:
        if sys.platform == "darwin":
            # macOS: use pbcopy
            subprocess.run(["pbcopy"], input=text.encode(), check=True)
            return True

        elif sys.platform == "win32":
            # Windows: use clip
            subprocess.run(["clip"], input=text.encode(), check=True)
            return True

        else:
            # Linux: try xclip, xsel, or wl-copy
            for cmd, args in [
                (["wl-copy"], []),  # Wayland
                (["xclip", "-selection", "clipboard"], []),
                (["xsel", "--clipboard", "--input"], []),
            ]:
                try:
                    subprocess.run(cmd + args, input=text.encode(), check=True)
                    return True
                except FileNotFoundError:
                    continue
            return False

    except subprocess.CalledProcessError:
        return False


def get_clipboard() -> Optional[str]:
    """Get text from system clipboard."""
    try:
        if sys.platform == "darwin":
            result = subprocess.run(["pbpaste"], capture_output=True, text=True)
            return result.stdout

        elif sys.platform == "win32":
            result = subprocess.run(["powershell", "-command", "Get-Clipboard"],
                                   capture_output=True, text=True)
            return result.stdout.strip()

        else:
            # Linux
            for cmd in ["wl-paste", "xclip -selection clipboard -o", "xsel --clipboard --output"]:
                try:
                    result = subprocess.run(cmd.split(), capture_output=True, text=True)
                    return result.stdout
                except FileNotFoundError:
                    continue
            return None

    except subprocess.CalledProcessError:
        return None


def clear_clipboard() -> bool:
    """Clear the system clipboard."""
    return copy_to_clipboard("")
