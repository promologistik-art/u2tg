import logging
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes, ConversationHandler
from sqlalchemy import select, update as sql_update, delete
from database import AsyncSessionLocal
from models import User, SourceChannel
from scrapers import YouTubeScraper
from .constants import (
    AWAITING_YOUTUBE_SOURCE_TYPE, AWAITING_YOUTUBE_CHANNEL_ID, AWAITING_YOUTUBE_LINK,
    AWAITING_YOUTUBE_SEARCH_QUERY, AWAITING_YOUTUBE_COUNTRY, AWAITING_YOUTUBE_CATEGORY,
    AWAITING_YOUTUBE_CONTENT_TYPE,
    AWAITING_VIEWS, AWAITING_REACTIONS, AWAITING_MEDIA_FILTER, AWAITING_REMOVE_TEXT,
    AWAITING_KEYWORDS, CURRENT_PROJECT_KEY
)
from .utils import require_project, get_sources_count, get_project_target, send_project_ready_message, check_action_limit, check_user_access

logger = logging.getLogger(__name__)

# Список стран для выбора
COUNTRIES = {
    'RU': 'Россия',
    'US': 'США',
    'GB': 'Великобритания',
    'DE': 'Германия',
    'FR': 'Франция',
    'IT': 'Италия',
    'ES': 'Испания',
    'JP': 'Япония',
    'KR': 'Корея',
    'IN': 'Индия',
    'BR': 'Бразилия',
    'MX': 'Мексика',
    'CA': 'Канада',
    'AU': 'Австралия',
    'UA': 'Украина',
    'KZ': 'Казахстан',
    'BY': 'Беларусь',
    'PL': 'Польша',
    'TR': 'Турция',
    'AE': 'ОАЭ'
}

# Список категорий YouTube (основные)
CATEGORIES = {
    '1': 'Фильмы и анимация',
    '2': 'Авто и транспорт',
    '10': 'Музыка',
    '15': 'Животные',
    '17': 'Спорт',
    '19': 'Путешествия',
    '20': 'Игры',
    '22': 'Люди и блоги',
    '23': 'Комедия',
    '24': 'Развлечения',
    '25': 'Новости и политика',
    '26': 'Как это работает',
    '27': 'Образование',
    '28': 'Наука и технологии',
    '29': 'Благотворительность',
    '30': 'Фильмы',
    '31': 'Аниме',
    '32': 'Действия и приключения',
    '33': 'Классические фильмы',
    '34': 'Комедии',
    '35': 'Документальные',
    '36': 'Драмы',
    '37': 'Семейные фильмы',
    '38': 'Ужасы',
    '39': 'Триллеры',
    '40': 'Мюзиклы',
    '41': 'Новости и политика',
    '42': 'Кулинария',
    '43': 'DIY',
    '44': 'Обзоры товаров',
    '45': 'Влоги',
    '46': 'Макияж и мода',
    '47': 'Аниме',
    '48': 'TikTok',
    '49': 'Шортсы'
}


