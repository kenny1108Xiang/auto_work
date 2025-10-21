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
    successful_day_names = summary_data.get("successful_day_names", [])
    failed_tasks = summary_data.get("failed_tasks", [])

    preheader = f"本次提交：{len(successful_day_names)} 成功, {len(failed_tasks)} 失敗"

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
        # 成功部分
        success_items = []
        if successful_day_names:
            for day_name in successful_day_names:
                success_items.append(
                    f"<li class='success-item'><span class='chip chip-day chip-success'>{day_name}</span></li>"
                )
            success_list_html = "<ul class='success-list'>{}</ul>".format("\n".join(success_items))
        else:
            success_list_html = "<p class='hint'>無</p>"
        
        # 失敗部分
        failed_items = []
        for task in failed_tasks:
            day_name = task.get('day_name', '未知表單')
            status = task.get('status', 'unknown')
            
            if status == 'closed':
                reason_text = "表單已關閉或名額已滿"
            elif status == 'prep_failed':
                reason_text = "資料準備失敗 (URL/欄位錯誤)"
            elif status == 'submission_failed':
                reason_text = "提交失敗 (網路或伺服器錯誤)"
            else:
                reason_text = "未知失敗"
            
            failed_items.append(
                f"<li class='failure-item'><span class='chip chip-day'>{day_name}</span><span class='failure-reason'>{reason_text}</span></li>"
            )
        
        failed_list_html = "<ul class='failures-list'>{}</ul>".format("\n".join(failed_items))

        result_html = f"""
        <div class="status">
          <span class="badge failure">未全數成功</span>
          <div class="result-section">
            <p class="result-label">成功部分：</p>
            {success_list_html}
          </div>
          <div class="result-section" style="margin-top:16px;">
            <p class="result-label">失敗部分：</p>
            {failed_list_html}
            <p class="hint" style="margin-top:12px;">請查看程式的日誌輸出以了解詳細錯誤原因。</p>
          </div>
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

    /* 失敗列表 */
    .failures-list {{ list-style:none; padding:10px 0 0 0; margin:0; }}
    .failure-item {{
        display:flex; gap:10px; align-items:center;
        background:#FEF2F2; border:1px solid #FECACA; border-radius:10px;
        padding:8px 12px; margin-bottom:8px;
    }}
    .failure-item .chip-day {{
        background:#FEE2E2; border-color:#FCA5A5; color:#991B1B;
    }}
    .failure-reason {{ color:#991B1B; font-weight:700; font-size:13px; }}

    /* 成功列表 */
    .success-list {{ list-style:none; padding:10px 0 0 0; margin:0; }}
    .success-item {{
        display:flex; gap:10px; align-items:center;
        background:#ECFDF5; border:1px solid #A7F3D0; border-radius:10px;
        padding:8px 12px; margin-bottom:8px;
    }}
    .success-item .chip-day {{
        background:#D1FAE5; border-color:#6EE7B7; color:#065F46;
    }}
    .chip-success {{ background:#D1FAE5; border-color:#6EE7B7; color:#065F46; }}

    /* 結果區塊標籤 */
    .result-section {{ margin-top:8px; }}
    .result-label {{ font-weight:700; font-size:14px; color:#0F172A; margin-bottom:8px; }}

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
      .badge.success {{ color:#86EFAC; background:#052E1A; border-color:#14532d; }}
      .badge.failure {{ color:#FCA5A5; background:#2A0B0B; border-color:#7f1d1d; }}
      
      .failure-item {{ background:#2A0B0B; border-color:#7f1d1d; }}
      .failure-item .chip-day {{ background:#450a0a; border-color:#991B1B; color:#FCA5A5; }}
      .failure-reason {{ color:#FCA5A5; }}
      
      .success-item {{ background:#052E1A; border-color:#14532d; }}
      .success-item .chip-day {{ background:#064E3B; border-color:#065F46; color:#86EFAC; }}
      .chip-success {{ background:#064E3B; border-color:#065F46; color:#86EFAC; }}
      
      .result-label {{ color:#F3F4F6; }}
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
    recipient_email_str = os.getenv("RECIPIENT_EMAIL")  # 可能包含多個郵箱（逗號分隔）
    app_password = os.getenv("KEY")

    if not all([sender_email, recipient_email_str, app_password]):
        logging.error("郵件設定不完整，請檢查 mail_key.env 和 mail_settings.env 的設定。")
        if not sender_email:
            logging.error("-> 缺少 SENDER_EMAIL")
        if not recipient_email_str:
            logging.error("-> 缺少 RECIPIENT_EMAIL")
        if not app_password:
            logging.error("-> 缺少 KEY")
        return False

    # 解析收件人列表（支持逗號或分號分隔，並去除空白）
    recipient_emails = [email.strip() for email in recipient_email_str.replace(';', ',').split(',') if email.strip()]
    
    if not recipient_emails:
        logging.error("收件人郵箱列表為空，請檢查 RECIPIENT_EMAIL 設定。")
        return False
    
    logging.info(f"收件人列表：{', '.join(recipient_emails)}")

    # --- 建立郵件內容（HTML，無 emoji） ---
    subject = "自動填寫工作劃假表單總結報告"
    body = render_email_html(summary_data)

    # --- 設定郵件物件 ---
    msg = MIMEText(body, 'html', 'utf-8')
    msg['From'] = f'自動填寫劃假表單'  # 設定顯示名稱（不加引號以隱藏郵箱）
    msg['To'] = ', '.join(recipient_emails)  # 在郵件標頭中顯示所有收件人
    msg['Subject'] = Header(subject, 'utf-8')

    # --- 發送郵件 ---
    try:
        logging.info(f"正在嘗試發送郵件至 {len(recipient_emails)} 位收件人...")
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(sender_email, app_password)
            server.sendmail(sender_email, recipient_emails, msg.as_string())  # 傳遞列表
        logging.info(f"郵件發送成功，已發送至：{', '.join(recipient_emails)}")
        return True
    except smtplib.SMTPAuthenticationError:
        logging.error("郵件發送失敗：SMTP 驗證錯誤。請檢查 SENDER_EMAIL 與 KEY 是否正確。")
        return False
    except Exception as e:
        logging.error(f"郵件發送時發生未預期的錯誤：{e}")
        return False
