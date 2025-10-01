import sys

# Check Python version before importing other modules
if sys.version_info < (3, 9):
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"Error: Current Python version is {current_version}")
    print("This program requires Python 3.9 or higher to run")
    print("Please upgrade your Python installation")
    sys.exit(1)

import asyncio
import datetime as dt
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from playwright.async_api import TimeoutError, async_playwright

# ==== Configurable Section ====
NAME = "your name"
TIMEZONE = "Asia/Taipei"
FORMS_URL_FILE = "forms_url.txt"
DATE_FILE = "date.txt"
HEADLESS = False
NAV_TIMEOUT_MS = 40_000
ACTION_TIMEOUT_MS = 20_000
MAX_RETRIES_PER_FORM = 2  # Total attempts: 2 times (first attempt + 1 retry)
RETRY_BACKOFF_SECONDS = [3]  # Wait 3 seconds after first failure before retry

# Form submission timeout settings
SUBMIT_WARNING_TIMEOUT_SEC = 10  # Send warning email if no redirect within 10 seconds
SUBMIT_KILL_TIMEOUT_SEC = 20     # Mark as failure if no redirect within 20 seconds

# Screenshot settings
SCREENSHOT_DIR = "fail_img"  # Directory for failure screenshots

# Chinese weekday to index mapping (Monday=0, ..., Sunday=6)
WEEKDAY_MAP: Dict[str, int] = {
    "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6
}

# Weekday index to English name mapping (capitalized)
WEEKDAY_EN: Dict[int, str] = {
    0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
    4: "Friday", 5: "Saturday", 6: "Sunday"
}

# Keywords for vacation options
VACATION_KEYWORDS = [
    r"休假", r"請假", r"不出勤", r"放假", r"vacation", r"leave", r"off",
]

SUBMIT_BTN_PATTERNS = [
    r"送出", r"提交", r"提交表單", r"Submit", r"Send", r"回覆", r"確定", r"Next", r"下一步"
]

# ---- Timezone utilities ----
try:
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # Python 3.9+
except Exception:
    ZoneInfo = None  # type: ignore
    ZoneInfoNotFoundError = Exception  # type: ignore


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


async def check_form_closed(page) -> bool:
    """
    Check if form is closed (displays "not accepting responses")
    Returns True if form is closed
    """
    try:
        # Try to find closed form indicators
        closed_patterns = [
            "不接受回應",
            "不再接受回應",
            "已停止接受回應",
            "停止接受回應",
            "不接受填寫",
            "已關閉",
            "劃假已滿，如有相關問題可聯繫班次主管與排班組。"
        ]
        
        for pattern in closed_patterns:
            try:
                element = page.get_by_text(pattern)
                if await element.count() > 0:
                    print(f"偵測到表單已關閉: 找到「{pattern}」字樣")
                    return True
            except Exception:
                continue
        
        return False
    except Exception:
        return False


def load_requested_weekdays(path: str = DATE_FILE) -> List[str]:
    """
    Load weekdays from date.txt
    Format example: 三、四、六
    Returns: ["三", "四", "六"]
    """
    p = Path(path)
    if not p.exists():
        print(f"警告: 找不到 {path}, 視為無需填寫")
        return []
    raw_text = p.read_text(encoding="utf-8").strip()
    if not raw_text:
        return []
    return [token.strip() for token in raw_text.split("、") if token.strip()]


