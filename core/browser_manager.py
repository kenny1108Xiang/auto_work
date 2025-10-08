"""
Browser management for form submission
Handles browser creation, form filling with retry logic
"""
import asyncio
from typing import Tuple, Optional
from pathlib import Path

from config.settings import (
    HEADLESS, NAV_TIMEOUT_MS, ACTION_TIMEOUT_MS, 
    MAX_RETRIES_PER_FORM, RETRY_BACKOFF_SECONDS, SCREENSHOT_DIR
)
from core.form_filler import FormFiller
from utils.screenshot import take_screenshot, ensure_screenshot_dir, get_screenshot_filename
from utils.validators import check_form_closed
from core.scheduler import precise_sleep_until


class BrowserManager:
    """Manages browser instances and form submission workflow"""
    
    @staticmethod
    async def submit_single_form(context, url: str, weekday_name: str = "未知", weekday_idx: int = 0) -> Optional[str]:
        """Submit single form (fill and submit immediately)"""
        page = await context.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        page.set_default_timeout(ACTION_TIMEOUT_MS)

        screenshot_path = None
        filler = FormFiller(page, weekday_name)
        
        try:
            await filler.fill_form_only(url)
            await filler.submit_filled_form()
            return None  # Success
            
        except Exception as e:
            print(f"錯誤: 星期{weekday_name}表單填寫失敗: {e}")
            
            is_closed = await check_form_closed(page)
            
            try:
                screenshot_path = await take_screenshot(page, weekday_idx)
                print(f"已儲存失敗截圖: {screenshot_path}")
            except Exception as screenshot_err:
                print(f"截圖失敗: {screenshot_err}")
            
            if is_closed:
                print(f"原因: 表單已關閉 (不接受回應)")
            
            raise
            
        finally:
            await page.close()
            
        return screenshot_path

    @staticmethod
    async def submit_form_with_retry(context, url: str, weekday_name: str = "未知", weekday_idx: int = 0) -> Tuple[bool, Optional[str], Optional[str]]:
        """Retry form submission with failure notification"""
        from notifications.email_service import EmailService
        
        email_service = EmailService()
        last_err: Optional[Exception] = None
        first_screenshot_path: Optional[str] = None
        first_failure_notified = False
        
        for attempt, delay in enumerate([0] + RETRY_BACKOFF_SECONDS, start=1):
            if delay > 0:
                print(f"等待 {delay} 秒後重試...")
                await asyncio.sleep(delay)
            
            try:
                print(f"嘗試第 {attempt} 次（共 {MAX_RETRIES_PER_FORM} 次）")
                result = await BrowserManager.submit_single_form(context, url, weekday_name, weekday_idx)
                return (True, None, None)
                
            except Exception as e:
                last_err = e
                print(f"第 {attempt} 次失敗：{e}")
                
                if attempt == 1 and not first_failure_notified:
                    ensure_screenshot_dir()
                    screenshot_filename = get_screenshot_filename(weekday_idx)
                    potential_screenshot_path = Path(SCREENSHOT_DIR) / screenshot_filename
                    
                    if potential_screenshot_path.exists():
                        first_screenshot_path = str(potential_screenshot_path)
                        print(f"找到第一次失敗的截圖：{first_screenshot_path}")
                    
                    try:
                        await email_service.send_immediate_failure(
                            weekday_name=weekday_name,
                            url=url,
                            screenshot_path=first_screenshot_path,
                            error_msg=str(e)
                        )
                        first_failure_notified = True
                        print(f"已發送第一次失敗通知郵件（星期{weekday_name}）")
                    except Exception as mail_err:
                        print(f"發送失敗通知郵件時出錯：{mail_err}")
        
        return (False, first_screenshot_path, str(last_err))

    @staticmethod
    async def run_in_isolated_browser(p, url: str, weekday_idx: int) -> Tuple[int, bool, Optional[str], Optional[str]]:
        """Run form submission in isolated browser"""
        weekday_name = "一二三四五六日"[weekday_idx]
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        
        try:
            success, screenshot_path, error_msg = await BrowserManager.submit_form_with_retry(
                context, url, weekday_name, weekday_idx
            )
            return (weekday_idx, success, screenshot_path, error_msg)
        finally:
            await context.close()
            await browser.close()

    @staticmethod
    async def prefill_and_submit_at_exact_time(p, url: str, weekday_idx: int, submit_time) -> Tuple[int, bool, Optional[str], Optional[str]]:
        """Pre-fill form then submit at exact time (for Wednesday mode)"""
        weekday_name = "一二三四五六日"[weekday_idx]
        browser = await p.chromium.launch(headless=HEADLESS)
        context = await browser.new_context()
        page = await context.new_page()
        page.set_default_navigation_timeout(NAV_TIMEOUT_MS)
        page.set_default_timeout(ACTION_TIMEOUT_MS)
        
        screenshot_path = None
        error_msg = None
        success = False
        filler = FormFiller(page, weekday_name)
        
        try:
            print(f"[星期{weekday_name}] 開始填寫表單...")
            await filler.fill_form_only(url)
            print(f"[星期{weekday_name}] 表單已填寫完畢，等待送出時間...")
            
            await precise_sleep_until(submit_time)
            
            print(f"[星期{weekday_name}] 送出表單！")
            await filler.submit_filled_form()
            
            success = True
            print(f"[星期{weekday_name}] ✓ 表單送出成功")
            
        except Exception as e:
            error_msg = str(e)
            print(f"[星期{weekday_name}] ✗ 表單處理失敗: {error_msg}")
            
            try:
                screenshot_path = await take_screenshot(page, weekday_idx)
            except Exception as screenshot_err:
                print(f"[星期{weekday_name}] 截圖失敗: {screenshot_err}")
        
        finally:
            await page.close()
            await context.close()
            await browser.close()
        
        return (weekday_idx, success, screenshot_path, error_msg)

