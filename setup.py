"""
Setup and Configuration Entry Point
This is the main entry point for the application
"""
import sys
import json
from pathlib import Path

# Check Python version before importing other modules
if sys.version_info < (3, 9):
    current_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    print(f"Error: Current Python version is {current_version}")
    print("This program requires Python 3.9 or higher to run")
    print("Please upgrade your Python installation")
    sys.exit(1)


def check_and_load_config():
    """Check if config.json exists and load it"""
    config_path = Path("config.json")
    
    if not config_path.exists():
        print("=" * 60)
        print("❌ 錯誤：找不到 config.json")
        print("=" * 60)
        print("\n請先建立 config.json 檔案。")
        print("您可以複製 config.json.example 並修改內容：")
        print("\n  Windows: copy config.json.example config.json")
        print("  macOS/Linux: cp config.json.example config.json")
        print("\n然後編輯 config.json 填入您的個人資料。")
        sys.exit(1)
    
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            config = json.load(f)
        return config
    except json.JSONDecodeError as e:
        print(f"❌ 錯誤：config.json 格式不正確")
        print(f"詳細錯誤：{e}")
        sys.exit(1)


def validate_config(config):
    """Validate config.json content"""
    print("=" * 60)
    print("配置資訊確認")
    print("=" * 60)
    
    # Display user info
    print("\n【使用者資訊】")
    print(f"  姓名：{config.get('user', {}).get('name', '未設定')}")
    
    # Display email info
    print("\n【郵件設定】")
    email = config.get('email', {})
    print(f"  發送帳號：{email.get('gmail_account', '未設定')}")
    print(f"  接收帳號：{email.get('recipient_email', '未設定')}")
    print(f"  顯示名稱：{email.get('sender_name', '未設定')}")
    
    # Display dates
    print("\n【劃假日期】")
    dates = config.get('dates', {})
    weekdays = dates.get('weekdays', [])
    if weekdays:
        weekday_str = "、".join(f"星期{day}" for day in weekdays)
        print(f"  {weekday_str}")
    else:
        print("  （無）")
    
    # Display reasons
    reasons = dates.get('reasons', {})
    if reasons:
        print("\n【請假原因】")
        for weekday, reason in reasons.items():
            if weekday in weekdays:
                print(f"  星期{weekday}：{reason}")
    
    # Display forms URLs
    print("\n【表單 URL】")
    urls = config.get('forms_urls', [])
    if len(urls) == 7:
        weekday_names = ["一", "二", "三", "四", "五", "六", "日"]
        for i, url in enumerate(urls):
            print(f"  星期{weekday_names[i]}：{url}")
    else:
        print(f"  ⚠️  警告：表單 URL 數量不正確（需要 7 個，目前 {len(urls)} 個）")
    
    # Display settings
    print("\n【其他設定】")
    settings = config.get('settings', {})
    print(f"  無頭模式：{'是' if settings.get('headless', False) else '否'}")
    print(f"  最低原因字數：{settings.get('min_reason_length', 15)} 字")
    
    print("\n" + "=" * 60)
    
    # Ask for confirmation
    ans = input("\n以上資訊是否正確？(y/n)：").strip().lower()
    if ans != "y":
        print("\n請修改 config.json 檔案，然後重新執行。")
        print("修改路徑：./config.json")
        sys.exit(1)
    
    return config


def check_mail_key():
    """Check if mail_key.env exists and handle email functionality"""
    mail_key_path = Path("mail_key.env")
    
    if mail_key_path.exists():
        print("\n✓ 偵測到 mail_key.env，郵件功能已啟用")
        return True
    
    print("\n" + "=" * 60)
    print("⚠️  未偵測到 mail_key.env")
    print("=" * 60)
    print("\n您沒有設定 mail_key.env")
    print("本次執行不會傳送郵件。")
    
    ans = input("\n是否要啟用傳送郵件功能？(y/n)：").strip().lower()
    
    if ans != "y":
        print("\n✓ 郵件功能已停用，程式將繼續執行（不傳送郵件）")
        return False
    
    # User wants to enable email
    print("\n請輸入您的 Gmail 應用程式密碼（16 個字元）：")
    print("格式：xxxx xxxx xxxx xxxx （可以有空格）")
    print("取得方式：Google 帳戶 → 安全性 → 兩步驟驗證 → 應用程式密碼")
    
    key = input("\nKEY=").strip()
    
    if not key:
        print("\n✗ 未輸入密碼，郵件功能已停用")
        return False
    
    # Write to mail_key.env
    try:
        with open(mail_key_path, "w", encoding="utf-8") as f:
            f.write(f"KEY={key}\n")
        print("\n✓ 已儲存 mail_key.env，郵件功能已啟用")
        return True
    except Exception as e:
        print(f"\n✗ 儲存 mail_key.env 失敗：{e}")
        print("郵件功能已停用")
        return False