def load_form_urls(path: str = FORMS_URL_FILE) -> List[str]:
    """
    Load form URLs from forms_url.txt, must contain exactly 7 lines for Monday to Sunday
    """
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"找不到 {path}（需包含 7 行 URL，週一→週日）")
    lines = [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(lines) != 7:
        raise ValueError("forms_url 檔應包含 **7 行**，對應星期一到星期日的網址。")
    return lines


def validate_execution_time() -> None:
    """
    Display current time and check if it's Wednesday 14:00 (Taiwan time)
    """
    tz = get_tz()
    now = dt.datetime.now(tz)
    weekday_name = ["一", "二", "三", "四", "五", "六", "日"][now.weekday()]
    print(f"目前時間 ({TIMEZONE}): {now:%Y-%m-%d %H:%M:%S}, 星期{weekday_name}")
    if now.weekday() != 2:
        print("提醒: 今天不是星期三")
    if now.hour != 14 or now.minute != 0:
        print("提醒: 現在不是下午兩點整")


async def wait_network_quiet(page, quiet_ms: int = 1500, total_ms: int = 10_000):
    """
    Helper function: wait for network to be quiet for stability
    """
    try:
        await page.wait_for_load_state("networkidle", timeout=total_ms)
    except TimeoutError:
        # Some forms have long connections, fallback to timeout
        await page.wait_for_timeout(quiet_ms)


# === Form DOM operations ===

async def robust_fill_name(page, name: str) -> None:
    # Fill name input using various DOM selector strategies
    candidates = [
        "input.whsOnd[aria-labelledby]",          # Most precise (DOM)
        "input.whsOnd",                            # Second most precise
        "input[aria-label='姓名']",
        "input[aria-labelledby*='姓名']",
        "input[role='textbox']",
        "div[role='textbox']",
    ]

    for sel in candidates:
        try:
            loc = page.locator(sel).first
            await loc.click(timeout=8_000)
            await loc.fill(name, timeout=8_000)
            return
        except Exception:
            continue

    # Text anchor method as fallback
    try:
        label = page.get_by_text(r"^\s*姓名\s*$", exact=True)
        input_el = label.locator("xpath=..").locator("xpath=following::input[@type='text'][1]")
        await input_el.fill(name, timeout=8_000)
        return
    except Exception:
        pass

    raise RuntimeError("找不到『姓名』輸入框")


async def ensure_form_ready(page) -> None:
    # Wait for Google Form main body to load
    await page.wait_for_selector("form", timeout=15_000)
    # Wait for any common input field to appear
    await page.wait_for_selector("input.whsOnd, input[role='textbox'], div[role='textbox']", timeout=15_000)


async def robust_check_vacation(page) -> None:
    # Click vacation radio button directly without artificial delays
    try:
        await page.locator("[role='radio'][aria-label*='休假']").first.click(timeout=8_000)
        return
    except Exception:
        pass
    try:
        await page.locator("[role='radio'][data-value*='休假']").first.click(timeout=8_000)
        return
    except Exception:
        pass
    try:
        await page.locator("[role='radio']:has-text('休假')").first.click(timeout=8_000)
        return
    except Exception:
        pass
    try:
        await page.locator("span.aDTYNe.snByac:has-text('休假')").first.click(timeout=8_000)
        return
    except Exception:
        pass

    raise RuntimeError("找不到『休假』單選選項。")


async def robust_submit(page, weekday_name: str = "未知") -> None:
    """
    Submit form and monitor redirect status
    
    Overview:
    This function implements a two-stage timeout monitoring mechanism to ensure form submission reliability
    After form submission, Google Forms typically redirects to success page (formResponse) within seconds
    If network is abnormal or server responds slowly, it may cause long waiting time without response
    
    Two-stage mechanism:
    Stage 1: First 10 seconds after clicking submit
      - If redirect succeeds within 10 seconds -> considered success, function returns immediately
      - If no redirect within 10 seconds -> send warning email, proceed to stage 2
    
    Stage 2: 11-20 seconds
      - If redirect succeeds in these 10 seconds -> considered success (slower but still valid)
      - If still no redirect within 20 seconds -> considered failure, raise RuntimeError
    
    Design rationale:
    1. 10 seconds is reasonable network response time, exceeding may indicate issues
    2. 20 seconds is maximum tolerable wait time, avoid program hanging indefinitely
    3. Warning email lets user know potential issues early
    4. After failure, retry mechanism (submit_form_with_retry) decides whether to retry
    
    Parameters:
      page: Playwright Page object
      weekday_name: Weekday name (e.g. "一", "二"), used for logging and notification
    
    Raises:
      RuntimeError: When redirect fails within 20 seconds
    """
    from send_mail import send_warning_email
    
    # Step 1: Find and click submit button
    # Google Forms submit button may have various DOM structures, try in order
    btn_candidates = [
        "div[role='button']:has-text('提交')",
        "div[role='button']:has-text('送出')",
        "div[role='button']:has-text('Submit')",
        "div[role='button'] >> text=提交",
        "div[role='button'] >> text=送出",
        "div[role='button'] >> text=Submit",
    ]

    clicked = False
    for sel in btn_candidates:
        try:
            await page.locator(sel).first.click(timeout=8_000)
            clicked = True
            break
        except Exception:
            continue

    # If all above selectors fail, try last fallback selector
    if not clicked:
        try:
            await page.locator("span.NPEfkd.RveJvd.snByac:has-text('提交')").first.click(timeout=8_000)
            clicked = True
        except Exception:
            pass

    # If all attempts fail, submit button not found (possibly form structure changed)
    if not clicked:
        raise RuntimeError("找不到『提交/送出』按鈕")

    # Step 2: Stage 1 - Monitor redirect status in first 10 seconds
    # 
    # Explanation:
    # After successful Google Forms submission, URL changes from /viewform to one of:
    #   1. /formResponse - Most common success page
    #   2. /thankyou - Custom thank you page
    #   3. /viewform?edit2=... - Page allowing edit response
    # 
    # We use regex to match these URL patterns
    # timeout parameter is in milliseconds, so SUBMIT_WARNING_TIMEOUT_SEC * 1000
    # 
    # Execution flow:
    # - Start waiting for URL change
    # - If URL matches success pattern within 10 seconds -> exit try, execute return
    # - If still no match after 10 seconds -> trigger TimeoutError, enter except block
    try:
        await page.wait_for_url(
            re.compile(r"formResponse|/thankyou|/viewform\?edit2=.*"), 
            timeout=SUBMIT_WARNING_TIMEOUT_SEC * 1000
        )
        # Success case: redirect successful within 10 seconds, function returns here
        return
    except TimeoutError:
        # Timeout case: no redirect to success page within 10 seconds
        # We think there may be issues, but don't directly mark as failure, send warning instead
        print(f"警告: 星期{weekday_name}表單在10秒內未轉跳, 發送警告郵件...")
        
        # Try to send warning email
        # Use try-except to ensure even if email fails, it won't affect subsequent judgment
        try:
            await send_warning_email(weekday_name)
        except Exception as mail_err:
            # Email failure only logged, doesn't interrupt flow
            print(f"警告: 發送警告郵件失敗: {mail_err}")
    
    # Step 3: Stage 2 - Give 10 seconds grace period (20 seconds total)
    # 
    # Explanation:
    # Reaching here means first 10 seconds timed out, but we give additional 10 seconds
    # This is because in some cases (temporary network instability, high server load),
    # longer time may be needed to complete submission
    # 
    # timeout calculation:
    # (SUBMIT_KILL_TIMEOUT_SEC - SUBMIT_WARNING_TIMEOUT_SEC) * 1000
    # Example: (20 - 10) * 1000 = 10000 milliseconds = 10 seconds
    # 
    # Execution flow:
    # - Continue waiting for URL change, wait up to 10 more seconds
    # - If redirect succeeds in these 10 seconds -> execute return (slower but still considered success)
    # - If still no success after these 10 seconds -> trigger TimeoutError, mark as failure
    try:
        await page.wait_for_url(
            re.compile(r"formResponse|/thankyou|/viewform\?edit2=.*"), 
            timeout=(SUBMIT_KILL_TIMEOUT_SEC - SUBMIT_WARNING_TIMEOUT_SEC) * 1000
        )
        # Delayed success case: redirect successful in 11-20 seconds
        # Slower than expected, but still considered valid submission
        print(f"提示: 星期{weekday_name}表單在第11-20秒間成功轉跳 (回應較慢)")
        return
    except TimeoutError:
        # Complete failure case: still no redirect after waiting total of 20 seconds
        # Now we mark submission as failure, raise RuntimeError
        # 
        # Subsequent handling:
        # This exception will be caught by submit_single_form,
        # then submit_form_with_retry decides whether to retry (max 2 times)
        raise RuntimeError(f"星期{weekday_name}表單提交失敗: 20秒內未轉跳到成功頁面")


# === Single page handling: fill name + check vacation simultaneously, then submit ===
async def submit_single_form(context, url: str, weekday_name: str = "未知", weekday_idx: int = 0) -> Optional[str]:
    """
    Submit single form
    
    Returns:
      None: Success
      str: Screenshot path if failed
    """
    page = await context.new_page()
    page.set_default_navigation_timeout(NAV_TIMEOUT_MS)  # Sync API, don't await
    page.set_default_timeout(ACTION_TIMEOUT_MS)          # Sync API, don't await

    screenshot_path = None
    try:
        print(f"開啟表單: {url}")
        await page.goto(url, wait_until="domcontentloaded")
        await ensure_form_ready(page)

        # Fill name & check vacation simultaneously (no artificial waits)
        await asyncio.gather(
            robust_fill_name(page, NAME),
            robust_check_vacation(page)
        )

        # Submit after completion
        await robust_submit(page, weekday_name)
        print(f"成功: 星期{weekday_name}表單已送出")
        return None  # Success
        
    except Exception as e:
        # When error occurs, check if form is closed
        print(f"錯誤: 星期{weekday_name}表單填寫失敗: {e}")
        
        # Check if "not accepting responses" text exists
        is_closed = await check_form_closed(page)
        
        # Screenshot on failure regardless of "not accepting responses" detection
        # (Because element may not be found but page hasn't fully loaded)
        try:
            screenshot_path = await take_screenshot(page, weekday_idx)
            print(f"已儲存失敗截圖: {screenshot_path}")
        except Exception as screenshot_err:
            print(f"截圖失敗: {screenshot_err}")
        
        if is_closed:
            print(f"原因: 表單已關閉 (不接受回應)")
        
        # Re-raise exception for retry mechanism to handle
        raise
        
    finally:
        await page.close()
        
    return screenshot_path


async def submit_form_with_retry(context, url: str, weekday_name: str = "未知", weekday_idx: int = 0) -> Tuple[bool, Optional[str], Optional[str]]:
    """
    Retry form submission
    
    Description:
    Total attempts: MAX_RETRIES_PER_FORM times (set to 2)
    On first failure:
      1. Auto screenshot (done in submit_single_form)
      2. Immediately send failure notification email (with screenshot)
      3. Wait then proceed to second attempt
    
    Returns:
      (success status, screenshot path, error message)
    """
    from send_mail import send_immediate_failure_email
    
    last_err: Optional[Exception] = None
    first_screenshot_path: Optional[str] = None
    first_failure_notified = False
    
    for attempt, delay in enumerate([0] + RETRY_BACKOFF_SECONDS, start=1):
        if delay > 0:
            print(f"等待 {delay} 秒後重試...")
            await asyncio.sleep(delay)
        
        try:
            print(f"嘗試第 {attempt} 次（共 {MAX_RETRIES_PER_FORM} 次）")
            result = await submit_single_form(context, url, weekday_name, weekday_idx)
            # 成功時 result 為 None
            return (True, None, None)
            
        except Exception as e:
            last_err = e
            print(f"第 {attempt} 次失敗：{e}")
            
            # 第一次失敗時立即發送郵件
            # 注意：submit_single_form 已經在失敗時自動截圖
            if attempt == 1 and not first_failure_notified:
                # 確認是否已有截圖
                # submit_single_form 在失敗時會截圖並儲存
                # 我們需要取得那個截圖的路徑
                # 截圖檔名格式：西元年-月-日-星期幾.png
                ensure_screenshot_dir()
                screenshot_filename = get_screenshot_filename(weekday_idx)
                potential_screenshot_path = Path(SCREENSHOT_DIR) / screenshot_filename
                
                if potential_screenshot_path.exists():
                    first_screenshot_path = str(potential_screenshot_path)
                    print(f"找到第一次失敗的截圖：{first_screenshot_path}")
                
                # 發送立即失敗通知
                try:
                    await send_immediate_failure_email(
                        weekday_name=weekday_name,
                        url=url,
                        screenshot_path=first_screenshot_path,
                        error_msg=str(e)
                    )
                    first_failure_notified = True
                    print(f"已發送第一次失敗通知郵件（星期{weekday_name}）")
                except Exception as mail_err:
                    print(f"發送失敗通知郵件時出錯：{mail_err}")
    
    # 所有嘗試都失敗
    return (False, first_screenshot_path, str(last_err))


# === 精準等待工具 ===

def next_wed_14_taipei(now: Optional[dt.datetime] = None) -> dt.datetime:
    """取得『當週的星期三 14:00』；若當下已超過該時間，則回傳『下一週的星期三 14:00』。"""
    tz = get_tz()
    if now is None:
        now = dt.datetime.now(tz)

    # 週一=0, 週三=2
    today_wd = now.weekday()
    days_to_wed = (2 - today_wd) % 7
    target = (now + dt.timedelta(days=days_to_wed)).replace(hour=14, minute=0, second=0, microsecond=0)

    if target <= now:
        target = target + dt.timedelta(days=7)
    return target


async def precise_sleep_until(target: dt.datetime) -> None:
    """
    使用單調時鐘做『非常精準』等待到 target（aware datetime）。
    先粗睡到 60 秒前，再進入 1 秒粒度，最後毫秒級收斂。
    """
    tz = get_tz()
    assert target.tzinfo is not None, "target 必須為帶時區的 datetime"

    def now_tz():
        return dt.datetime.now(tz)

    while True:
        now = now_tz()
        delta = (target - now).total_seconds()
        if delta <= 0:
            return
        if delta > 60:
            await asyncio.sleep(min(delta - 60, 300))  # 最多 5 分鐘一步
        elif delta > 1:
            await asyncio.sleep(delta - 1)
        else:
            await asyncio.sleep(max(delta, 0.001))


def prompt_schedule_choice() -> tuple[str, Optional[int]]:
    """
    啟動互動式詢問：
      1) 等當週三14:00？(y/n)
         - y => mode="wed"
         - n => 2) 馬上執行？(y/n)
                  - y => mode="now"
                  - n => 3) 等幾分鐘（正整數）？ => mode="delay", minutes=N
    回傳:
      ("wed", None) | ("now", None) | ("delay", 分鐘數)
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


# === 新增：每個 URL 用「獨立瀏覽器」執行 ===
async def run_in_isolated_browser(p, url: str, weekday_idx: int) -> Tuple[int, bool, Optional[str], Optional[str]]:
    """
    為每個表單開『獨立』瀏覽器（非分頁），獨立 context，送出後關閉。
    回傳：(weekday_idx, 是否成功, 截圖路徑, 錯誤訊息)
    """
    weekday_name = "一二三四五六日"[weekday_idx]
    browser = await p.chromium.launch(headless=HEADLESS)
    context = await browser.new_context()
    
    try:
        success, screenshot_path, error_msg = await submit_form_with_retry(context, url, weekday_name, weekday_idx)
        return (weekday_idx, success, screenshot_path, error_msg)
    finally:
        await context.close()
        await browser.close()


def compute_target_indices_and_urls() -> Tuple[List[int], List[str]]:
    """
    先讀取 date.txt 與 forms_url 檔，計算要填的星期索引與 URL 陣列。
    回傳：
      target_indices（已去重、排序）,
      form_urls（7 列）
    """
    requested_days = load_requested_weekdays(DATE_FILE)
    if not requested_days:
        print("提示：date.txt 無內容或不存在，沒有需要填寫的日期，程式結束。")
        return [], []

    try:
        form_urls = load_form_urls(FORMS_URL_FILE)
    except Exception as e:
        print(f"錯誤：讀取 {FORMS_URL_FILE} 失敗：{e}")
        return [], []

    # 中文星期 -> 索引
    indices: List[int] = []
    for token in requested_days:
        if token not in WEEKDAY_MAP:
            print(f"警告：無法辨識的星期：{token}，略過。")
            continue
        idx = WEEKDAY_MAP[token]
        if idx not in indices:
            indices.append(idx)

    indices.sort()
    if not indices:
        print("提示：沒有有效的星期可供填寫。")
        return [], []

    return indices, form_urls


async def main() -> None:
    # 互動式排程決策
    mode, minutes = prompt_schedule_choice()
    tz = get_tz()

    # 先「預算」要開的瀏覽器數量與對應星期（特別針對 mode == "wed" 的需求）
    target_indices, form_urls = compute_target_indices_and_urls()
    if not target_indices:
        return

    # 印出預計要開的瀏覽器數量與對應星期
    weekday_str = "、".join("一二三四五六日"[i] for i in target_indices)
    weekday_list = ["一二三四五六日"[i] for i in target_indices]
    print(f"預計要填的星期：{weekday_str}（共 {len(target_indices)} 個表單／瀏覽器）")

    if mode == "wed":
        from send_mail import send_reminder_email
        
        target = next_wed_14_taipei()
        now = dt.datetime.now(tz)
        wait_seconds = (target - now).total_seconds()
        
        print(f"將等待至（{TIMEZONE}）：{target:%Y-%m-%d %H:%M:%S}（週三 14:00）再執行...")
        
        # 如果等待時間超過5分鐘，則在執行前5分鐘發送提醒
        if wait_seconds > 300:  # 300秒 = 5分鐘
            reminder_time = target - dt.timedelta(minutes=5)
            print(f"提示：將在 {reminder_time:%Y-%m-%d %H:%M:%S} 發送提醒郵件（執行前5分鐘）")
            
            # 等待到提醒時間
            await precise_sleep_until(reminder_time)
            
            # 發送提醒郵件
            try:
                await send_reminder_email(weekday_list)
                print("已發送執行前提醒郵件")
            except Exception as mail_err:
                print(f"發送提醒郵件失敗：{mail_err}")
            
            # 繼續等待剩餘的5分鐘
            await precise_sleep_until(target)
        else:
            # 等待時間不足5分鐘，直接等待
            await precise_sleep_until(target)
            
    elif mode == "delay":
        start = dt.datetime.now(tz)
        target = start + dt.timedelta(minutes=minutes or 0)
        print(f"將等待 {minutes} 分鐘，目標時間（{TIMEZONE}）：{target:%Y-%m-%d %H:%M:%S}")
        await precise_sleep_until(target)
    else:
        print("立即執行。")

    # 僅提醒目前時間（不阻擋）
    validate_execution_time()

    # ---- Playwright 啟動（多瀏覽器併行）----
    from send_mail import send_summary_email
    
    results = []  # 收集所有結果：[(weekday_idx, success, error_msg), ...]
    
    async with async_playwright() as p:
        # 若只有一個日期：仍然是開「一個瀏覽器」（也是獨立）
        if len(target_indices) == 1:
            idx = target_indices[0]
            url = form_urls[idx]
            print(f"\n=== 星期索引 {idx}（{'一二三四五六日'[idx]}） → 開 1 個瀏覽器 ===")
            result = await run_in_isolated_browser(p, url, idx)
            results.append(result)
        else:
            # 多個日期：為每個 URL 開一個「獨立瀏覽器」，同時執行
            tasks = []
            for idx in target_indices:
                url = form_urls[idx]
                print(f"\n=== 星期索引 {idx}（{'一二三四五六日'[idx]}） → 開獨立瀏覽器 ===")
                tasks.append(asyncio.create_task(run_in_isolated_browser(p, url, idx)))

            results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # 記錄執行結束時間
    end_time = dt.datetime.now(tz)
    
    # ---- 統計結果 ----
    print("\n" + "=" * 50)
    print("執行結果統計")
    print("=" * 50)
    
    success_list = []
    failure_list = []
    failure_screenshots = []  # 收集失敗的截圖路徑
    
    # 建立星期索引到URL的映射
    weekday_url_map = {idx: form_urls[idx] for idx in target_indices}
    
    for result in results:
        if isinstance(result, Exception):
            print(f"發生未預期錯誤：{result}")
            continue
        
        weekday_idx, success, screenshot_path, error_msg = result
        weekday_name = "一二三四五六日"[weekday_idx]
        url = weekday_url_map.get(weekday_idx, "未知")
        
        if success:
            success_list.append(weekday_name)
            print(f"成功：星期{weekday_name}")
        else:
            failure_list.append((weekday_name, url, error_msg))
            if screenshot_path:
                failure_screenshots.append(screenshot_path)
            print(f"失敗：星期{weekday_name} - {error_msg}")
    
    print("=" * 50)
    print(f"總計：成功 {len(success_list)} 個，失敗 {len(failure_list)} 個")
    print("=" * 50)
    
    # ---- 發送總結郵件 ----
    try:
        await send_summary_email(
            success_list=success_list,
            failure_list=failure_list,
            end_time=end_time
        )
    except Exception as mail_err:
        print(f"發送總結郵件失敗：{mail_err}")

if __name__ == "__main__":
    asyncio.run(main())
