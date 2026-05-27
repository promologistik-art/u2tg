from sqlalchemy import Column, Integer, String, BigInteger, Boolean, DateTime, JSON, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timedelta

Base = declarative_base()


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True)
    telegram_id = Column(BigInteger, unique=True, nullable=False)
    username = Column(String, nullable=True)
    full_name = Column(String, nullable=True)
    is_admin = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    trial_ends_at = Column(DateTime, default=lambda: datetime.utcnow() + timedelta(days=5))
    subscription_active = Column(Boolean, default=False)
    subscription_ends_at = Column(DateTime, nullable=True)
    tariff = Column(String, default="trial")
    
    max_projects = Column(Integer, default=1)
    max_sources_per_project = Column(Integer, default=3)
    min_post_interval_minutes = Column(Integer, default=120)
    min_check_interval_minutes = Column(Integer, default=60)
    
    posts_parsed_today = Column(Integer, default=0)
    posts_posted_today = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)
    
    last_trial_warning_sent = Column(DateTime, nullable=True)
    last_subscription_warning_sent = Column(DateTime, nullable=True)


class Project(Base):
    __tablename__ = "projects"
    id = Column(Integer, primary_key=True)
    user_id = Column(BigInteger, ForeignKey("users.telegram_id"), nullable=False)
    name = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    check_interval_minutes = Column(Integer, default=60)
    post_interval_hours = Column(Integer, default=2)
    active_hours_start = Column(Integer, default=8)
    active_hours_end = Column(Integer, default=22)
    signature = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    posts_parsed_today = Column(Integer, default=0)
    posts_posted_today = Column(Integer, default=0)
    last_reset = Column(DateTime, default=datetime.utcnow)


class SourceChannel(Base):
    __tablename__ = "source_channels"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    user_id = Column(BigInteger, nullable=True)
    
    # Общие поля
    name = Column(String, nullable=False)  # Название источника (для отображения)
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    last_parsed = Column(DateTime, nullable=True)
    last_post_url = Column(String, nullable=True)
    
    # YouTube-specific
    source_type = Column(String, default="channel")  # channel, link, search
    youtube_channel_id = Column(String, nullable=True)  # Для channel
    youtube_link_url = Column(String, nullable=True)  # Для link
    youtube_search_query = Column(String, nullable=True)  # Для search
    youtube_country = Column(String, nullable=True)  # Код страны (US, RU, etc) для search
    youtube_category = Column(String, nullable=True)  # ID категории для search
    youtube_content_type = Column(String, default="all")  # all, shorts, long
    
    # Критерии отбора
    criteria = Column(JSON, default={})  # min_views, min_likes, min_comments
    media_filter = Column(String, default="all")  # all, shorts_only, long_only
    remove_original_text = Column(Boolean, default=False)
    max_video_duration = Column(Integer, nullable=True)  # в секундах
    exclude_phrases = Column(String, nullable=True)  # стоп-фразы в заголовке/описании
    include_keywords = Column(String, nullable=True)  # ключевые слова через запятую
    max_age_hours = Column(Integer, default=24)  # максимальный возраст видео в часах


class TargetChannel(Base):
    __tablename__ = "target_channels"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=True)
    user_id = Column(BigInteger, nullable=True)
    
    platform = Column(String, default="telegram")
    
    channel_id = Column(BigInteger, nullable=True)
    channel_username = Column(String, nullable=True)
    channel_title = Column(String, nullable=True)
    
    is_active = Column(Boolean, default=True)
    added_at = Column(DateTime, default=datetime.utcnow)
    last_posted = Column(DateTime, nullable=True)


class ParsedPost(Base):
    __tablename__ = "parsed_posts"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    source_channel_id = Column(Integer, nullable=False)
    post_url = Column(String, nullable=False)
    parsed_at = Column(DateTime, default=datetime.utcnow)
    
    __table_args__ = (UniqueConstraint('project_id', 'post_url', name='uq_project_post'),)


class PostQueue(Base):
    __tablename__ = "post_queue"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    target_channel_id = Column(BigInteger, nullable=False)
    platform = Column(String, default="telegram")
    post_data = Column(JSON, nullable=False)
    scheduled_time = Column(DateTime, nullable=False)
    status = Column(String, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    published_at = Column(DateTime, nullable=True)
    error_message = Column(String, nullable=True)


class PublishedPost(Base):
    __tablename__ = "published_posts"
    id = Column(Integer, primary_key=True)
    project_id = Column(Integer, ForeignKey("projects.id"), nullable=False)
    target_channel_id = Column(BigInteger, nullable=False)
    platform = Column(String, default="telegram")
    source_channel_username = Column(String, nullable=False)
    post_url = Column(String, nullable=False)
    post_data = Column(JSON, nullable=True)
    published_at = Column(DateTime, default=datetime.utcnow)