# Google Forms Auto-Fill Bot

自動化填寫 Google 表單的機器人，支援精準定時送出、郵件通知、失敗重試等功能。

## 功能特色

- **精準定時送出**：可在星期三 14:00:00 準時送出表單（13:59:30 預填，14:00:00 送出）
- **智能表單填寫**：自動填寫姓名、按下休假選項、填寫請假原因
- **失敗重試機制**：每個表單最多重試 2 次
- **自動截圖**：失敗時自動截圖保存，便於除錯
- **郵件通知系統（可選）**：
  - 執行前 5 分鐘寄送提醒郵件
  - 如果超時, 則寄送警告郵件（10 秒內未轉跳）
  - 第一次失敗立即通知郵件（附截圖）
  - 最後寄送總結郵件
- **多瀏覽器並行**：支援同時處理多個表單，每個表單獨立瀏覽器
- **特殊日期處理**：星期六、日需填寫請假原因（至少 15 字）
- **表單關閉檢測**：自動偵測表單是否已關閉

## 📁 專案結構

```
auto_work/
├── setup.py                   # 程式進入點（配置驗證 + 執行）
├── main.py                    # 主程式邏輯
├── config.json                # 主要配置檔案（包含所有設定）
├── config.json.example        # 配置檔案範例
│
├── config/                    # 配置模塊
│   ├── __init__.py
│   └── settings.py           # Python 配置（由 setup.py 自動生成）
│
├── core/                      # 核心功能模塊
│   ├── __init__.py
│   ├── form_filler.py        # FormFiller 類：表單填寫操作
│   ├── browser_manager.py    # BrowserManager 類：瀏覽器管理
│   └── scheduler.py          # Scheduler 類：時間控制與排程
│
├── utils/                     # 工具函數模塊
│   ├── __init__.py
│   ├── config_loader.py      # 配置讀取器（直接讀取 config.json）
│   ├── screenshot.py         # 截圖功能
│   └── validators.py         # 驗證函數
│
├── notifications/             # 通知模塊
│   ├── __init__.py
│   └── email_service.py      # EmailService 類：郵件服務
│
├── fail_img/                  # 失敗截圖保存目錄
│   └── .gitkeep
├── mail_key.env               # Gmail 應用程式密碼（選擇性）
└── requirements.txt           # 依賴套件
```

## 快速開始

### 環境需求

- **Python 3.9 或更高版本**（程式會自動檢查版本）
- **作業系統**：Windows / macOS / Linux

### 三步驟快速開始

#### 步驟 1：安裝

```bash
git clone https://github.com/kenny1108Xiang/auto_work.git
cd auto_work
pip install -r requirements.txt
playwright install
```

#### 步驟 2：建立配置檔案

複製範例檔案：
```bash
# Windows
copy config.json.example config.json

# macOS/Linux
cp config.json.example config.json
```

**這是唯一需要手動建立的配置檔案！** 所有資料都集中在這一個 JSON 檔案中。

編輯 `config.json`，填入所有必要資料：

```json
{
  "user": {
    "name": "您的姓名"  ← 修改這裡
  },
  "email": {
    "gmail_account": "your_email@gmail.com",  ← 修改這裡
    "recipient_email": "recipient@example.com",  ← 修改這裡
    "sender_name": "表單填寫機器人"
  },
  "dates": {
    "weekdays": ["三", "四", "六"],  ← 修改要填寫的星期
    "reasons": {
      "六": "因為家庭有重要事務需要處理所以請假",  ← 至少15字
      "日": "因為學校需要上課所以無法出勤請假"
    }
  },
  "forms_urls": [
    "https://forms.gle/GTjSPcJjtYJgb4qz8",  ← 如果 Line 群組有公布或修改網址, 請根據最新的網址填入, 目前截至 2025/10/08
    "https://forms.gle/M8Jdm8gCKiAMW2R28",
    "https://forms.gle/ArbaQXNe7R9oHYvJA",
    "https://forms.gle/eB7hcUUxoMYX5bap8",
    "https://forms.gle/sHV7kfMktfoX55K4A",
    "https://forms.gle/ctieTHBEbMoBRNe26",
    "https://forms.gle/uXW3XdYt7V3eLZbg7"
  ],
  "settings": {
    "headless": false,  ← true: 無頭模式, false: 顯示瀏覽器, 基本上不用改
    "min_reason_length": 15
  }
}
```

> **重要**：
> - `forms_urls` 必須包含 7 個 URL（星期一到星期日）
> - 星期六、日的 `reasons` 必須至少 15 個字（不含空白）
> - 只需在 `weekdays` 中列出要填寫的星期

### 郵件功能設定（選擇性）

郵件功能是**選擇性的**，如果不需要郵件通知，可以跳過此步驟。

每次執行 `python setup.py` 時，若發現沒有 `mail_key.env` 程式會詢問是否啟用郵件功能：
- 選擇「是」：需要輸入 Gmail 應用程式密碼
- 選擇「否」：程式正常執行，但不會發送任何郵件

Gmail 應用程式密碼取得方式：
> Google 帳戶 → 安全性 → 兩步驟驗證 → 應用程式密碼

#### 步驟 3：執行程式

```bash
python setup.py
```

