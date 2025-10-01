"""
Email sending module

This module provides email notification functions:
1. send_warning_email: Send warning when form doesn't redirect within 10 seconds
2. send_summary_email: Send summary report after execution (with success/failure list)
3. send_reminder_email: Send reminder 5 minutes before execution
4. send_immediate_failure_email: Send immediate notification on first failure
"""

import asyncio
import datetime as dt
from pathlib import Path
from typing import List, Tuple

# ==== Configurable Section ====
GMAIL_ACCOUNT = "denny0979539212@gmail.com"  # Sender Gmail account
RECIPIENT_EMAIL = "kennymail@jinxiang.dev"  # Recipient email
SENDER_NAME = "表單填寫機器人"  # Sender display name
MAIL_KEY_FILE = "mail_key.env"  # App password file path

# SMTP server settings (Gmail fixed values, usually no need to change)
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
# ==== Configurable Section End ====


def _load_app_password(file_path: str = MAIL_KEY_FILE) -> str:
    """
    Load application password from mail_key.env
    Format: KEY=your_app_password
    """
    p = Path(file_path)
    if not p.exists():
        raise FileNotFoundError(f"Cannot find {file_path}, please create this file and fill in app password")
    
    content = p.read_text(encoding="utf-8").strip()
    
    if "=" not in content:
        raise ValueError(f"{file_path} format error, should be: KEY=your_app_password")
    
    key, value = content.split("=", 1)
    password = value.strip()
    
    # Remove spaces from password (Gmail app password format is xxxx xxxx xxxx xxxx)
    password = password.replace(" ", "")
    
    if len(password) != 16:
        print(f"警告: 應用程式密碼長度為 {len(password)}, 預期為 16 位")
    
    return password


async def send_warning_email(weekday_name: str) -> None:
    """
    Send warning email: called when form doesn't redirect within 10 seconds
    
    Parameters:
        weekday_name: Weekday name (e.g. "一", "二")
    """
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
        await _send_email_via_smtp(subject, body)
        print(f"[郵件模組] 警告郵件已發送")
    except Exception as e:
        print(f"[郵件模組] 警告郵件發送失敗：{e}")
        raise


async def send_reminder_email(weekday_list: List[str]) -> None:
    """
    Send reminder email 5 minutes before execution
    
    Parameters:
        weekday_list: List of weekdays to apply for leave, e.g. ["一", "二", "日"]
    """
    print("[郵件模組] 準備發送執行前提醒郵件...")
    
    now = dt.datetime.now()
    
    subject = "下午兩點準時劃假"
    
    weekday_str = "、".join(f"星期{name}" for name in weekday_list)
    
    body = f"""劃假機器人提醒通知

提醒時間：{now:%Y-%m-%d %H:%M:%S}

本次將於下午兩點準時執行劃假作業。

劃假星期：
  {weekday_str}

程式將在 5 分鐘後自動執行。

----
本郵件由表單填寫機器人自動發送
"""
    
    try:
        await _send_email_via_smtp(subject, body)
        print(f"[郵件模組] 執行前提醒郵件已發送")
    except Exception as e:
        print(f"[郵件模組] 執行前提醒郵件發送失敗：{e}")
        raise


async def send_immediate_failure_email(weekday_name: str, url: str, screenshot_path: str = None, error_msg: str = "") -> None:
    """
    Send email immediately on first failure
    
    Parameters:
        weekday_name: Weekday name (e.g. "一", "二")
        url: Form URL
        screenshot_path: Screenshot file path
        error_msg: Error message
    """
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
        # 如果有截圖，附加到郵件
        if screenshot_path:
            await _send_email_with_attachment(subject, body, [screenshot_path])
        else:
            await _send_email_via_smtp(subject, body)
        print(f"[郵件模組] 第一次失敗通知已發送")
    except Exception as e:
        print(f"[郵件模組] 第一次失敗通知發送失敗：{e}")
        raise


