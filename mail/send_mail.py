import smtplib
import os
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv
import logging


def render_email_html(summary_data: dict) -> str:
    """
    產生精美、相容度高的郵件 HTML（無 emoji）。
    - 專業 UX/UI 配色與排版
    - 高對比，深/淺色模式皆清楚
    - 仍以 table 為骨架提高相容度
    """
    submitted_days = summary_data.get("submitted_days", [])
    submitted_days_str = "、".join(submitted_days) if submitted_days else "（無）"

    reasons = summary_data.get("reasons", {}) or {}
    all_success = bool(summary_data.get("all_success", False))
    failed_days = summary_data.get("failed_days", []) or []
    failed_days_str = "、".join(failed_days) if failed_days else ""

    preheader = f"本次提交：{submitted_days_str}"

    # 理由列表 HTML
    reasons_items = []
    if reasons.get("sat"):
        reasons_items.append(
            f"<li><span class='chip chip-day'>星期六</span><span class='reason'>{reasons['sat']}</span></li>"
        )
    if reasons.get("sun"):
        reasons_items.append(
            f"<li><span class='chip chip-day'>星期日</span><span class='reason'>{reasons['sun']}</span></li>"
        )
    reasons_html = ""
    if reasons_items:
        reasons_html = """
        <tr>
          <td class="section">
            <div class="section-title">請假理由</div>
            <ul class="reasons">
              {items}
            </ul>
          </td>
        </tr>
        """.format(items="\n".join(reasons_items))

    # 執行結果 HTML
    if all_success:
        result_html = """
        <div class="status">
          <span class="badge success">全數成功</span>
          <p class="hint">已成功提交所有指定表單。</p>
        </div>
        """
    else:
        extra = f"<p class='failed-list'><b>失敗的表單：</b>{failed_days_str}</p>" if failed_days_str else ""
        result_html = f"""
        <div class="status">
          <span class="badge failure">未全數成功</span>
          {extra}
          <p class="hint">請查看程式的日誌輸出以了解詳細錯誤原因。</p>
        </div>
        """

    return f"""\
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="x-apple-disable-message-reformatting">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="color-scheme" content="light dark">
  <title>表單提交總結報告</title>
  <style>
    /* -------- 基礎重置 -------- */
    body,table,td,p,span,a {{ margin:0; padding:0; }}
    img {{ border:0; line-height:100%; outline:none; text-decoration:none; max-width:100%; }}
    a {{ text-decoration:none; }}

    /* -------- 淺色主題（預設） -------- */
    body {{
      background:#F6F8FC;
      color:#111827; /* 高對比正文 */
      font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Helvetica Neue",Arial,"Noto Sans TC","PingFang TC","Microsoft JhengHei",sans-serif;
      line-height:1.65;
    }}
    .wrapper {{ width:100%; padding:28px 12px; }}
    .container {{
      width:100%; max-width:720px; margin:0 auto; background:#FFFFFF;
      border:1px solid #E5E7EB; border-radius:12px; overflow:hidden;
    }}
    .header {{
      padding:24px 28px;
      background:#FFFFFF;
      border-bottom:1px solid #E5E7EB;
    }}
    .eyebrow {{
      font-size:12px; letter-spacing:.08em; text-transform:uppercase;
      color:#2563EB; font-weight:700; margin-bottom:6px;
    }}
    .title {{
      font-size:22px; font-weight:800; color:#0F172A; /* 更深的標題色 */
    }}
    .content {{ padding:8px 28px 28px 28px; }}
    .section {{ padding:18px 0; }}
    .section + .section {{ border-top:1px solid #EEF2F7; }}
    .section-title {{
      font-size:15px; font-weight:800; color:#0F172A; margin-bottom:10px;
      padding-left:10px; border-left:3px solid #2563EB; /* 清楚的視覺錨點 */
    }}

    /* 資訊卡：提高對比 */
    .card {{
      background:#F9FAFB;
      border:1px solid #E5E7EB;
      border-radius:10px;
      padding:14px 16px;
    }}
    .meta p {{ margin:0 0 6px 0; color:#111827; }}
    .meta b {{ color:#0F172A; }}

    /* 膠囊標籤、狀態徽章 */
    .chip {{
      display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px; font-weight:700;
      border:1px solid #C7D2FE; background:#EEF2FF; color:#1E3A8A;
      vertical-align:middle; margin-right:8px;
    }}
    .chip-day {{ min-width:56px; text-align:center; }}

    .badge {{
      display:inline-block; padding:7px 12px; border-radius:999px;
      font-size:13px; font-weight:800; border:1px solid transparent;
    }}
    .badge.success {{ color:#065F46; background:#ECFDF5; border-color:#A7F3D0; }}
    .badge.failure {{ color:#7F1D1D; background:#FEF2F2; border-color:#FECACA; }}

    .status {{ display:block; }}
    .failed-list {{ margin:8px 0 0 0; color:#B91C1C; }}
    .hint {{ color:#4B5563; font-size:13px; margin-top:6px; }}

    /* 理由列表：條列與留白 */
    .reasons {{ list-style:none; padding-left:0; margin:0; }}
    .reasons li {{
      display:flex; gap:10px; align-items:flex-start;
      background:#F9FAFB; border:1px solid #E5E7EB; border-radius:10px;
      padding:10px 12px; margin-bottom:8px;
      color:#111827;
    }}
    .reasons .reason {{ flex:1; }}

    .footer {{
      padding:16px 28px; border-top:1px solid #E5E7EB; color:#6B7280; font-size:12px; text-align:center;
      background:#FAFAFA;
    }}

    /* -------- 深色模式：手動指定避免被客戶端自動反色影響對比 -------- */
    @media (prefers-color-scheme: dark) {{
      body {{ background:#0B0F14; color:#E5E7EB; }}
      .container {{ background:#0F1720; border-color:#1F2937; }}
      .header {{ background:#0F1720; border-bottom-color:#1F2937; }}
      .title {{ color:#F3F4F6; }}
      .section + .section {{ border-top-color:#1F2937; }}
      .section-title {{ color:#F3F4F6; border-left-color:#3B82F6; }}
      .card {{ background:#111827; border-color:#334155; }}
      .meta p {{ color:#E5E7EB; }}
      .meta b {{ color:#FFFFFF; }}
      .chip {{ background:#13233F; border-color:#1E3A8A; color:#93C5FD; }}
      .reasons li {{ background:#111827; border-color:#334155; color:#E5E7EB; }}
      .footer {{ background:#0F1720; border-top-color:#1F2937; color:#9CA3AF; }}
      .hint {{ color:#9CA3AF; }}
      .badge.success {{ color:#86EFAC; background:#052E1A; border-color:#14532D; }}
      .badge.failure {{ color:#FCA5A5; background:#2A0B0B; border-color:#7F1D1D; }}
      .failed-list {{ color:#FCA5A5; }}
    }}

    /* -------- 小螢幕微調 -------- */
    @media screen and (max-width:520px) {{
      .header, .content, .footer {{ padding-left:18px; padding-right:18px; }}
      .title {{ font-size:20px; }}
    }}

    /* 收件匣摘要（隱藏） */
    .preheader {{
      display:none !important; visibility:hidden; opacity:0; color:transparent; height:0; width:0;
      overflow:hidden; mso-hide:all;
    }}
  </style>
</head>
<body>
  <span class="preheader">{preheader}</span>
  <table role="presentation" class="wrapper" cellpadding="0" cellspacing="0" width="100%">
    <tr>
      <td align="center">
        <table role="presentation" class="container" cellpadding="0" cellspacing="0" width="100%">
          <tr>
            <td class="header">
              <div class="eyebrow">Google Form Auto-Filler</div>
              <div class="title">表單提交總結報告</div>
            </td>
          </tr>
          <tr>
            <td class="content">
              <table role="presentation" width="100%" cellpadding="0" cellspacing="0">
                <tr>
                  <td class="section">
                    <div class="section-title">提交詳情</div>
                    <div class="card meta">
                      <p><b>本次提交的表單：</b>{submitted_days_str}</p>
                    </div>
                  </td>
                </tr>
                {reasons_html}
                <tr>
                  <td class="section">
                    <div class="section-title">執行結果</div>
                    {result_html}
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td class="footer">
              這是一封自動發送的郵件，請勿直接回覆。
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def send_summary_email(summary_data):
    """
    發送總結報告郵件。

    Args:
        summary_data (dict): 包含報告內容的字典。
    
    Returns:
        bool: 是否成功發送郵件。
    """
    # 從不同路徑載入環境變數
    load_dotenv(dotenv_path='mail/mail_key.env')       # 讀取 mail/ 目錄下的 mail_key.env
    load_dotenv(dotenv_path='mail/mail_settings.env')  # 讀取 mail/ 目錄下的 mail_settings.env
    
    sender_email = os.getenv("SENDER_EMAIL")
    recipient_email = os.getenv("RECIPIENT_EMAIL")
    app_password = os.getenv("KEY")

    if not all([sender_email, recipient_email, app_password]):
        logging.error("郵件設定不完整，請檢查 mail_key.env 和 mail_settings.env 的設定。")
        if not sender_email:
            logging.error("-> 缺少 SENDER_EMAIL")
        if not recipient_email:
            logging.error("-> 缺少 RECIPIENT_EMAIL")
        if not app_password:
            logging.error("-> 缺少 KEY")
        return False

    # --- 建立郵件內容（HTML，無 emoji） ---
    subject = "自動填寫工作劃假表單總結報告"
    body = render_email_html(summary_data)

    # --- 設定郵件物件 ---
    msg = MIMEText(body, 'html', 'utf-8')
    msg['From'] = sender_email
    msg['To'] = recipient_email
    msg['Subject'] = Header(subject, 'utf-8')

    # --- 發送郵件 ---
    try:
        logging.info(f"正在嘗試發送郵件至 {recipient_email}...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, [recipient_email], msg.as_string())
        logging.info("郵件發送成功。")
        return True
    except smtplib.SMTPAuthenticationError:
        logging.error("郵件發送失敗：SMTP 驗證錯誤。請檢查 SENDER_EMAIL 與 KEY 是否正確。")
        return False
    except Exception as e:
        logging.error(f"郵件發送時發生未預期的錯誤：{e}")
        return False
