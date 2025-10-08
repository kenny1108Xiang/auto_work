"""
Time scheduling utilities for precise execution timing
"""
import asyncio
import datetime as dt
from typing import Optional

from config.settings import TIMEZONE

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


def next_wed_14_taipei(now: Optional[dt.datetime] = None) -> dt.datetime:
    """Get next Wednesday 14:00, if already passed then get next week's Wednesday 14:00"""
    tz = get_tz()
    if now is None:
        now = dt.datetime.now(tz)

    # Monday=0, Wednesday=2
    today_wd = now.weekday()
    days_to_wed = (2 - today_wd) % 7
    target = (now + dt.timedelta(days=days_to_wed)).replace(hour=14, minute=0, second=0, microsecond=0)

    if target <= now:
        target = target + dt.timedelta(days=7)
    return target


async def precise_sleep_until(target: dt.datetime) -> None:
    """
    Precise sleep until target datetime using monotonic clock
    First sleep to 60 seconds before, then 1 second granularity, finally millisecond convergence
    """
    tz = get_tz()
    assert target.tzinfo is not None, "target must be timezone-aware datetime"

    def now_tz():
        return dt.datetime.now(tz)

    while True:
        now = now_tz()
        delta = (target - now).total_seconds()
        if delta <= 0:
            return
        if delta > 60:
            await asyncio.sleep(min(delta - 60, 300))  # Max 5 minutes per step
        elif delta > 1:
            await asyncio.sleep(delta - 1)
        else:
            await asyncio.sleep(max(delta, 0.001))


def validate_execution_time() -> None:
    """Display current time and check if it's Wednesday 14:00 (Taiwan time)"""
    tz = get_tz()
    now = dt.datetime.now(tz)
    weekday_name = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
    print(f"目前時間 ({TIMEZONE}): {now:%Y-%m-%d %H:%M:%S}, 星期{weekday_name}")
    if now.weekday() != 2:
        print("提醒: 今天不是星期三")
    if now.hour != 14 or now.minute != 0:
        print("提醒: 現在不是下午兩點整")


def prompt_schedule_choice() -> tuple[str, Optional[int]]:
    """
    Interactive schedule choice prompt
    Returns: ("wed", None) | ("now", None) | ("delay", minutes)
    """
    ans = input("要等到『當週的星期三下午 2 點』再執行嗎？(y/n)：").strip().lower()
    if ans == "y":
        return "wed", None

    ans2 = input("要『馬上』執行嗎？(y/n)：").strip().lower()
    if ans2 == "y":
        return "now", None

    while True:
        raw = input("請輸入要等待的『分鐘數』（正整數）：").strip()
        if raw.isdigit() and int(raw) > 0:
            return "delay", int(raw)
        print("錯誤：輸入無效，請輸入正整數。")


class Scheduler:
    """Handles scheduling and timing operations"""
    
    @staticmethod
    def get_timezone():
        return get_tz()
    
    @staticmethod
    def next_wednesday_14():
        return next_wed_14_taipei()
    
    @staticmethod
    async def sleep_until(target_time):
        await precise_sleep_until(target_time)
    
    @staticmethod
    def validate_time():
        validate_execution_time()
    
    @staticmethod
    def prompt_choice():
        return prompt_schedule_choice()