async def send_summary_email(success_list: List[str], failure_list: List[Tuple[str, str, str]], end_time) -> None:
    """
    Send summary email: called after all forms execution completes
    
    Parameters:
        success_list: List of successful weekdays, e.g. ["一", "二"]
        failure_list: Failure information, e.g. [("三", "https://...", "20秒內未轉跳")]
        end_time: Execution end time (datetime object)
    """
    print("[郵件模組] 準備發送總結郵件...")
    
    total = len(success_list) + len(failure_list)
    
    if len(failure_list) == 0:
        # 全部成功
        subject = f"表單填寫完成：全部成功（{total}個）"
        status = "[成功]"
    else:
        # 有失敗
        subject = f"表單填寫完成：成功{len(success_list)}個，失敗{len(failure_list)}個"
        status = "[警告]"
    
    body = f"""{status} 表單填寫執行報告

====================================
執行結束時間：{end_time:%Y-%m-%d %H:%M:%S}
總表單數：{total}
成功數量：{len(success_list)}
失敗數量：{len(failure_list)}
====================================

成功的表單：
{_format_success_list(success_list)}

失敗的表單：
{_format_failure_list_with_url(failure_list)}

====================================

本郵件由表單填寫機器人自動發送。
"""
    
    try:
        await _send_email_via_smtp(subject, body)
        print(f"[郵件模組] 總結郵件已發送")
    except Exception as e:
        print(f"[郵件模組] 總結郵件發送失敗：{e}")
        raise


def _format_success_list(success_list: List[str]) -> str:
    """Format success list"""
    if not success_list:
        return "  (None)"
    return "\n".join(f"  - 星期{name}" for name in success_list)


def _format_failure_list(failure_list: List[Tuple[str, str]]) -> str:
    """Format failure list (old version, kept for backward compatibility)"""
    if not failure_list:
        return "  (None)"
    return "\n".join(f"  - 星期{name}: {error}" for name, error in failure_list)


def _format_failure_list_with_url(failure_list: List[Tuple[str, str, str]]) -> str:
    """Format failure list (with URL)"""
    if not failure_list:
        return "  （無）"
    
    result = []
    for weekday_name, url, error_msg in failure_list:
        result.append(f"  - 星期{weekday_name}：{url}")
        result.append(f"    錯誤：{error_msg}")
    
    return "\n".join(result)


# ==== 以下是實作範例（待填入真實邏輯）====

async def _send_email_via_smtp(subject: str, body: str) -> None:
    """
    使用 Gmail SMTP 發送郵件
    """
    try:
        import aiosmtplib
        from email.message import EmailMessage
    except ImportError:
        raise ImportError("請先安裝 aiosmtplib：pip install aiosmtplib")
    
    # 讀取應用程式密碼
    app_password = _load_app_password()
    
    # 建立郵件訊息
    message = EmailMessage()
    message["From"] = f"{SENDER_NAME} <{GMAIL_ACCOUNT}>"
    message["To"] = RECIPIENT_EMAIL
    message["Subject"] = subject
    message.set_content(body, charset="utf-8")
    
    # 發送郵件
    await aiosmtplib.send(
        message,
        hostname=SMTP_SERVER,
        port=SMTP_PORT,
        username=GMAIL_ACCOUNT,
        password=app_password,
        start_tls=True,
    )


async def _send_email_with_attachment(subject: str, body: str, attachment_paths: List[str]) -> None:
    """
    使用 Gmail SMTP 發送帶附件的郵件
    
    參數:
        subject: 郵件主旨
        body: 郵件內容
        attachment_paths: 附件路徑列表
    """
    try:
        import aiosmtplib
        from email.message import EmailMessage
        from email.mime.image import MIMEImage
        from email.mime.multipart import MIMEMultipart
        from email.mime.text import MIMEText
    except ImportError:
        raise ImportError("請先安裝 aiosmtplib：pip install aiosmtplib")
    
    # 讀取應用程式密碼
    app_password = _load_app_password()
    
    # 建立多部分郵件
    message = MIMEMultipart()
    message["From"] = f"{SENDER_NAME} <{GMAIL_ACCOUNT}>"
    message["To"] = RECIPIENT_EMAIL
    message["Subject"] = subject
    
    # 附加文字內容
    message.attach(MIMEText(body, "plain", "utf-8"))
    
    # 附加圖片檔案
    for file_path in attachment_paths:
        if not file_path or not Path(file_path).exists():
            continue
        
        try:
            with open(file_path, "rb") as f:
                img_data = f.read()
            
            # 根據副檔名判斷圖片類型
            file_path_obj = Path(file_path)
            filename = file_path_obj.name
            
            image = MIMEImage(img_data)
            image.add_header("Content-Disposition", "attachment", filename=filename)
            message.attach(image)
            
            print(f"[郵件模組] 已附加檔案：{filename}")
        except Exception as e:
            print(f"[郵件模組] 附加檔案失敗 {file_path}：{e}")
    
    # 發送郵件
    await aiosmtplib.send(
        message,
        hostname=SMTP_SERVER,
        port=SMTP_PORT,
        username=GMAIL_ACCOUNT,
        password=app_password,
        start_tls=True,
    )

