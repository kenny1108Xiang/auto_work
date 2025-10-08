"""
Screenshot utilities for capturing form errors
"""
import datetime as dt
from pathlib import Path

from config.settings import SCREENSHOT_DIR, WEEKDAY_EN, TIMEZONE

# Timezone utilities
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # Python 3.9+
except Exception:
    ZoneInfo = None
    ZoneInfoNotFoundError = Exception


def get_tz():
    """Get timezone, prefer ZoneInfo('Asia/Taipei'), fallback to UTC+8 if tzdata is missing"""
    if ZoneInfo is None:
        return dt.timezone(dt.timedelta(hours=8))
    try:
        return ZoneInfo(TIMEZONE)
    except ZoneInfoNotFoundError:
        return dt.timezone(dt.timedelta(hours=8))


def ensure_screenshot_dir():
    """Ensure screenshot directory exists"""
    Path(SCREENSHOT_DIR).mkdir(exist_ok=True)


def get_screenshot_filename(weekday_idx: int) -> str:
    """
    Generate screenshot filename
    Format: YYYY-MM-DD-Weekday.png
    Example: 2025-10-02-Thursday.png
    """
    tz = get_tz()
    now = dt.datetime.now(tz)
    weekday_en = WEEKDAY_EN[weekday_idx]
    return f"{now:%Y-%m-%d}-{weekday_en}.png"


async def take_screenshot(page, weekday_idx: int) -> str:
    """
    Take screenshot and save to fail_img directory
    Returns the full path of the screenshot
    """
    ensure_screenshot_dir()
    filename = get_screenshot_filename(weekday_idx)
    filepath = Path(SCREENSHOT_DIR) / filename
    
    await page.screenshot(path=str(filepath), full_page=True)
    print(f"已截圖: {filepath}")
    
    return str(filepath)