async def add_source_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало добавления источника YouTube."""
    # Сохраняем текущий проект
    current_project = context.user_data.get(CURRENT_PROJECT_KEY)
    context.user_data.clear()
    if current_project:
        context.user_data[CURRENT_PROJECT_KEY] = current_project
    
    telegram_id = update.effective_user.id
    project = await require_project(update, context)
    
    if not project:
        return ConversationHandler.END
    
    has_access, message, user = await check_user_access(telegram_id)
    if not has_access:
        await update.message.reply_text(message)
        return ConversationHandler.END
    
    can_add, limit_msg = await check_action_limit(user, "add_source", project_id=project.id)
    if not can_add and not user.is_admin:
        await update.message.reply_text(f"❌ {limit_msg}")
        return ConversationHandler.END
    
    context.user_data['temp_project_id'] = project.id
    context.user_data['temp_project_name'] = project.name
    
    keyboard = [
        [InlineKeyboardButton("📺 Канал", callback_data="youtube_type_channel")],
        [InlineKeyboardButton("🔗 Ссылка на видео", callback_data="youtube_type_link")],
        [InlineKeyboardButton("🔍 Поиск", callback_data="youtube_type_search")],
    ]
    
    await update.message.reply_text(
        f"📥 Добавление источника в «{project.name}»\n\n"
        f"Выберите тип источника YouTube:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )
    return AWAITING_YOUTUBE_SOURCE_TYPE


async def youtube_source_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор типа источника YouTube."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data.replace("youtube_type_", "")
    context.user_data['youtube_source_type'] = choice
    
    if choice == "channel":
        await query.edit_message_text(
            "📺 <b>Добавление канала YouTube</b>\n\n"
            "Отправьте ID канала, @username или ссылку:\n"
            "• @channel\n"
            "• https://youtube.com/@channel\n"
            "• https://youtube.com/channel/UCxxxxx\n"
            "• UCxxxxx\n\n"
            "Пример: @durov или UCxxxxx",
            parse_mode="HTML"
        )
        return AWAITING_YOUTUBE_CHANNEL_ID
    
    elif choice == "link":
        await query.edit_message_text(
            "🔗 <b>Добавление ссылки на видео</b>\n\n"
            "Отправьте ссылку на видео YouTube:\n"
            "• https://youtube.com/watch?v=xxxxx\n"
            "• https://youtu.be/xxxxx\n"
            "• https://youtube.com/shorts/xxxxx",
            parse_mode="HTML"
        )
        return AWAITING_YOUTUBE_LINK
    
    elif choice == "search":
        await query.edit_message_text(
            "🔍 <b>Поиск видео</b>\n\n"
            "Введите поисковый запрос:\n"
            "Например: «как приготовить пиццу» или «нейросети 2026»",
            parse_mode="HTML"
        )
        return AWAITING_YOUTUBE_SEARCH_QUERY


async def youtube_channel_id_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод ID канала."""
    input_text = update.message.text.strip()
    
    async with YouTubeScraper() as scraper:
        channel_id = scraper._extract_channel_id(input_text)
        if not channel_id:
            await update.message.reply_text("❌ Не удалось распознать ID канала. Попробуйте ещё раз.")
            return AWAITING_YOUTUBE_CHANNEL_ID
        
        info = await scraper.get_channel_info(channel_id)
        if not info:
            await update.message.reply_text("❌ Канал не найден. Проверьте ID или повторите попытку.")
            return AWAITING_YOUTUBE_CHANNEL_ID
    
    context.user_data['temp_source'] = {
        'name': info['title'],
        'source_type': 'channel',
        'youtube_channel_id': channel_id,
        'project_id': context.user_data.get('temp_project_id'),
        'project_name': context.user_data.get('temp_project_name')
    }
    
    return await show_criteria_selection(update, context, info['title'])