def write_config_to_settings_py(config):
    """Write config.json data to config/settings.py"""
    # Update config/settings.py
    user = config.get('user', {})
    email = config.get('email', {})
    settings = config.get('settings', {})
    
    settings_content = f'''"""
Application Configuration Settings
All configurable parameters are defined here
"""

# ==== User Configuration ====
NAME = "{user.get('name', '您的姓名')}"
TIMEZONE = "Asia/Taipei"

# ==== File Paths ====
SCREENSHOT_DIR = "fail_img"

# ==== Browser Settings ====
HEADLESS = {str(settings.get('headless', False))}
NAV_TIMEOUT_MS = 40_000
ACTION_TIMEOUT_MS = 20_000

# ==== Retry Settings ====
MAX_RETRIES_PER_FORM = 2  # Total attempts: 2 times (first attempt + 1 retry)
RETRY_BACKOFF_SECONDS = [3]  # Wait 3 seconds after first failure before retry

# ==== Form Submission Timeout Settings ====
SUBMIT_WARNING_TIMEOUT_SEC = 10  # Send warning email if no redirect within 10 seconds
SUBMIT_KILL_TIMEOUT_SEC = 20     # Mark as failure if no redirect within 20 seconds

# ==== Reason Validation ====
MIN_REASON_LENGTH = {settings.get('min_reason_length', 15)}  # Minimum character count for weekend reason (excluding spaces)

# ==== Weekday Mappings ====
# Chinese weekday to index mapping (Monday=0, ..., Sunday=6)
WEEKDAY_MAP = {{
    "一": 0, "二": 1, "三": 2, "四": 3, "五": 4, "六": 5, "日": 6, "天": 6
}}

# Weekday index to English name mapping (capitalized)
WEEKDAY_EN = {{
    0: "Monday", 1: "Tuesday", 2: "Wednesday", 3: "Thursday",
    4: "Friday", 5: "Saturday", 6: "Sunday"
}}

# ==== Form Field Keywords ====
VACATION_KEYWORDS = [
    r"休假", r"請假", r"不出勤", r"放假", r"vacation", r"leave", r"off",
]

SUBMIT_BTN_PATTERNS = [
    r"送出", r"提交", r"提交表單", r"Submit", r"Send", r"回覆", r"確定", r"Next", r"下一步"
]

# ==== Email Configuration ====
GMAIL_ACCOUNT = "{email.get('gmail_account', 'your_email@gmail.com')}"
RECIPIENT_EMAIL = "{email.get('recipient_email', 'recipient@example.com')}"
SENDER_NAME = "{email.get('sender_name', '表單填寫機器人')}"
MAIL_KEY_FILE = "mail_key.env"
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
'''
    
    Path("config/settings.py").write_text(settings_content, encoding="utf-8")


def main():
    """Main setup entry point"""
    print("=" * 60)
    print("Google Forms Auto-Fill Bot")
    print("=" * 60)
    
    # Step 1: Check and load config.json
    print("\n[步驟 1/3] 檢查配置檔案...")
    config = check_and_load_config()
    
    # Step 2: Validate and confirm config
    print("\n[步驟 2/3] 驗證配置資訊...")
    config = validate_config(config)
    
    # Step 3: Check mail_key.env
    print("\n[步驟 3/3] 檢查郵件設定...")
    email_enabled = check_mail_key()
    
    # Write config to settings.py
    print("\n正在生成 config/settings.py...")
    write_config_to_settings_py(config)
    print("✓ config/settings.py 已生成")
    
    # Set global email flag
    import os
    os.environ['EMAIL_ENABLED'] = '1' if email_enabled else '0'
    
    # Import and run main program
    print("\n" + "=" * 60)
    print("開始執行程式")
    print("=" * 60)
    
    # Import main after config is ready
    from main import main as run_main
    import asyncio
    
    asyncio.run(run_main())


if __name__ == "__main__":
    main()

