import os
from dotenv import load_dotenv

load_dotenv()

class Config:
    BOT_TOKEN = os.getenv("BOT_TOKEN")
    ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
    ADMIN_USERNAME = os.getenv("ADMIN_USERNAME", "")
    
    # YouTube API
    YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
    
    # Лимиты по умолчанию
    DEFAULT_MAX_PROJECTS = int(os.getenv("DEFAULT_MAX_PROJECTS", "1"))
    DEFAULT_MAX_SOURCES_PER_PROJECT = int(os.getenv("DEFAULT_MAX_SOURCES_PER_PROJECT", "3"))
    DEFAULT_CHECK_INTERVAL = int(os.getenv("DEFAULT_CHECK_INTERVAL", "60"))
    
    # Настройки публикации
    DEFAULT_POST_INTERVAL_HOURS = int(os.getenv("DEFAULT_POST_INTERVAL_HOURS", "2"))
    MIN_POST_INTERVAL_MINUTES = int(os.getenv("MIN_POST_INTERVAL_MINUTES", "30"))
    DEFAULT_ACTIVE_HOURS_START = int(os.getenv("DEFAULT_ACTIVE_HOURS_START", "8"))
    DEFAULT_ACTIVE_HOURS_END = int(os.getenv("DEFAULT_ACTIVE_HOURS_END", "22"))
    
    # Глобальные настройки
    SHOW_SOURCE_SIGNATURE = os.getenv("SHOW_SOURCE_SIGNATURE", "false").lower() == "true"
    
    TIMEZONE = "Europe/Moscow"
    
    # Пути
    DATA_DIR = "data"
    DB_PATH = os.path.join(DATA_DIR, "bot.db")
    TEMP_DIR = "temp"
    BACKUP_DIR = "backups"
    
    # Настройки YouTube API
    YOUTUBE_MAX_RESULTS = int(os.getenv("YOUTUBE_MAX_RESULTS", "50"))
    YOUTUBE_SEARCH_DAYS = int(os.getenv("YOUTUBE_SEARCH_DAYS", "7"))
    
    @classmethod
    def validate(cls):
        if not cls.BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        if not cls.YOUTUBE_API_KEY:
            raise ValueError("YOUTUBE_API_KEY is required")
        if not cls.ADMIN_ID:
            raise ValueError("ADMIN_ID is required")

Config.validate()