程式會：
1. 驗證 `config.json` 內容並讓您確認
2. 詢問是否啟用郵件功能（選擇性）
3. 開始執行表單填寫

## 使用方法

### 執行程式

**重要：請使用 setup.py 作為進入點**

```bash
python setup.py
```

> **注意**：不要直接執行 `python main.py`，請使用 `setup.py` 作為進入點

### 執行模式選擇

程式會提示您選擇執行模式：

**1. 等到星期三下午 2 點再執行**
```
要等到『當週的星期三下午 2 點』再執行嗎？(y/n)：y
```
- 表單將在 13:59:30 開始填寫
- 14:00:00 準時送出
- 如果等待時間超過 5 分鐘，會在執行前 5 分鐘發送提醒郵件

**2. 立即執行**
```
要等到『當週的星期三下午 2 點』再執行嗎？(y/n)：n
要『馬上』執行嗎？(y/n)：y
```
- 立即開始填寫並送出表單

**3. 延遲 N 分鐘執行**
```
要等到『當週的星期三下午 2 點』再執行嗎？(y/n)：n
要『馬上』執行嗎？(y/n)：n
請輸入要等待的『分鐘數』（正整數）：10
```
- 等待指定分鐘數後執行

## 主要類別說明

### FormFiller (core/form_filler.py)
負責表單填寫操作
```python
- fill_name()              # 填寫姓名
- check_vacation()         # 選擇休假選項（星期日特殊處理）
- fill_reason()            # 填寫請假原因
- submit()                 # 提交表單
- fill_form_only()         # 只填寫不提交（預填功能）
- submit_filled_form()     # 提交已填寫的表單
```

### BrowserManager (core/browser_manager.py)
負責瀏覽器管理與執行流程
```python
- submit_single_form()                    # 單一表單提交
- submit_form_with_retry()                # 失敗重試機制
- run_in_isolated_browser()               # 獨立瀏覽器執行
- prefill_and_submit_at_exact_time()      # 預填 + 定時送出
```

### EmailService (notifications/email_service.py)
負責所有郵件通知
```python
- send_warning()            # 警告郵件（10 秒未轉跳）
- send_reminder()           # 提醒郵件（執行前 5 分鐘）
- send_immediate_failure()  # 即時失敗通知（第一次失敗）
- send_summary()            # 總結郵件（執行完成）
```

### Scheduler (core/scheduler.py)
負責時間控制與排程
```python
- next_wednesday_14()    # 計算下週三 14:00
- sleep_until()          # 精準睡眠到指定時間
- validate_time()        # 驗證執行時間
- prompt_choice()        # 互動式選擇執行模式
```

## 故障排除

### Python 版本錯誤
```
Error: Current Python version is 3.8.x
This program requires Python 3.9 or higher to run
```
**解決方案**：升級 Python 到 3.9 或更高版本

### 模塊導入錯誤
```
ModuleNotFoundError: No module named 'playwright'
```
**解決方案**：
```bash
pip install -r requirements.txt
playwright install
```

### 原因字數不足錯誤
```
❌ 錯誤：星期六的請假原因字數不足
目前原因：「家庭因素」
字數統計：4 個字（不含空白）
最低要求：15 個字（不含空白）
```
**解決方案**：在 `config.json` 的 `dates.reasons.六` 中增加原因字數至少 15 字

### 配置檔案找不到
```
❌ 錯誤：找不到 config.json
```
**解決方案**：
1. 確認已複製 `config.json.example` 為 `config.json`
2. 檢查檔案是否在專案根目錄

### 配置資料錯誤
執行 `python setup.py` 後，如果顯示配置資訊有誤：
1. 編輯 `config.json` 修改錯誤的資料
2. 重新執行 `python setup.py`

### 郵件發送失敗
**檢查項目**：
1. 確認已啟用郵件功能（執行 setup.py 時選擇「是」）
2. Gmail 帳號在 `config.json` 中是否正確
3. 應用程式密碼是否為 16 個字元
4. `mail_key.env` 檔案是否存在
5. `aiosmtplib` 套件是否已安裝

**如何重新設定郵件**：
1. 刪除 `mail_key.env` 檔案
2. 重新執行 `python setup.py`
3. 選擇啟用郵件功能並輸入新的密碼

### 表單無法點擊
**可能原因**：
1. 表單結構已變更
2. 網路連線問題
3. 表單已關閉

**解決方案**：檢查終端機輸出的錯誤訊息和 `fail_img/` 中的截圖

## 技術特點

### 精準時間控制
- 使用三階段睡眠策略：長睡（60 秒前）→ 秒級（1 秒前）→ 毫秒級收斂
- 精準度：±1-10 毫秒

### 智能選擇器策略
- 支援多種 DOM 結構變化
- 星期日特殊處理（無 aria-label 的表單）
- 失敗時自動嘗試 JavaScript 點擊

### 模塊化架構
- 配置集中化：所有設定在 `config/settings.py`
- 功能分層清晰：核心 → 工具 → 通知
- OOP 設計：便於擴展和維護

## 授權

此專案僅供個人學習和使用。

## 貢獻

歡迎提出 Issue 和 Pull Request！

---

**最後更新**：2025-10-08
**Python 版本**：3.9+
**主要依賴**：Playwright 1.55.0, aiosmtplib 3.0.2

