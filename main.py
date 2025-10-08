"""
Google Forms Auto-Fill Bot
Main entry point for the application
"""
import sys
import asyncio
import datetime as dt
from typing import List, Tuple
from playwright.async_api import async_playwright

# Check Python version before importing other modules
if sys.version_info < (3, 9):
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"Error: Current Python version is {current_version}")
    print("This program requires Python 3.9 or higher to run")
    print("Please upgrade your Python installation")
    sys.exit(1)

from config.settings import WEEKDAY_MAP
from utils.config_loader import get_config_loader
from core.scheduler import Scheduler, get_tz
from core.browser_manager import BrowserManager
from notifications.email_service import EmailService


def compute_target_indices_and_urls() -> Tuple[List[int], List[str]]:
    """
    Load config.json and compute target weekday indices and URLs
    Returns: (target_indices (deduplicated and sorted), form_urls (7 lines))
    """
    config_loader = get_config_loader()
    
    try:
        requested_days = config_loader.get_weekdays()
    except Exception as e:
        print(f"錯誤：讀取配置失敗：{e}")
        return [], []
    
    if not requested_days:
        print("提示：config.json 中沒有設定要填寫的日期，程式結束。")
        return [], []

    try:
        form_urls = config_loader.get_form_urls()
    except Exception as e:
        print(f"錯誤：讀取表單 URL 失敗：{e}")
        return [], []

    # Convert Chinese weekday to index
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
    """Main application entry point"""
    # Interactive schedule choice
    scheduler = Scheduler()
    mode, minutes = scheduler.prompt_choice()
    tz = get_tz()

    # Compute target indices and URLs
    target_indices, form_urls = compute_target_indices_and_urls()
    if not target_indices:
        return

    # Display execution plan
    weekday_str = "、".join("一二三四五六日"[i] for i in target_indices)
    weekday_list = ["一二三四五六日"[i] for i in target_indices]
    print(f"預計要填的星期：{weekday_str}（共 {len(target_indices)} 個表單／瀏覽器）")

    # Load and validate reason mapping from config.json
    config_loader = get_config_loader()
    config_loader.validate_reasons(weekday_list)
    reason_map = config_loader.get_reasons()
    
    # Initialize email service
    email_service = EmailService()

    # Handle different execution modes
    if mode == "wed":
        target = scheduler.next_wednesday_14()  # 14:00:00
        prefill_time = target - dt.timedelta(seconds=30)  # 13:59:30
        now = dt.datetime.now(tz)
        wait_seconds = (target - now).total_seconds()
        
        print(f"將等待至（{tz.key if hasattr(tz, 'key') else 'Asia/Taipei'}）：{target:%Y-%m-%d %H:%M:%S}（週三 14:00）再執行...")
        print(f"表單將在 {prefill_time:%H:%M:%S} 開始填寫，{target:%H:%M:%S} 準時送出")
        
        # Send reminder email if wait time > 5 minutes
        if wait_seconds > 300:
            reminder_time = target - dt.timedelta(minutes=5)
            print(f"提示：將在 {reminder_time:%Y-%m-%d %H:%M:%S} 發送提醒郵件（執行前5分鐘）")
            
            await scheduler.sleep_until(reminder_time)
            
            try:
                await email_service.send_reminder(weekday_list, reason_map)
                print("已發送執行前提醒郵件")
            except Exception as mail_err:
                print(f"發送提醒郵件失敗：{mail_err}")
            
            print(f"等待到預填時間...")
            await scheduler.sleep_until(prefill_time)
        else:
            await scheduler.sleep_until(prefill_time)
            
    elif mode == "delay":
        start = dt.datetime.now(tz)
        target = start + dt.timedelta(minutes=minutes or 0)
        print(f"將等待 {minutes} 分鐘，目標時間：{target:%Y-%m-%d %H:%M:%S}")
        await scheduler.sleep_until(target)
    else:
        print("立即執行。")

    # Validate execution time
    scheduler.validate_time()

    # Execute browser automation
    results = []
    
    async with async_playwright() as p:
        # Special handling for Wednesday mode
        if mode == "wed":
            print(f"\n=== 星期三模式：開始預填所有表單 ===")
            print(f"當前時間: {dt.datetime.now(tz):%H:%M:%S}")
            
            tasks = []
            for idx in target_indices:
                url = form_urls[idx]
                weekday_name = "一二三四五六日"[idx]
                print(f"[星期{weekday_name}] 準備開啟瀏覽器...")
                tasks.append(asyncio.create_task(
                    BrowserManager.prefill_and_submit_at_exact_time(p, url, idx, target)
                ))
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
        # Normal mode: fill and submit immediately
        else:
            if len(target_indices) == 1:
                idx = target_indices[0]
                url = form_urls[idx]
                print(f"\n=== 星期索引 {idx}（{'一二三四五六日'[idx]}） → 開 1 個瀏覽器 ===")
                result = await BrowserManager.run_in_isolated_browser(p, url, idx)
                results.append(result)
            else:
                tasks = []
                for idx in target_indices:
                    url = form_urls[idx]
                    print(f"\n=== 星期索引 {idx}（{'一二三四五六日'[idx]}） → 開獨立瀏覽器 ===")
                    tasks.append(asyncio.create_task(
                        BrowserManager.run_in_isolated_browser(p, url, idx)
                    ))

                results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Record end time
    end_time = dt.datetime.now(tz)
    
    # Process and display results
    print("\n" + "=" * 50)
    print("執行結果統計")
    print("=" * 50)
    
    success_list = []
    failure_list = []
    
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
            print(f"失敗：星期{weekday_name} - {error_msg}")
    
    print("=" * 50)
    print(f"總計：成功 {len(success_list)} 個，失敗 {len(failure_list)} 個")
    print("=" * 50)
    
    # Send summary email
    try:
        await email_service.send_summary(
            success_list=success_list,
            failure_list=failure_list,
            end_time=end_time,
            reason_map=reason_map
        )
    except Exception as mail_err:
        print(f"發送總結郵件失敗：{mail_err}")


if __name__ == "__main__":
    asyncio.run(main())