async def youtube_link_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод ссылки на видео."""
    url = update.message.text.strip()
    
    async with YouTubeScraper() as scraper:
        video = await scraper.get_video_by_url(url)
        if not video:
            await update.message.reply_text("❌ Не удалось найти видео по ссылке. Проверьте URL.")
            return AWAITING_YOUTUBE_LINK
    
    context.user_data['temp_source'] = {
        'name': video['title'][:50],
        'source_type': 'link',
        'youtube_link_url': url,
        'project_id': context.user_data.get('temp_project_id'),
        'project_name': context.user_data.get('temp_project_name')
    }
    
    # Для ссылки на видео сразу добавляем в очередь (без критериев)
    return await add_link_source_direct(update, context, video)


async def youtube_search_query_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает ввод поискового запроса."""
    query = update.message.text.strip()
    if len(query) < 2:
        await update.message.reply_text("❌ Запрос должен быть длиннее 2 символов.")
        return AWAITING_YOUTUBE_SEARCH_QUERY
    
    context.user_data['youtube_search_query'] = query
    
    # Выбор страны
    keyboard = []
    row = []
    countries_list = list(COUNTRIES.items())
    for i, (code, name) in enumerate(countries_list):
        row.append(InlineKeyboardButton(name, callback_data=f"country_{code}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🌍 Все страны", callback_data="country_all")])
    
    await update.message.reply_text(
        f"🔍 <b>Выберите страну:</b>\n\n"
        f"Запрос: <code>{query}</code>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return AWAITING_YOUTUBE_COUNTRY


async def youtube_country_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор страны."""
    query = update.callback_query
    await query.answer()
    
    country = query.data.replace("country_", "")
    context.user_data['youtube_country'] = None if country == "all" else country
    
    # Выбор категории
    keyboard = []
    row = []
    categories_list = list(CATEGORIES.items())
    for i, (cat_id, name) in enumerate(categories_list):
        row.append(InlineKeyboardButton(name[:15], callback_data=f"category_{cat_id}"))
        if len(row) == 3:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("📂 Все категории", callback_data="category_all")])
    
    await query.edit_message_text(
        f"🔍 <b>Выберите категорию:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return AWAITING_YOUTUBE_CATEGORY


async def youtube_category_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор категории."""
    query = update.callback_query
    await query.answer()
    
    category = query.data.replace("category_", "")
    context.user_data['youtube_category'] = None if category == "all" else category
    
    # Выбор типа контента
    keyboard = [
        [InlineKeyboardButton("🎬 Все видео", callback_data="content_all")],
        [InlineKeyboardButton("📱 Только шортсы", callback_data="content_shorts")],
        [InlineKeyboardButton("📺 Обычные видео", callback_data="content_long")],
    ]
    
    await query.edit_message_text(
        f"🔍 <b>Выберите тип контента:</b>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return AWAITING_YOUTUBE_CONTENT_TYPE


async def youtube_content_type_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор типа контента."""
    query = update.callback_query
    await query.answer()
    
    content_type = query.data.replace("content_", "")
    context.user_data['youtube_content_type'] = content_type
    
    name = f"{context.user_data.get('youtube_search_query', 'поиск')}"
    
    context.user_data['temp_source'] = {
        'name': name,
        'source_type': 'search',
        'youtube_search_query': context.user_data.get('youtube_search_query'),
        'youtube_country': context.user_data.get('youtube_country'),
        'youtube_category': context.user_data.get('youtube_category'),
        'youtube_content_type': content_type,
        'project_id': context.user_data.get('temp_project_id'),
        'project_name': context.user_data.get('temp_project_name')
    }
    
    return await show_criteria_selection(update, context, name)


async def show_criteria_selection(update: Update, context: ContextTypes.DEFAULT_TYPE, source_name: str):
    """Показывает меню выбора критериев."""
    keyboard = [
        [InlineKeyboardButton("🎯 Свои критерии", callback_data="criteria_custom")],
        [InlineKeyboardButton("👁 1000+ просмотров", callback_data="criteria_views")],
        [InlineKeyboardButton("❤️ 50+ лайков", callback_data="criteria_likes")],
        [InlineKeyboardButton("👁+❤️ 500+ и 25+", callback_data="criteria_both")],
        [InlineKeyboardButton("⚡ Без критериев", callback_data="criteria_none")],
    ]
    
    if isinstance(update, Update) and update.callback_query:
        await update.callback_query.edit_message_text(
            f"✅ Источник: {source_name}\n\nВыберите критерии отбора:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    else:
        await update.message.reply_text(
            f"✅ Источник: {source_name}\n\nВыберите критерии отбора:",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
    return AWAITING_CRITERIA


async def add_source_criteria(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор критериев."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data.replace("criteria_", "")
    temp = context.user_data.get('temp_source')
    
    if not temp:
        await query.edit_message_text("❌ Ошибка: данные не найдены.")
        return ConversationHandler.END
    
    if choice == "custom":
        await query.edit_message_text(
            "📊 <b>Настройка критериев</b>\n\nВведите минимальное количество просмотров (0 = не учитывать):",
            parse_mode="HTML"
        )
        context.user_data['awaiting_criteria'] = 'views'
        return AWAITING_VIEWS
    
    elif choice == "views":
        criteria = {"min_views": 1000}
    elif choice == "likes":
        criteria = {"min_likes": 50}
    elif choice == "both":
        criteria = {"min_views": 500, "min_likes": 25}
    else:  # none
        criteria = {}
    
    context.user_data['temp_criteria'] = criteria
    return await show_media_filters(query, context, temp)


async def criteria_views_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод минимальных просмотров."""
    try:
        views = int(update.message.text.strip())
        if views < 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Введите целое число (0 = не учитывать):")
        return AWAITING_VIEWS
    
    context.user_data['temp_criteria_views'] = views
    await update.message.reply_text("📊 Введите минимальное количество лайков (0 = не учитывать):")
    return AWAITING_REACTIONS


async def criteria_reactions_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ввод минимальных лайков."""
    try:
        likes = int(update.message.text.strip())
        if likes < 0:
            raise ValueError
    except:
        await update.message.reply_text("❌ Введите целое число (0 = не учитывать):")
        return AWAITING_REACTIONS
    
    views = context.user_data.get('temp_criteria_views', 0)
    criteria = {}
    if views > 0:
        criteria['min_views'] = views
    if likes > 0:
        criteria['min_likes'] = likes
    
    context.user_data['temp_criteria'] = criteria
    
    temp = context.user_data.get('temp_source')
    return await show_media_filters(update, context, temp)


async def show_media_filters(target, context, temp):
    """Показывает меню фильтров контента."""
    keyboard = [
        [InlineKeyboardButton("📷 Все (шортсы + обычные)", callback_data="media_all")],
        [InlineKeyboardButton("📱 Только шортсы", callback_data="media_shorts_only")],
        [InlineKeyboardButton("📺 Только обычные", callback_data="media_long_only")],
    ]
    
    text = f"✅ Критерии выбраны\n\nТеперь выберите тип контента для {temp['name']}:"
    
    if hasattr(target, 'edit_message_text'):
        await target.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await target.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    
    return AWAITING_MEDIA_FILTER


async def media_filter_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор медиа-фильтра."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data.replace("media_", "")
    context.user_data['temp_media_filter'] = choice
    
    # Для шортсов/обычных ограничение по длительности
    if choice in ("all", "long_only"):
        keyboard = [
            [InlineKeyboardButton("📏 До 1 минуты", callback_data="duration_60")],
            [InlineKeyboardButton("📏 До 3 минут", callback_data="duration_180")],
            [InlineKeyboardButton("📏 До 5 минут", callback_data="duration_300")],
            [InlineKeyboardButton("📏 До 10 минут", callback_data="duration_600")],
            [InlineKeyboardButton("📏 Без ограничений", callback_data="duration_0")],
        ]
        await query.edit_message_text(
            "🎬 <b>Максимальная длительность видео:</b>",
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="HTML"
        )
        return AWAITING_MEDIA_FILTER
    else:
        # Для shorts_only — без ограничений
        context.user_data['temp_max_video_duration'] = None
        return await ask_remove_text(query, context)


async def duration_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор длительности видео."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data.replace("duration_", "")
    duration = int(choice)
    context.user_data['temp_max_video_duration'] = duration if duration > 0 else None
    
    return await ask_remove_text(query, context)


async def ask_remove_text(target, context):
    """Спрашивает, удалять ли текст описания."""
    keyboard = [
        [InlineKeyboardButton("✅ Оставлять описание", callback_data="text_keep")],
        [InlineKeyboardButton("❌ Удалять описание", callback_data="text_remove")],
    ]
    
    text = (
        f"📝 <b>Оригинальное описание видео:</b>\n\n"
        f"Хотите оставлять или удалять описание из источника?\n"
        f"Если удалить — останется только заголовок, медиа и подпись."
    )
    
    if hasattr(target, 'edit_message_text'):
        await target.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    else:
        await target.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode="HTML")
    
    context.user_data['awaiting_text_choice'] = True
    return AWAITING_REMOVE_TEXT


async def remove_text_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обрабатывает выбор удаления текста."""
    query = update.callback_query
    await query.answer()
    
    choice = query.data.replace("text_", "")
    remove_text = (choice == "remove")
    
    temp = context.user_data.get('temp_source')
    criteria = context.user_data.get('temp_criteria', {})
    media_filter = context.user_data.get('temp_media_filter', 'all')
    max_video_duration = context.user_data.get('temp_max_video_duration')
    
    if not temp:
        await query.edit_message_text("❌ Ошибка: данные не найдены.")
        return ConversationHandler.END
    
    async with AsyncSessionLocal() as session:
        # Проверяем, существует ли уже такой источник
        if temp['source_type'] == 'channel':
            existing = await session.execute(
                select(SourceChannel).where(
                    SourceChannel.project_id == temp['project_id'],
                    SourceChannel.youtube_channel_id == temp.get('youtube_channel_id')
                )
            )
        elif temp['source_type'] == 'link':
            existing = await session.execute(
                select(SourceChannel).where(
                    SourceChannel.project_id == temp['project_id'],
                    SourceChannel.youtube_link_url == temp.get('youtube_link_url')
                )
            )
        else:  # search
            existing = await session.execute(
                select(SourceChannel).where(
                    SourceChannel.project_id == temp['project_id'],
                    SourceChannel.youtube_search_query == temp.get('youtube_search_query')
                )
            )
        
        if existing.scalar_one_or_none():
            await query.edit_message_text(f"⚠️ Такой источник уже добавлен в этот проект.")
            return ConversationHandler.END
        
        channel = SourceChannel(
            project_id=temp['project_id'],
            name=temp['name'],
            source_type=temp['source_type'],
            youtube_channel_id=temp.get('youtube_channel_id'),
            youtube_link_url=temp.get('youtube_link_url'),
            youtube_search_query=temp.get('youtube_search_query'),
            youtube_country=temp.get('youtube_country'),
            youtube_category=temp.get('youtube_category'),
            youtube_content_type=temp.get('youtube_content_type', 'all'),
            criteria=criteria,
            media_filter=media_filter,
            remove_original_text=remove_text,
            max_video_duration=max_video_duration,
            max_age_hours=24
        )
        session.add(channel)
        await session.commit()
        context.user_data['temp_source_id'] = channel.id
    
    # Формируем ответ
    filter_text = {"all": "все", "shorts_only": "только шортсы", "long_only": "только обычные"}.get(media_filter, "все")
    
    criteria_parts = []
    if criteria.get('min_views'):
        criteria_parts.append(f"👁 от {criteria['min_views']}")
    if criteria.get('min_likes'):
        criteria_parts.append(f"❤️ от {criteria['min_likes']}")
    criteria_display = ", ".join(criteria_parts) if criteria_parts else "без критериев"
    
    text_parts = [f"✅ Источник «{temp['name']}» добавлен!"]
    text_parts.append(f"📋 Критерии: {criteria_display}")
    text_parts.append(f"📷 Контент: {filter_text}")
    if max_video_duration:
        text_parts.append(f"🎬 Длительность: до {max_video_duration} сек")
    text_parts.append(f"📝 Описание: {'удаляется' if remove_text else 'оставляется'}")
    
    await query.edit_message_text("\n".join(text_parts))
    
    keyboard = [
        [InlineKeyboardButton("✅ Добавить ключевые слова", callback_data="add_keywords_yes")],
        [InlineKeyboardButton("⏭️ Пропустить", callback_data="add_keywords_skip")]
    ]
    
    await query.message.reply_text(
        f"🔍 <b>Ключевые слова для фильтрации</b>\n\n"
        f"Вы можете указать ключевые слова (через запятую).\n"
        f"Бот будет публиковать только видео, содержащие эти слова в заголовке или описании.\n\n"
        f"<i>Видео старше 24 часов автоматически игнорируются.</i>",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="HTML"
    )
    return AWAITING_KEYWORDS


async def add_link_source_direct(update: Update, context: ContextTypes.DEFAULT_TYPE, video: dict):
    """Добавляет источник-ссылку сразу в очередь (без критериев)."""
    temp = context.user_data.get('temp_source')
    
    async with AsyncSessionLocal() as session:
        channel = SourceChannel(
            project_id=temp['project_id'],
            name=temp['name'],
            source_type='link',
            youtube_link_url=temp['youtube_link_url'],
            criteria={},
            media_filter='all',
            remove_original_text=False,
            max_age_hours=24
        )
        session.add(channel)
        await session.commit()
        context.user_data['temp_source_id'] = channel.id
    
    # Добавляем в очередь
    poster = context.application.bot_data.get('poster')
    if poster:
        from datetime import datetime, timedelta
        post_data = {
            'url': video['url'],
            'title': video['title'],
            'description': video.get('description', ''),
            'views': video.get('views', 0),
            'likes': video.get('likes', 0),
            'thumbnail_url': video.get('thumbnail_url'),
            'source_name': temp['name']
        }
        await poster.add_to_queue(
            project_id=temp['project_id'],
            target_channel_id=await get_project_target(temp['project_id']),
            post_data=post_data,
            scheduled_time=datetime.utcnow() + timedelta(minutes=5)
        )
    
    await update.message.reply_text(
        f"✅ Источник-ссылка добавлен!\n"
        f"📹 {video['title'][:50]}...\n"
        f"⏰ Добавлен в очередь публикации."
    )
    
    # Очистка временных данных
    context.user_data.pop('temp_source', None)
    context.user_data.pop('temp_project_id', None)
    context.user_data.pop('temp_project_name', None)
    
    return ConversationHandler.END


async def add_keywords_yes_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "🔍 <b>Введите ключевые слова</b>\n\n"
        "Введите слова или фразы через запятую.\n"
        "Пример: <code>искусственный интеллект, нейросети, ChatGPT</code>\n\n"
        "Бот будет публиковать только видео, содержащие хотя бы одно из этих слов в заголовке или описании.\n\n"
        "Отправьте <code>-</code> чтобы пропустить.",
        parse_mode="HTML"
    )
    return AWAITING_KEYWORDS


async def add_keywords_skip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ Источник добавлен! Ключевые слова не указаны.")
    
    # Очистка временных данных
    context.user_data.pop('temp_source_id', None)
    context.user_data.pop('temp_source', None)
    context.user_data.pop('temp_project_id', None)
    context.user_data.pop('temp_project_name', None)
    context.user_data.pop('temp_criteria', None)
    context.user_data.pop('temp_media_filter', None)
    context.user_data.pop('temp_max_video_duration', None)
    
    return ConversationHandler.END


async def process_keywords_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    source_id = context.user_data.get('temp_source_id')
    
    if text == "-":
        keywords = None
        reply = "✅ Источник добавлен! Ключевые слова не указаны."
    else:
        keywords = text
        reply = f"✅ Источник добавлен!\n\n🔍 Ключевые слова: {keywords}"
    
    async with AsyncSessionLocal() as session:
        await session.execute(
            sql_update(SourceChannel)
            .where(SourceChannel.id == source_id)
            .values(include_keywords=keywords)
        )
        await session.commit()
    
    await update.message.reply_text(reply)
    
    context.user_data.pop('temp_source_id', None)
    context.user_data.pop('temp_source', None)
    context.user_data.pop('temp_project_id', None)
    context.user_data.pop('temp_project_name', None)
    context.user_data.pop('temp_criteria', None)
    context.user_data.pop('temp_media_filter', None)
    context.user_data.pop('temp_max_video_duration', None)
    
    return ConversationHandler.END


async def my_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает список источников."""
    telegram_id = update.effective_user.id
    project = await require_project(update, context)
    if not project:
        return
    
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(SourceChannel).where(SourceChannel.project_id == project.id).order_by(SourceChannel.added_at.desc())
        )
        sources = result.scalars().all()
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalar_one()
    
    if not sources:
        text = f"📭 В проекте «{project.name}» нет источников.\nДобавьте: /add_source"
        await update.message.reply_text(text)
        return
    
    text = f"📥 <b>Источники «{project.name}»</b> ({len(sources)} / {user.max_sources_per_project})\n\n"
    
    for src in sources:
        type_icon = {
            'channel': '📺',
            'link': '🔗',
            'search': '🔍'
        }.get(src.source_type, '📺')
        
        criteria_parts = []
        if src.criteria:
            if 'min_views' in src.criteria:
                criteria_parts.append(f"👁 ≥{src.criteria['min_views']}")
            if 'min_likes' in src.criteria:
                criteria_parts.append(f"❤️ ≥{src.criteria['min_likes']}")
        criteria_str = ", ".join(criteria_parts) if criteria_parts else "без критериев"
        
        text += f"{type_icon} <b>{src.name}</b> ({src.source_type})\n"
        text += f"   📊 {criteria_str}\n"
        text += f"   📷 {src.media_filter}\n"
        if src.max_video_duration:
            text += f"   🎬 до {src.max_video_duration}с\n"
        text += f"   📝 {'без описания' if src.remove_original_text else 'с описанием'}\n"
        if src.include_keywords:
            text += f"   🔍 Ключевые слова: {src.include_keywords}\n"
        if src.last_parsed:
            text += f"   🕐 {src.last_parsed.strftime('%d.%m.%Y %H:%M')}\n"
        text += "\n"
    
    await update.message.reply_text(text, parse_mode="HTML")


async def edit_source_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Редактирование источника."""
    query = update.callback_query
    await query.answer()
    
    source_id = int(query.data.replace("edit_source_", ""))
    context.user_data['edit_source_id'] = source_id
    # ... (остальная логика редактирования аналогична tg2tg)