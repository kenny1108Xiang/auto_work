"""
Configuration loader - directly load from config.json
"""
import json
import sys
from pathlib import Path
from typing import List, Dict, Tuple

from config.settings import MIN_REASON_LENGTH


class ConfigLoader:
    """Load and validate configuration from config.json"""
    
    def __init__(self, config_path: str = "config.json"):
        self.config_path = Path(config_path)
        self.config = None
    
    def load(self) -> dict:
        """Load config.json"""
        if not self.config_path.exists():
            raise FileNotFoundError(f"找不到 {self.config_path}")
        
        with open(self.config_path, "r", encoding="utf-8") as f:
            self.config = json.load(f)
        
        return self.config
    
    def get_weekdays(self) -> List[str]:
        """Get requested weekdays from config"""
        if not self.config:
            self.load()
        
        return self.config.get('dates', {}).get('weekdays', [])
    
    def get_reasons(self) -> Dict[str, str]:
        """Get reason mapping from config"""
        if not self.config:
            self.load()
        
        return self.config.get('dates', {}).get('reasons', {})
    
    def get_form_urls(self) -> List[str]:
        """Get form URLs from config"""
        if not self.config:
            self.load()
        
        urls = self.config.get('forms_urls', [])
        if len(urls) != 7:
            raise ValueError(f"forms_urls 應包含 7 個 URL，對應星期一到星期日。目前有 {len(urls)} 個")
        
        return urls
    
    def validate_reasons(self, required_weekdays: List[str] = None) -> None:
        """Validate reason length for weekend days"""
        if not required_weekdays:
            return
        
        reasons = self.get_reasons()
        weekend_days_in_request = [day for day in required_weekdays if day in ["六", "日"]]
        
        if weekend_days_in_request:
            for weekday in weekend_days_in_request:
                if weekday not in reasons:
                    print(f"❌ 錯誤：config.json 的 dates.weekdays 中包含「星期{weekday}」")
                    print(f"但 dates.reasons 中找不到對應的原因說明")
                    print(f"請在 config.json 的 dates.reasons.{weekday} 中添加請假原因（至少{MIN_REASON_LENGTH}個字，不含空白）")
                    sys.exit(1)
                
                reason = reasons[weekday]
                reason_length = len(reason.replace(" ", "").replace("　", ""))
                
                if reason_length < MIN_REASON_LENGTH:
                    print(f"❌ 錯誤：星期{weekday}的請假原因字數不足")
                    print(f"目前原因：「{reason}」")
                    print(f"字數統計：{reason_length} 個字（不含空白）")
                    print(f"最低要求：{MIN_REASON_LENGTH} 個字（不含空白）")
                    print(f"缺少字數：{MIN_REASON_LENGTH - reason_length} 個字")
                    print(f"\n請修改 config.json 文件中 dates.reasons.{weekday} 的內容")
                    print(f"確保星期{weekday}的原因至少有{MIN_REASON_LENGTH}個字（不含空白）")
                    sys.exit(1)


# Global config loader instance
_config_loader = None


def get_config_loader() -> ConfigLoader:
    """Get global config loader instance"""
    global _config_loader
    if _config_loader is None:
        _config_loader = ConfigLoader()
    return _config_loader

