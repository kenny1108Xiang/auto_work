"""
Form filling functionality using Playwright
Handles all DOM interactions and form submissions
"""
import asyncio
import re
from playwright.async_api import TimeoutError

from config.settings import (
    NAME, SUBMIT_WARNING_TIMEOUT_SEC, SUBMIT_KILL_TIMEOUT_SEC
)
from utils.config_loader import get_config_loader


class FormFiller:
    """Handles form filling operations"""
    
    def __init__(self, page, weekday_name: str = "未知"):
        self.page = page
        self.weekday_name = weekday_name
    
    async def ensure_form_ready(self) -> None:
        """Wait for Google Form main body to load"""
        await self.page.wait_for_selector("form", timeout=15_000)
        await self.page.wait_for_selector(
            "input.whsOnd, input[role='textbox'], div[role='textbox']", 
            timeout=15_000
        )
    
    async def fill_name(self, name: str = NAME) -> None:
        """Fill name input using various DOM selector strategies"""
        candidates = [
            "input.whsOnd[aria-labelledby]",
            "input.whsOnd",
            "input[aria-label='姓名']",
            "input[aria-labelledby*='姓名']",
            "input[role='textbox']",
            "div[role='textbox']",
        ]

        for sel in candidates:
            try:
                loc = self.page.locator(sel).first
                await loc.click(timeout=8_000)
                await loc.fill(name, timeout=8_000)
                return
            except Exception:
                continue

        # Text anchor method as fallback
        try:
            label = self.page.get_by_text(r"^\s*姓名\s*$", exact=True)
            input_el = label.locator("xpath=..").locator("xpath=following::input[@type='text'][1]")
            await input_el.fill(name, timeout=8_000)
            return
        except Exception:
            pass

        raise RuntimeError("找不到『姓名』輸入框")
    
    async def check_vacation(self) -> None:
        """Click vacation radio button"""
        # Special handling for Sunday forms (no aria-label, empty data-value, empty span)
        if self.weekday_name == "日":
            try:
                radiogroup = self.page.locator("div[role='radiogroup']:has-text('星期日')").first
                await radiogroup.wait_for(state="visible", timeout=8_000)
                
                radio = radiogroup.locator("div[role='radio']").first
                await radio.scroll_into_view_if_needed(timeout=5_000)
                await radio.click(timeout=5_000)
                await self.page.wait_for_timeout(50)
                
                is_checked = await radio.get_attribute("aria-checked")
                if is_checked == "true":
                    return
                else:
                    await radio.click(force=True, timeout=5_000)
                    await self.page.wait_for_timeout(500)
                    is_checked = await radio.get_attribute("aria-checked")
                    if is_checked == "true":
                        return
            except Exception:
                pass
            
            # Last resort for Sunday: JavaScript click
            try:
                radio = self.page.locator("div[role='radiogroup'] div[role='radio']").first
                await radio.wait_for(state="attached", timeout=8_000)
                await radio.evaluate("element => element.click()")
                await self.page.wait_for_timeout(500)
                
                is_checked = await radio.get_attribute("aria-checked")
                if is_checked == "true":
                    return
            except Exception:
                pass
        
        # Standard strategy for other weekdays (Monday-Saturday)
        else:
            selector = "[role='radio'][aria-label='休假']"
            
            try:
                locator = self.page.locator(selector).first
                await locator.wait_for(state="visible", timeout=8_000)
                await locator.scroll_into_view_if_needed(timeout=5_000)
                await locator.click(timeout=5_000)
                await self.page.wait_for_timeout(50)
                is_checked = await locator.get_attribute("aria-checked")
                if is_checked == "true":
                    return
                else:
                    await locator.click(force=True, timeout=5_000)
                    await self.page.wait_for_timeout(500)
                    is_checked = await locator.get_attribute("aria-checked")
                    if is_checked == "true":
                        return
                        
            except Exception:
                pass
            
            # Last resort: Use JavaScript to click
            try:
                radio = self.page.locator("[role='radio'][aria-label='休假']").first
                await radio.wait_for(state="attached", timeout=8_000)
                await radio.evaluate("element => element.click()")
                await self.page.wait_for_timeout(500)
                
                is_checked = await radio.get_attribute("aria-checked")
                if is_checked == "true":
                    return
            except Exception:
                pass
        
        # If all strategies fail, raise error
        try:
            radiogroup = self.page.locator("div[role='radiogroup']")
            count = await radiogroup.count()
            print(f"調試資訊: 找到 {count} 個 radiogroup")
            
            if count > 0:
                radios = radiogroup.locator("div[role='radio']")
                radio_count = await radios.count()
                print(f"調試資訊: radiogroup 內有 {radio_count} 個 radio button")
        except Exception:
            pass
        
        raise RuntimeError("無法點擊『休假』單選選項: 所有策略都失敗了")
    
    async def fill_reason(self, reason: str) -> None:
        """Fill reason textarea (for weekend forms)"""
        if not reason:
            return
        
        candidates = [
            "textarea.KHxj8b.tL9Q4c",
            "textarea[jsname='YPqjbf']",
            "textarea[aria-label='您的回答']",
            "textarea[required]",
            "textarea",
        ]

        for sel in candidates:
            try:
                loc = self.page.locator(sel).last
                await loc.click(timeout=8_000)
                await loc.fill(reason, timeout=8_000)
                print(f"已填入原因: {reason}")
                return
            except Exception:
                continue

        # If all selectors fail, try to find by text label
        try:
            label = self.page.get_by_text(re.compile(r"說明|原因|理由"), exact=False)
            textarea_el = label.locator("xpath=..").locator("xpath=following::textarea[1]")
            await textarea_el.fill(reason, timeout=8_000)
            print(f"已填入原因: {reason}")
            return
        except Exception:
            pass

        print(f"警告: 找不到原因輸入欄位，但將繼續執行（原因: {reason}）")
    
    async def submit(self) -> None:
        """Submit form and monitor redirect status"""
        # Find and click submit button
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
                await self.page.locator(sel).first.click(timeout=8_000)
                clicked = True
                break
            except Exception:
                continue

        if not clicked:
            try:
                await self.page.locator("span.NPEfkd.RveJvd.snByac:has-text('提交')").first.click(timeout=8_000)
                clicked = True
            except Exception:
                pass

        if not clicked:
            raise RuntimeError("找不到『提交/送出』按鈕")

        # Stage 1: Wait for redirect (first 10 seconds)
        try:
            await self.page.wait_for_url(
                re.compile(r"formResponse|/thankyou|/viewform\?edit2=.*"), 
                timeout=SUBMIT_WARNING_TIMEOUT_SEC * 1000
            )
            return
        except TimeoutError:
            print(f"警告: 星期{self.weekday_name}表單在10秒內未轉跳, 發送警告郵件...")
            
            try:
                from notifications.email_service import EmailService
                email_service = EmailService()
                await email_service.send_warning(self.weekday_name)
            except Exception as mail_err:
                print(f"警告: 發送警告郵件失敗: {mail_err}")
        
        # Stage 2: Give 10 seconds grace period (20 seconds total)
        try:
            await self.page.wait_for_url(
                re.compile(r"formResponse|/thankyou|/viewform\?edit2=.*"), 
                timeout=(SUBMIT_KILL_TIMEOUT_SEC - SUBMIT_WARNING_TIMEOUT_SEC) * 1000
            )
            print(f"提示: 星期{self.weekday_name}表單在第11-20秒間成功轉跳 (回應較慢)")
            return
        except TimeoutError:
            raise RuntimeError(f"星期{self.weekday_name}表單提交失敗: 20秒內未轉跳到成功頁面")
    
    async def fill_form_only(self, url: str) -> None:
        """Fill the form without submitting (for pre-filling)"""
        print(f"開啟表單: {url}")
        await self.page.goto(url, wait_until="domcontentloaded")
        await self.ensure_form_ready()

        config_loader = get_config_loader()
        reason_map = config_loader.get_reasons()
        reason = reason_map.get(self.weekday_name, "")
        
        await asyncio.gather(
            self.fill_name(),
            self.check_vacation(),
            self.fill_reason(reason)
        )
        print(f"已填寫完畢: 星期{self.weekday_name}表單（等待送出）")
    
    async def submit_filled_form(self) -> None:
        """Submit a form that has already been filled"""
        await self.submit()
        print(f"成功: 星期{self.weekday_name}表單已送出")

