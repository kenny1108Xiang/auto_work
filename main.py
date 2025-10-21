#!/usr/bin/env python3

import requests
import re
import logging
import sys
import time
from datetime import datetime, timedelta, time as dt_time
from concurrent.futures import ThreadPoolExecutor, as_completed
from get_field_id import resolve_short_url, fetch_form_entry_ids_for_day
from mail.send_mail import send_summary_email

# --- 以下的程式碼保持不變，直到 submit_form 函式 ---

# 設定 logging
logging.basicConfig(
    level=logging.INFO, 
    format='%(asctime)s.%(msecs)03d - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

# 中文星期對應數字
DAY_MAP = {
    '一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '日': 7
}

DAY_NAMES = ['', '星期一', '星期二', '星期三', '星期四', '星期五', '星期六', '星期日']


def read_config_file(file_path="data.txt"):
    """
    讀取設定檔並解析內容。
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        if len(lines) < 4:
            logging.error(f"設定檔 {file_path} 格式不正確，至少需要 4 行。")
            return None
        
        # 解析姓名
        name_line = lines[0].strip()
        if not name_line.startswith('姓名:'):
            logging.error("設定檔第一行格式錯誤，應為「姓名:」")
            return None
        name = name_line.split(':', 1)[1].strip()
        if not name:
            logging.error("姓名不可為空")
            return None
        
        # 解析請假星期
        days_line = lines[1].strip()
        if not days_line.startswith('請假星期:'):
            logging.error("設定檔第二行格式錯誤，應為「請假星期:」")
            return None
        days_str = days_line.split(':', 1)[1].strip()
        if not days_str:
            logging.error("請假星期不可為空")
            return None
        
        # 解析星期（用頓號分隔）
        day_chars = [d.strip() for d in days_str.split('、') if d.strip()]
        days = []
        for day_char in day_chars:
            if day_char not in DAY_MAP:
                logging.error(f"無效的星期：{day_char}，請使用一、二、三、四、五、六、日")
                return None
            days.append(DAY_MAP[day_char])
        
        if not days:
            logging.error("請假星期不可為空")
            return None
        
        # 解析星期六原因
        reason_sat_line = lines[2].strip()
        if not reason_sat_line.startswith('星期六原因:'):
            logging.error("設定檔第三行格式錯誤，應為「星期六原因:」")
            return None
        reason_sat = reason_sat_line.split(':', 1)[1].strip()
        
        # 解析星期日原因
        reason_sun_line = lines[3].strip()
        if not reason_sun_line.startswith('星期日原因:'):
            logging.error("設定檔第四行格式錯誤，應為「星期日原因:」")
            return None
        reason_sun = reason_sun_line.split(':', 1)[1].strip()
        
        return {
            'name': name,
            'days': sorted(days),
            'reason_sat': reason_sat,
            'reason_sun': reason_sun
        }
    
    except FileNotFoundError:
        logging.error(f"找不到設定檔：{file_path}")
        return None
    except Exception as e:
        logging.error(f"讀取設定檔時發生錯誤：{e}")
        return None


def validate_config(config):
    """
    驗證設定檔內容，特別是原因字數。
    """
    days = config['days']
    reason_sat = config['reason_sat']
    reason_sun = config['reason_sun']
    
    # 檢查是否需要星期六原因
    if 6 in days:
        if not reason_sat:
            print("\n錯誤：請假星期包含「星期六」，但未填寫星期六原因")
            print("請在 data.txt 的第三行填寫至少 15 個字的原因（不含空白）")
            return False
        
        # 計算字數（不含空白）
        reason_sat_no_space = reason_sat.replace(' ', '').replace('\t', '').replace('\n', '')
        char_count = len(reason_sat_no_space)
        
        if char_count < 15:
            need_more = 15 - char_count
            print(f"\n錯誤：星期六原因字數不足")
            print(f"   需要填寫的表單：星期六")
            print(f"   目前字數：{char_count} 字（不含空白）")
            print(f"   還需補充：{need_more} 字")
            print(f"   最少需要：15 字")
            return False
    
    # 檢查是否需要星期日原因
    if 7 in days:
        if not reason_sun:
            print("\n錯誤：請假星期包含「星期日」，但未填寫星期日原因")
            print("請在 data.txt 的第四行填寫至少 15 個字的原因（不含空白）")
            return False
        
        # 計算字數（不含空白）
        reason_sun_no_space = reason_sun.replace(' ', '').replace('\t', '').replace('\n', '')
        char_count = len(reason_sun_no_space)
        
        if char_count < 15:
            need_more = 15 - char_count
            print(f"\n錯誤：星期日原因字數不足")
            print(f"   需要填寫的表單：星期日")
            print(f"   目前字數：{char_count} 字（不含空白）")
            print(f"   還需補充：{need_more} 字")
            print(f"   最少需要：15 字")
            return False
    
    return True


def display_config(config):
    """
    顯示設定檔內容給使用者確認。
    """
    print("\n" + "=" * 60)
    print("讀取到的設定內容")
    print("=" * 60)
    
    print(f"\n姓名：{config['name']}")
    
    day_list = [DAY_NAMES[d] for d in config['days']]
    print(f"請假星期：{' 、 '.join(day_list)}")
    
    if 6 in config['days']:
        reason_sat_no_space = config['reason_sat'].replace(' ', '').replace('\t', '').replace('\n', '')
        char_count = len(reason_sat_no_space)
        print(f"星期六原因：{config['reason_sat']} ({char_count} 字)")
    
    if 7 in config['days']:
        reason_sun_no_space = config['reason_sun'].replace(' ', '').replace('\t', '').replace('\n', '')
        char_count = len(reason_sun_no_space)
        print(f"星期日原因：{config['reason_sun']} ({char_count} 字)")
    
    print("=" * 60)

# --- 函式修改與新增 ---

def prepare_submission_data(day_number, mode, name, reason=None, leave_option="休假"):
    """
    預處理單一表單的提交資料，但不實際提交。
    返回一個包含所有提交所需資訊的字典，如果準備失敗則返回 None。
    """
    day_name = DAY_NAMES[day_number]
    logging.info(f"[{day_name}] 開始預先準備提交資料...")
    
    # 步驟 1: 解析 URL
    viewform_url = resolve_short_url(day_number, mode)
    if not viewform_url:
        return None
    formresponse_url = viewform_url.replace('/viewform', '/formResponse')
    
    # 步驟 2: 取得 fbzx token
    try:
        response_get = requests.get(viewform_url)
        response_get.raise_for_status()
        match = re.search(r'name="fbzx" value="([^"]+)"', response_get.text)
        if not match:
            logging.error(f"[{day_name}] 找不到 fbzx token。")
            return None
        fbzx = match.group(1)
    except requests.exceptions.RequestException as e:
        logging.error(f"[{day_name}] 準備 token 時無法訪問表單頁面: {e}")
        return None
        
    # 步驟 3: 取得欄位 ID
    name_entry, option_entry, reason_entry = fetch_form_entry_ids_for_day(viewform_url, day_number)
    if not name_entry or not option_entry or (day_number >= 6 and not reason_entry):
        logging.error(f"[{day_name}] 無法取得必要的欄位 ID。")
        return None
        
    # 步驟 4: 組合 payload
    payload = {"fbzx": fbzx}
    user_data = {name_entry: name, option_entry: leave_option}
    if day_number >= 6 and reason:
        user_data[reason_entry] = reason
    payload.update(user_data)
    
    logging.info(f"[{day_name}] 資料準備完成。")
    
    # 回傳所有提交時需要的資訊
    return {
        "day_number": day_number,
        "day_name": day_name,
        "url": formresponse_url,
        "headers": {'Referer': viewform_url},
        "payload": payload
    }


def execute_submission(submission_data):
    """
    執行單一已準備好的表單提交任務。
    """
    day_name = submission_data["day_name"]
    logging.info(f"[{day_name}] 正在提交...")
    
    try:
        with requests.Session() as session:
            response_post = session.post(
                submission_data["url"],
                headers=submission_data["headers"],
                data=submission_data["payload"]
            )
            response_post.raise_for_status()
            
            if response_post.status_code == 200:
                logging.info(f"[{day_name}] 提交成功！")
                return submission_data["day_number"], True
            else:
                logging.error(f"[{day_name}] 提交失敗，狀態碼：{response_post.status_code}")
                return submission_data["day_number"], False
                
    except requests.exceptions.RequestException as e:
        logging.error(f"[{day_name}] 提交時發生錯誤： {e}")
        return submission_data["day_number"], False


def wait_for_scheduled_time():
    """
    計算並等待直到下一個星期三的 13:59:59.500。
    """
    now = datetime.now()
    # 星期三的 weekday() 是 2 (星期一為0)
    days_until_wednesday = (2 - now.weekday() + 7) % 7
    
    # 如果今天是星期三，且時間已超過 14:00，則目標是下週的星期三
    if days_until_wednesday == 0 and now.time() >= dt_time(14, 0):
        days_until_wednesday = 7
        
    target_date = now.date() + timedelta(days=days_until_wednesday)
    # 目標時間設為 13:59:59.350
    target_datetime = datetime.combine(target_date, dt_time(13, 59, 59, 350000))
    
    wait_seconds = (target_datetime - now).total_seconds()
    
    if wait_seconds <= 0:
        print("目標時間已過，將立即執行提交。")
        return
        
    print("\n" + "=" * 60)
    print(f"已設定排程，將在以下時間點提交表單：")
    print(f"   {target_datetime.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]}")
    print("=" * 60)

    # 倒數計時顯示
    try:
        while wait_seconds > 0:
            mins, secs = divmod(wait_seconds, 60)
            hours, mins = divmod(mins, 60)
            days, hours = divmod(hours, 24)
            
            timer_str = f"距離提交還有: {int(days)}天 {int(hours):02d}時 {int(mins):02d}分 {int(secs):02d}秒"
            print(timer_str, end='\r')
            
            # 決定 sleep 的時間，越接近目標時間，檢查頻率越高
            if wait_seconds > 60:
                time.sleep(1)
            elif wait_seconds > 1:
                time.sleep(0.1)
            else:
                # 最後一秒高精度等待
                time.sleep(wait_seconds)
                break
            
            wait_seconds = (target_datetime - datetime.now()).total_seconds()
        
        print("\n時間到達，立即開始提交！")

    except KeyboardInterrupt:
        print("\n\n使用者手動中斷等待，程式結束。")
        sys.exit(0)


# --- 主程式修改 ---
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("Google 表單自動填寫工具 (多執行緒/排程版)")
    print("=" * 60 + "\n")
    
    # 讀取並驗證設定
    config = read_config_file("data.txt")
    if not config:
        sys.exit(1)
    
    display_config(config)
    
    if not validate_config(config):
        sys.exit(1)
    
    # 使用者確認
    confirm = input("\n請確認以上設定是否正確 (Y/n): ").strip().lower()
    if confirm and confirm not in ['y', 'yes', '是']:
        print("\n使用者取消操作")
        sys.exit(0)
    
    # 選擇模式
    print("\n" + "-" * 60)
    while True:
        mode_input = input("請選擇執行模式 (0=測試, 1=正式): ").strip()
        if mode_input in ['0', '1']:
            mode = int(mode_input)
            break
        else:
            print("✗ 請輸入 0 或 1")
    
    # --- 資料預處理階段 ---
    print("\n" + "=" * 60)
    print("開始預先準備所有表單資料...")
    print("=" * 60)
    
    prepared_tasks = []
    with ThreadPoolExecutor(max_workers=len(config['days'])) as executor:
        # 使用多執行緒來加速資料準備過程
        future_to_day = {
            executor.submit(
                prepare_submission_data,
                day_number, mode, config['name'], 
                config['reason_sat'] if day_number == 6 else config['reason_sun'] if day_number == 7 else None
            ): day_number for day_number in config['days']
        }
        
        for future in as_completed(future_to_day):
            result = future.result()
            if result:
                prepared_tasks.append(result)
            else:
                day_num = future_to_day[future]
                logging.error(f"[{DAY_NAMES[day_num]}] 資料準備失敗，無法繼續。")
                print("\n發生錯誤，程式結束。")
                sys.exit(1)

    print("\n所有表單資料均已準備完成！")
    
    # --- 根據模式決定是否等待 ---
    if mode == 1:
        wait_for_scheduled_time()
    else: # mode == 0
        print("\n測試模式，立即開始提交...")
        
    # --- 執行提交階段 ---
    print("\n" + "=" * 60)
    success_count = 0
    fail_count = 0
    
    with ThreadPoolExecutor(max_workers=len(prepared_tasks)) as executor:
        future_to_task = {executor.submit(execute_submission, task): task for task in prepared_tasks}
        
        for future in as_completed(future_to_task):
            try:
                day_num, success = future.result()
                day_name = DAY_NAMES[day_num]
                if success:
                    success_count += 1
                    print(f"{day_name} 提交成功")
                else:
                    fail_count += 1
                    print(f"{day_name} 提交失敗")
            except Exception as e:
                fail_count += 1
                task_name = future_to_task[future]['day_name']
                logging.error(f"處理 [{task_name}] 任務時發生未預期的錯誤: {e}")

    # 顯示總結
    print("\n" + "=" * 60)
    print("提交總結")
    print("=" * 60)
    print(f"成功：{success_count} 個表單")
    print(f"失敗：{fail_count} 個表單")
    print(f"總計：{success_count + fail_count} 個表單")
    print("=" * 60 + "\n")

    # --- 發送郵件總結 ---
    print("=" * 60)
    print("正在準備並發送總結郵件...")
    print("=" * 60)

    # 準備郵件內容
    submitted_days = [DAY_NAMES[d] for d in config['days']]
    reasons = {}
    if 6 in config['days']:
        reasons['sat'] = config['reason_sat']
    if 7 in config['days']:
        reasons['sun'] = config['reason_sun']
    
    failed_days_list = [task['day_name'] for task in prepared_tasks if task['day_number'] not in [res[0] for res in [f.result() for f in as_completed(future_to_task) if f.result()[1]] ]]

    summary_data = {
        'submitted_days': submitted_days,
        'reasons': reasons,
        'all_success': fail_count == 0,
        'failed_days': failed_days_list
    }

    # 發送郵件
    email_sent = send_summary_email(summary_data)
    if email_sent:
        print("總結郵件已成功發送。")
    else:
        print("發送總結郵件失敗，請檢查日誌。")
    
    print("\n所有任務已完成！")