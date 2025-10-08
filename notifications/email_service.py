"""
Email notification service
Handles all email sending operations
"""
import os
import datetime as dt
from pathlib import Path
from typing import List, Tuple, Optional

from config.settings import (
    GMAIL_ACCOUNT, RECIPIENT_EMAIL, SENDER_NAME, MAIL_KEY_FILE,
    SMTP_SERVER, SMTP_PORT
)


class EmailService:
    """Email notification service"""
    
    def __init__(self):
        self.gmail_account = GMAIL_ACCOUNT
        self.recipient_email = RECIPIENT_EMAIL
        self.sender_name = SENDER_NAME
        self.smtp_server = SMTP_SERVER
        self.smtp_port = SMTP_PORT
        self.email_enabled = os.environ.get('EMAIL_ENABLED', '1') == '1'
    
    def _check_email_enabled(self):
        """Check if email is enabled"""
        if not self.email_enabled:
            return False
        return True
    
    def _load_app_password(self, file_path: str = MAIL_KEY_FILE) -> str:
        """Load application password from mail_key.env"""
        p = Path(file_path)
        if not p.exists():
            raise FileNotFoundError(f"Cannot find {file_path}, please create this file and fill in app password")
        
        content = p.read_text(encoding="utf-8").strip()
        
        if "=" not in content:
            raise ValueError(f"{file_path} format error, should be: KEY=your_app_password")
        
        key, value = content.split("=", 1)
        password = value.strip()
        password = password.replace(" ", "")
        
        if len(password) != 16:
            print(f"警告: 應用程式密碼長度為 {len(password)}, 預期為 16 位")
        
        return password
    
    async def _send_via_smtp(self, subject: str, body: str) -> None:
        """Send email using Gmail SMTP"""
        try:
            import aiosmtplib
            from email.message import EmailMessage
        except ImportError:
            raise ImportError("請先安裝 aiosmtplib：pip install aiosmtplib")
        
        app_password = self._load_app_password()
        
        message = EmailMessage()
        message["From"] = f"{self.sender_name} <{self.gmail_account}>"
        message["To"] = self.recipient_email
        message["Subject"] = subject
        message.set_content(body, charset="utf-8")
        
        await aiosmtplib.send(
            message,
            hostname=self.smtp_server,
            port=self.smtp_port,
            username=self.gmail_account,
            password=app_password,
            start_tls=True,
        )
    
    async def _send_with_attachment(self, subject: str, body: str, attachment_paths: List[str]) -> None:
        """Send email with attachments"""
        try:
            import aiosmtplib
            from email.mime.image import MIMEImage
            from email.mime.multipart import MIMEMultipart
            from email.mime.text import MIMEText
        except ImportError:
            raise ImportError("請先安裝 aiosmtplib: pip install aiosmtplib")
        
        app_password = self._load_app_password()
        
        message = MIMEMultipart()
        message["From"] = f"{self.sender_name} <{self.gmail_account}>"
        message["To"] = self.recipient_email
        message["Subject"] = subject
        
        message.attach(MIMEText(body, "plain", "utf-8"))
        
        for file_path in attachment_paths:
            if not file_path or not Path(file_path).exists():
                continue
            
            try:
                with open(file_path, "rb") as f:
                    img_data = f.read()
                
                file_path_obj = Path(file_path)
                filename = file_path_obj.name
                
                image = MIMEImage(img_data)
                image.add_header("Content-Disposition", "attachment", filename=filename)
                message.attach(image)
                
                print(f"[郵件模組] 已附加檔案：{filename}")
            except Exception as e:
                print(f"[郵件模組] 附加檔案失敗 {file_path}：{e}")
        
        await aiosmtplib.send(
            message,
            hostname=self.smtp_server,
            port=self.smtp_port,
            username=self.gmail_account,
            password=app_password,
            start_tls=True,
        )
    
    async def send_warning(self, weekday_name: str) -> None:
        """Send warning email when form doesn't redirect within 10 seconds"""
        if not self._check_email_enabled():
            return
        
        print(f"[郵件模組] 準備發送警告郵件: 星期{weekday_name}表單超時...")
        
        now = dt.datetime.now()
        subject = f"警告: 星期{weekday_name}表單提交超時"
        body = f"""表單填寫警告通知

時間：{now:%Y-%m-%d %H:%M:%S}
星期：{weekday_name}

警告內容：
星期{weekday_name}的表單在點擊提交後，10秒內未轉跳到成功頁面。
程式將繼續等待至20秒，若仍未成功則會標記為失敗。

可能原因：
1. 網路速度較慢
2. Google 伺服器回應延遲
3. 表單設定有誤

程式將繼續嘗試，請留意最終結果通知。

----
自動發送於表單提交後第10秒
"""
        
        try:
            await self._send_via_smtp(subject, body)
            print(f"[郵件模組] 警告郵件已發送")
        except Exception as e:
            print(f"[郵件模組] 警告郵件發送失敗：{e}")
            raise
    
    async def send_reminder(self, weekday_list: List[str], reason_map: dict = None) -> None:
        """Send reminder email 5 minutes before execution"""
        if not self._check_email_enabled():
            return
        
        print("[郵件模組] 準備發送執行前提醒郵件...")
        
        now = dt.datetime.now()
        subject = "下午兩點準時劃假"
        weekday_str = "、".join(f"星期{name}" for name in weekday_list)
        
        reason_section = ""
        if reason_map:
            reason_lines = []
            for weekday in weekday_list:
                if weekday in reason_map and reason_map[weekday]:
                    reason_lines.append(f"  星期{weekday}：{reason_map[weekday]}")
            
            if reason_lines:
                reason_section = f"""
請假理由說明：
{chr(10).join(reason_lines)}
"""
        
        body = f"""劃假機器人提醒通知

提醒時間：{now:%Y-%m-%d %H:%M:%S}

本次將於下午兩點準時執行劃假作業。

劃假星期：
  {weekday_str}
{reason_section}
程式將在 5 分鐘後自動執行。

----
本郵件由表單填寫機器人自動發送
"""
        
        try:
            await self._send_via_smtp(subject, body)
            print(f"[郵件模組] 執行前提醒郵件已發送")
        except Exception as e:
            print(f"[郵件模組] 執行前提醒郵件發送失敗：{e}")
            raise
    
    async def send_immediate_failure(self, weekday_name: str, url: str, screenshot_path: str = None, error_msg: str = "") -> None:
        """Send immediate failure notification on first failure"""
        if not self._check_email_enabled():
            return
        
        print(f"[郵件模組] 準備發送第一次失敗通知：星期{weekday_name}...")
        
        now = dt.datetime.now()
        subject = f"傳送表單失敗 - 星期{weekday_name}"
        body = f"""表單填寫失敗通知

時間：{now:%Y-%m-%d %H:%M:%S}

以下星期劃假失敗：
  星期{weekday_name}

表單資訊：
  星期{weekday_name}：{url}

錯誤訊息：
  {error_msg}

程式將進行第二次嘗試，請留意最終結果通知。

----
本郵件由表單填寫機器人自動發送（第一次失敗通知）
"""
        
        try:
            if screenshot_path:
                await self._send_with_attachment(subject, body, [screenshot_path])
            else:
                await self._send_via_smtp(subject, body)
            print(f"[郵件模組] 第一次失敗通知已發送")
        except Exception as e:
            print(f"[郵件模組] 第一次失敗通知發送失敗：{e}")
            raise
    
    async def send_summary(self, success_list: List[str], failure_list: List[Tuple[str, str, str]], end_time, reason_map: dict = None) -> None:
        """Send summary email after all forms execution completes"""
        if not self._check_email_enabled():
            print("[郵件模組] 郵件功能已停用，跳過發送總結郵件")
            return
        
        print("[郵件模組] 準備發送總結郵件...")
        
        total = len(success_list) + len(failure_list)
        
        if len(failure_list) == 0:
            subject = f"表單填寫完成：全部成功（{total}個）"
            status = "[成功]"
        else:
            subject = f"表單填寫完成：成功{len(success_list)}個，失敗{len(failure_list)}個"
            status = "[警告]"
        
        reason_section = ""
        if reason_map:
            reason_lines = []
            all_weekdays = success_list + [f[0] for f in failure_list]
            for weekday in all_weekdays:
                if weekday in reason_map and reason_map[weekday]:
                    reason_lines.append(f"  星期{weekday}：{reason_map[weekday]}")
            
            if reason_lines:
                reason_section = f"""
請假理由說明：
{chr(10).join(reason_lines)}

====================================
"""
        
        body = f"""{status} 表單填寫執行報告

====================================
執行結束時間：{end_time:%Y-%m-%d %H:%M:%S}
總表單數：{total}
成功數量：{len(success_list)}
失敗數量：{len(failure_list)}
====================================
{reason_section}
成功的表單：
{self._format_success_list(success_list)}

失敗的表單：
{self._format_failure_list_with_url(failure_list)}

====================================

本郵件由表單填寫機器人自動發送。
"""
        
        try:
            await self._send_via_smtp(subject, body)
            print(f"[郵件模組] 總結郵件已發送")
        except Exception as e:
            print(f"[郵件模組] 總結郵件發送失敗：{e}")
            raise
    
    def _format_success_list(self, success_list: List[str]) -> str:
        """Format success list"""
        if not success_list:
            return "  (None)"
        return "\n".join(f"  - 星期{name}" for name in success_list)
    
    def _format_failure_list_with_url(self, failure_list: List[Tuple[str, str, str]]) -> str:
        """Format failure list with URL"""
        if not failure_list:
            return "  （無）"
        
        result = []
        for weekday_name, url, error_msg in failure_list:
            result.append(f"  - 星期{weekday_name}：{url}")
            result.append(f"    錯誤：{error_msg}")
        
        return "\n".join(result)

