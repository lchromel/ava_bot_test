
# Telegram Avatar Bot

Бот для Telegram, который накладывает стикеры на аватарку пользователя по выбранной категории:

- 🛌 Day Off
- 🏖 Vacation
- 💼 Business Trip (с выбором часового пояса)

---

## 🚀 Быстрый старт

### 1. Клонируй репозиторий

```bash
git clone https://github.com/lchromel/telegram-avatar-bot.git
cd telegram-avatar-bot
```

### 2. Установи зависимости

Рекомендуется использовать [Python 3.10+]

```bash
pip install -r requirements.txt
```

### 3. Добавь токен бота

Создай файл `.env` или добавь переменную окружения `TELEGRAM_BOT_TOKEN`:

```bash
export TELEGRAM_BOT_TOKEN=your_telegram_bot_token
```

Или вставь токен прямо в `bot.py` (не рекомендуется для продакшена):

```python
token = "your_telegram_bot_token"
```

### 4. Запусти бота

```bash
python bot.py
```

---

## 🖼 PNG оверлеи

Положи нужные оверлеи в папку `overlays/` с такими именами:

- `day_off.png`
- `vacation.png`
- `business_trip_utc.png`
- `business_trip_dubai.png`
- `business_trip_moscow.png`
- `business_trip_ny.png`

Формат: прозрачный PNG (размер автоматически подгоняется под фото пользователя).

---

## ☁️ Деплой (например, Railway)

1. Подключи репозиторий на [https://railway.app](https://railway.app)
2. Добавь переменную окружения `TELEGRAM_BOT_TOKEN`
3. Команда запуска: `python bot.py`

---

## 🛠 Зависимости

- [python-telegram-bot](https://github.com/python-telegram-bot/python-telegram-bot)
- [Pillow](https://pillow.readthedocs.io/en/stable/)

---

## 📸 Автор

Разработка: [lchromel](https://github.com/lchromel)
