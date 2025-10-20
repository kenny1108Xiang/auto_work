#!/usr/bin/env python3

import requests
import re
import logging
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from get_field_id import resolve_short_url, fetch_form_entry_ids_for_day

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
    
    參數:
        file_path: 設定檔路徑
    
    返回:
        dict: {
            'name': 姓名,
            'days': [星期數字列表],
            'reason_sat': 星期六原因,
            'reason_sun': 星期日原因
        }
        失敗則返回 None
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
    
    參數:
        config: read_config_file() 返回的設定字典
    
    返回:
        bool: 驗證是否通過
    """
    days = config['days']
    reason_sat = config['reason_sat']
    reason_sun = config['reason_sun']
    
    # 檢查是否需要星期六原因
    if 6 in days:
        if not reason_sat:
            print("\n❌ 錯誤：請假星期包含「星期六」，但未填寫星期六原因")
            print("請在 data.txt 的第三行填寫至少 15 個字的原因（不含空白）")
            return False
        
        # 計算字數（不含空白）
        reason_sat_no_space = reason_sat.replace(' ', '').replace('\t', '').replace('\n', '')
        char_count = len(reason_sat_no_space)
        
        if char_count < 15:
            need_more = 15 - char_count
            print(f"\n❌ 錯誤：星期六原因字數不足")
            print(f"   需要填寫的表單：星期六")
            print(f"   目前字數：{char_count} 字（不含空白）")
            print(f"   還需補充：{need_more} 字")
            print(f"   最少需要：15 字")
            return False
    
    # 檢查是否需要星期日原因
    if 7 in days:
        if not reason_sun:
            print("\n❌ 錯誤：請假星期包含「星期日」，但未填寫星期日原因")
            print("請在 data.txt 的第四行填寫至少 15 個字的原因（不含空白）")
            return False
        
        # 計算字數（不含空白）
        reason_sun_no_space = reason_sun.replace(' ', '').replace('\t', '').replace('\n', '')
        char_count = len(reason_sun_no_space)
        
        if char_count < 15:
            need_more = 15 - char_count
            print(f"\n❌ 錯誤：星期日原因字數不足")
            print(f"   需要填寫的表單：星期日")
            print(f"   目前字數：{char_count} 字（不含空白）")
            print(f"   還需補充：{need_more} 字")
            print(f"   最少需要：15 字")
            return False
    
    return True


def display_config(config):
    """
    顯示設定檔內容給使用者確認。
    
    參數:
        config: read_config_file() 返回的設定字典
    """
    print("\n" + "=" * 60)
    print("📋 讀取到的設定內容")
    print("=" * 60)
    
    print(f"\n👤 姓名：{config['name']}")
    
    day_list = [DAY_NAMES[d] for d in config['days']]
    print(f"📅 請假星期：{' 、 '.join(day_list)}")
    
    if 6 in config['days']:
        reason_sat_no_space = config['reason_sat'].replace(' ', '').replace('\t', '').replace('\n', '')
        char_count = len(reason_sat_no_space)
        print(f"📝 星期六原因：{config['reason_sat']} ({char_count} 字)")
    
    if 7 in config['days']:
        reason_sun_no_space = config['reason_sun'].replace(' ', '').replace('\t', '').replace('\n', '')
        char_count = len(reason_sun_no_space)
        print(f"📝 星期日原因：{config['reason_sun']} ({char_count} 字)")
    
    print("=" * 60)


def submit_form(day_number, mode, name, reason=None, leave_option="休假"):
    """
    提交 Google 表單。
    
    根據星期數字自動決定需要填寫的欄位：
    - 星期一到五 (1-5)：只提交姓名和選項
    - 星期六到日 (6-7)：提交姓名、選項和原因

    Args:
        day_number (int): 星期數字 (1-7)
        mode (int): 執行模式 (0=測試, 1=正式)
        name (str): 姓名
        reason (str, optional): 原因 (星期六、日必填)
        leave_option (str, optional): 休假選項，預設為 "休假"
    
    Returns:
        tuple: (day_number, bool) -> (星期數字, 是否成功提交)
    """
    day_name = DAY_NAMES[day_number]
    
    # 步驟 1: 解析短網址取得完整的表單 URL
    viewform_url = resolve_short_url(day_number, mode)
    if not viewform_url:
        logging.error(f"[{day_name}] 無法取得表單 URL，提交失敗。")
        return day_number, False
    
    # 步驟 2: 生成 formResponse URL
    formresponse_url = viewform_url.replace('/viewform', '/formResponse')
    
    # 步驟 3: 建立 session 並訪問頁面取得 fbzx token
    session = requests.Session()
    try:
        response_get = session.get(viewform_url)
        response_get.raise_for_status()
        
        match = re.search(r'name="fbzx" value="([^"]+)"', response_get.text)
        if not match:
            logging.error(f"[{day_name}] 在頁面中找不到必要的 fbzx token。")
            return day_number, False
        
        payload = {"fbzx": match.group(1)}
        logging.info(f"[{day_name}] 成功取得 fbzx token。")

    except requests.exceptions.RequestException as e:
        logging.error(f"[{day_name}] 無法訪問表單頁面以取得 token。 {e}")
        return day_number, False
    
    # 步驟 4: 取得表單欄位 ID
    name_entry, option_entry, reason_entry = fetch_form_entry_ids_for_day(viewform_url, day_number)
    
    # 檢查必要欄位
    if not name_entry or not option_entry:
        logging.error(f"[{day_name}] 無法取得必要的表單欄位 ID (姓名或選項)。")
        return day_number, False
    
    # 星期六、日需要檢查 reason_entry
    if day_number >= 6 and not reason_entry:
        logging.error(f"[{day_name}] 需要原因欄位，但無法取得 reason_entry ID。")
        return day_number, False
    
    # 步驟 5: 組合使用者資料
    user_data = {
        name_entry: name,
        option_entry: leave_option
    }
    
    # 只在星期六、日才加入原因欄位
    if day_number >= 6 and reason:
        user_data[reason_entry] = reason
    
    payload.update(user_data)
    
    # 步驟 6: 提交表單
    headers = {'Referer': viewform_url}
    
    logging.info(f"[{day_name}] 正在提交資料：姓名='{name}', 選項='{leave_option}'" + 
                 (f", 原因='{reason}'" if day_number >= 6 and reason else ""))
    
    try:
        response_post = session.post(formresponse_url, headers=headers, data=payload)
        response_post.raise_for_status()
        
        if response_post.status_code == 200:
            logging.info(f"[{day_name}] ✅ 提交成功！")
            return day_number, True
        else:
            logging.error(f"[{day_name}] ❌ 提交失敗，狀態碼：{response_post.status_code}")
            return day_number, False
            
    except requests.exceptions.RequestException as e:
        logging.error(f"[{day_name}] ❌ 提交時發生錯誤： {e}")
        return day_number, False


# --- 如何使用 ---
if __name__ == "__main__":
    print("\n" + "=" * 60)
    print("🚀 Google 表單自動填寫工具 (多執行緒版)")
    print("=" * 60 + "\n")
    
    # 讀取設定檔
    logging.info("正在讀取設定檔 data.txt...")
    config = read_config_file("data.txt")
    
    if not config:
        print("\n❌ 無法讀取設定檔，程式結束")
        sys.exit(1)
    
    # 顯示設定內容
    display_config(config)
    
    # 驗證設定
    if not validate_config(config):
        print("\n❌ 設定驗證失敗，程式結束\n")
        sys.exit(1)
    
    # 詢問使用者確認
    print("\n請確認以上設定是否正確")
    confirm = input("是否繼續？(Y/n): ").strip().lower()
    if confirm and confirm not in ['y', 'yes', '是']:
        print("\n⚠️  使用者取消操作")
        sys.exit(0)
    
    # 詢問執行模式
    print("\n" + "-" * 60)
    while True:
        mode_input = input("請選擇執行模式 (0=測試, 1=正式): ").strip()
        if mode_input in ['0', '1']:
            mode = int(mode_input)
            mode_name = "測試模式" if mode == 0 else "正式模式"
            print(f"✓ 已選擇: {mode_name}")
            break
        else:
            print("✗ 請輸入 0 或 1")
    
    print("\n" + "=" * 60)
    print("開始併發提交表單...")
    print("=" * 60 + "\n")
    
    # 對每個請假日期併發提交表單
    success_count = 0
    fail_count = 0
    
    with ThreadPoolExecutor(max_workers=len(config['days'])) as executor:
        futures = []
        for day_number in config['days']:
            reason = None
            if day_number == 6:
                reason = config['reason_sat']
            elif day_number == 7:
                reason = config['reason_sun']
            
            future = executor.submit(
                submit_form,
                day_number=day_number,
                mode=mode,
                name=config['name'],
                reason=reason,
                leave_option="休假"
            )
            futures.append(future)
        
        for future in as_completed(futures):
            try:
                day_num, success = future.result()
                day_name = DAY_NAMES[day_num]
                if success:
                    success_count += 1
                    print(f"✅ {day_name} 提交成功")
                else:
                    fail_count += 1
                    print(f"❌ {day_name} 提交失敗")
            except Exception as e:
                fail_count += 1
                logging.error(f"處理任務時發生未預期的錯誤: {e}")

    # 顯示總結
    print("\n" + "=" * 60)
    print("📊 提交總結")
    print("=" * 60)
    print(f"✅ 成功：{success_count} 個表單")
    print(f"❌ 失敗：{fail_count} 個表單")
    print(f"📋 總計：{success_count + fail_count} 個表單")
    print("=" * 60 + "\n")