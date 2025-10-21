import smtplib
import os
from email.mime.text import MIMEText
from email.header import Header
from dotenv import load_dotenv
import logging


def render_email_html(summary_data: dict) -> str:
    """
    產生精美、相容度高的郵件 HTML（無 emoji）。
    - 使用表格為骨架（傳統郵件相容度較佳）
    - 內嵌 CSS，並包含簡單的深色模式支援
    - 含 preheader（於收件匣摘要顯示）
    """
    submitted_days = summary_data.get("submitted_days", [])
    submitted_days_str = "、".join(submitted_days) if submitted_days else "（無）"

    reasons = summary_data.get("reasons", {}) or {}
    all_success = bool(summary_data.get("all_success", False))
    failed_days = summary_data.get("failed_days", []) or []
    failed_days_str = "、".join(failed_days) if failed_days else ""

    preheader = f"本次提交：{submitted_days_str}"  # 收件匣摘要

    # 理由列表 HTML
    reasons_items = []
    if reasons.get("sat"):
        reasons_items.append(
            f"<li><span class='day'>星期六</span><span class='reason'>{reasons['sat']}</span></li>"
        )
    if reasons.get("sun"):
        reasons_items.append(
            f"<li><span class='day'>星期日</span><span class='reason'>{reasons['sun']}</span></li>"
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
        """.format(
            items="\n".join(reasons_items)
        )

    # 執行結果 HTML
    if all_success:
        result_html = """
        <p class="badge success">全數成功</p>
        """
    else:
        extra = (
            f"<p class='failed-list'><b>失敗的表單：</b>{failed_days_str}</p>"
            if failed_days_str
            else ""
        )
        result_html = f"""
        <p class="badge failure">未全數成功</p>
        {extra}
        <p class="hint"><b>失敗原因：</b>請查看程式執行的日誌輸出以取得詳細錯誤訊息。</p>
        """

    return f"""\
<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <meta name="x-apple-disable-message-reformatting">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>表單提交總結報告</title>
  <style>
    /* 基礎重置 */
    body,table,td,p,span,a {{ margin:0; padding:0; }}
    body {{
      background-color:#f4f7f6; 
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans TC", "PingFang TC", "Microsoft JhengHei", sans-serif;
      color:#333333; 
      line-height:1.6;
    }}
    a {{ color:#0b65c2; text-decoration:none; }}
    img {{ border:0; line-height:100%; outline:none; text-decoration:none; max-width:100%; }}
    /* 外框容器（使用 table 以提升相容度） */
    .wrapper {{ width:100%; background:#f4f7f6; padding:24px 12px; }}
    .container {{
      width:100%; max-width:680px; margin:0 auto; background:#ffffff; 
      border:1px solid #e6e6e6; border-radius:12px; overflow:hidden;
    }}
    .header {{
      padding:28px 32px; 
      background:linear-gradient(135deg,#f8fafc 0%, #ffffff 100%);
      border-bottom:1px solid #eef1f4;
    }}
    .title {{ font-size:22px; font-weight:700; letter-spacing:0.2px; }}
    .subtle {{ color:#6b7280; font-size:13px; margin-top:6px; }}
    .content {{ padding:8px 32px 28px 32px; }}
    .section {{ padding:18px 0; }}
    .section + .section {{ border-top:1px dashed #eaecef; }}
    .section-title {{ font-size:16px; font-weight:700; color:#374151; margin-bottom:10px; }}
    .card {{
      background:#fafbfc; border:1px solid #eef1f4; border-radius:10px;
      padding:14px 16px;
    }}
    .meta p {{ margin:0 0 6px 0; }}
    .badge {{
      display:inline-block; font-size:13px; font-weight:700; border-radius:999px; padding:6px 12px; 
      border:1px solid transparent;
    }}
    .badge.success {{ color:#166534; background:#ecfdf5; border-color:#a7f3d0; }}
    .badge.failure {{ color:#7f1d1d; background:#fef2f2; border-color:#fecaca; }}
    .failed-list {{ margin-top:8px; }}
    .hint {{ color:#6b7280; font-size:13px; margin-top:8px; }}
    .reasons {{ list-style:none; padding-left:0; margin:0; }}
    .reasons li {{
      display:flex; gap:10px; align-items:flex-start;
      background:#f9fafb; border:1px solid #eceff3; border-radius:8px; padding:10px 12px; margin-bottom:8px;
    }}
    .reasons .day {{ min-width:56px; font-weight:700; color:#374151; }}
    .reasons .reason {{ color:#374151; }}
    .footer {{
      padding:18px 32px; border-top:1px solid #eef1f4; color:#6b7280; font-size:12px; text-align:center;
      background:#fafbfc;
    }}
    /* 深色模式 */
    @media (prefers-color-scheme: dark) {{
      body {{ background:#0b0f14; color:#e5e7eb; }}
      .wrapper {{ background:#0b0f14; }}
      .container {{ background:#0f1720; border-color:#1f2937; }}
      .header {{ background:linear-gradient(135deg,#0f1720 0%, #111827 100%); border-color:#1f2937; }}
      .title {{ color:#e5e7eb; }}
      .subtle {{ color:#9ca3af; }}
      .section + .section {{ border-top-color:#1f2937; }}
      .card {{ background:#0b1220; border-color:#1f2a3a; }}
      .section-title, .reasons .day, .reasons .reason {{ color:#e5e7eb; }}
      .footer {{ background:#0b1220; border-color:#1f2937; color:#9ca3af; }}
      .badge.success {{ color:#86efac; background:#052e1a; border-color:#14532d; }}
      .badge.failure {{ color:#fca5a5; background:#2a0b0b; border-color:#7f1d1d; }}
      .reasons li {{ background:#0f1720; border-color:#1f2937; }}
      .hint {{ color:#9ca3af; }}
    }}
    /* 小螢幕微調 */
    @media screen and (max-width: 520px) {{
      .header, .content, .footer {{ padding-left:18px; padding-right:18px; }}
      .title {{ font-size:20px; }}
    }}
    /* 隱藏 preheader */
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
              <div class="title">表單提交總結報告</div>
              <div class="subtle">此報告由系統自動產生</div>
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
