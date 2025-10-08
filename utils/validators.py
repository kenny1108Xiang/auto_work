"""
Form validation utilities
"""


async def check_form_closed(page) -> bool:
    """
    Check if form is closed (displays "not accepting responses")
    Returns True if form is closed
    """
    try:
        # Try to find closed form indicators
        closed_patterns = [
            "不接受回應",
            "不再接受回應",
            "已停止接受回應",
            "停止接受回應",
            "不接受填寫",
            "已關閉",
            "劃假已滿，如有相關問題可聯繫班次主管與排班組。"
        ]
        
        for pattern in closed_patterns:
            try:
                element = page.get_by_text(pattern)
                if await element.count() > 0:
                    print(f"偵測到表單已關閉: 找到「{pattern}」字樣")
                    return True
            except Exception:
                continue
        
        return False
    except Exception:
        return False

