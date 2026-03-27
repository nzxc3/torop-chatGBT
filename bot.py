#!/usr/bin/env python3
"""
TELEGRAM БОТ С OPENROUTER API И АДМИН-ПАНЕЛЬЮ
РАЗРАБОТЧИК: Тороп Никита
"""

import asyncio
import aiohttp
import json
import os
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage
from datetime import datetime

# ===== НАСТРОЙКИ =====
TOKEN = "8360813002:AAFe0ONoF76RswDIIQIKpCyL2G0vS3kpnBg"
OPENROUTER_KEY = "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"
ADMIN_USERNAME = "fuexu"
PASSWORD = "admin123"

# ===== ИНИЦИАЛИЗАЦИЯ =====
storage = MemoryStorage()
bot = Bot(token=TOKEN)
dp = Dispatcher(storage=storage)

authorized_users = {}
user_history = {}

# ===== ЗАГРУЗКА ВАЙТ-ЛИСТА =====
WHITELIST_FILE = "whitelist.json"

def load_whitelist():
    if os.path.exists(WHITELIST_FILE):
        with open(WHITELIST_FILE, 'r') as f:
            try:
                return json.load(f)  # <-- НЕ f.read(), а просто f!
            except json.JSONDecodeError:
                return []  # Если файл поврежден, возвращаем пустой список
    return []

def save_whitelist(whitelist):
    with open(WHITELIST_FILE, 'w') as f:
        json.dump(whitelist, f, indent=4)

whitelist = load_whitelist()

# ===== СОСТОЯНИЯ ДЛЯ FSM =====
class PasswordState(StatesGroup):
    waiting_for_password = State()

class AdminState(StatesGroup):
    waiting_for_add_username = State()
    waiting_for_remove_username = State()

# ===== КЛАВИАТУРЫ =====
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="💬 Задать вопрос"), KeyboardButton(text="ℹ️ Помощь")],
        [KeyboardButton(text="👨‍💻 О создателе"), KeyboardButton(text="🗑️ Очистить историю")]
    ],
    resize_keyboard=True
)

admin_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📋 Список вайт-листа"), KeyboardButton(text="➕ Добавить в вайт-лист")],
        [KeyboardButton(text="❌ Удалить из вайт-листа"), KeyboardButton(text="📊 Статистика")],
        [KeyboardButton(text="🔙 В главное меню")]
    ],
    resize_keyboard=True
)

# ===== ФУНКЦИЯ OPENROUTER API =====
async def ask_openrouter(prompt, history=None):
    try:
        messages = []
        if history:
            for msg in history[-10:]:
                messages.append(msg)
        messages.append({"role": "user", "content": prompt})
        
        async with aiohttp.ClientSession() as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                json={
                    "model": "openai/gpt-3.5-turbo",
                    "messages": messages,
                    "max_tokens": 1000,
                    "temperature": 0.7
                },
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json"
                },
                timeout=aiohttp.ClientTimeout(total=45)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["choices"][0]["message"]["content"]
                else:
                    return f"⚠️ Ошибка API (статус {resp.status})"
    except asyncio.TimeoutError:
        return "⚠️ Превышено время ожидания."
    except Exception as e:
        return f"⚠️ Ошибка: {str(e)}"

# ===== ПРОВЕРКА АДМИНА =====
def is_admin(username):
    return username == ADMIN_USERNAME

def is_authorized(user_id, username):
    if is_admin(username):
        return True
    if username in whitelist:
        return True
    return user_id in authorized_users

# ===== КОМАНДЫ =====
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if is_authorized(user_id, username):
        keyboard = admin_keyboard if is_admin(username) else main_keyboard
        await message.answer(
            "🤖 *Добро пожаловать!*\n\n✅ Вы уже авторизованы.",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
        return
    
    await message.answer(
        "🤖 *Добро пожаловать!*\n\n🔐 Введите /login для входа.",
        parse_mode="Markdown"
    )

@dp.message(Command("login"))
async def cmd_login(message: types.Message, state: FSMContext):
    username = message.from_user.username
    user_id = message.from_user.id
    
    if is_authorized(user_id, username):
        keyboard = admin_keyboard if is_admin(username) else main_keyboard
        await message.answer("✅ Вы уже авторизованы!", reply_markup=keyboard)
        return
    
    await state.set_state(PasswordState.waiting_for_password)
    await message.answer("🔐 *Введите пароль:*", parse_mode="Markdown")

@dp.message(PasswordState.waiting_for_password)
async def check_password(message: types.Message, state: FSMContext):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if message.text == PASSWORD:
        authorized_users[user_id] = {
            "authorized_at": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
            "username": username or message.from_user.first_name
        }
        if user_id not in user_history:
            user_history[user_id] = []
        
        await state.clear()
        keyboard = admin_keyboard if is_admin(username) else main_keyboard
        
        await message.answer(
            "✅ *Доступ разрешен!*",
            parse_mode="Markdown",
            reply_markup=keyboard
        )
    else:
        await message.answer("❌ *Неверный пароль!*", parse_mode="Markdown")

@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    username = message.from_user.username
    
    if not is_admin(username):
        await message.answer("⛔ *Нет доступа к админ-панели.*", parse_mode="Markdown")
        return
    
    await message.answer(
        "🛡️ *АДМИН-ПАНЕЛЬ*\n\n"
        "/admin add @username — добавить в вайт-лист\n"
        "/admin remove @username — удалить\n"
        "/admin list — показать список\n"
        "/admin stats — статистика",
        parse_mode="Markdown",
        reply_markup=admin_keyboard
    )

@dp.message(Command("admin", commands=["admin"]))
async def admin_commands(message: types.Message):
    username = message.from_user.username
    if not is_admin(username):
        return
    
    args = message.text.split()
    if len(args) == 1:
        await cmd_admin(message)
        return
    
    command = args[1].lower()
    
    if command == "add" and len(args) >= 3:
        target = args[2].replace("@", "")
        if target in whitelist:
            await message.answer(f"⚠️ @{target} уже в вайт-листе.")
            return
        whitelist.append(target)
        save_whitelist(whitelist)
        await message.answer(f"✅ @{target} добавлен в вайт-лист!")
    
    elif command == "remove" and len(args) >= 3:
        target = args[2].replace("@", "")
        if target not in whitelist:
            await message.answer(f"⚠️ @{target} не найден.")
            return
        whitelist.remove(target)
        save_whitelist(whitelist)
        await message.answer(f"✅ @{target} удален из вайт-листа!")
    
    elif command == "list":
        if not whitelist:
            await message.answer("📋 Вайт-лист пуст.")
        else:
            text = "📋 *Вайт-лист:*\n\n" + "\n".join([f"• @{u}" for u in whitelist])
            await message.answer(text, parse_mode="Markdown")
    
    elif command == "stats":
        await message.answer(
            f"📊 *Статистика*\n\n"
            f"👥 Вайт-лист: {len(whitelist)}\n"
            f"🔐 По паролю: {len(authorized_users)}\n"
            f"💬 Диалогов: {len([h for h in user_history.values() if h])}",
            parse_mode="Markdown"
        )
    
    elif command == "exit":
        await message.answer("🔙 Выход", reply_markup=main_keyboard)

# ===== АДМИН-КНОПКИ =====
@dp.message(lambda msg: msg.text == "📋 Список вайт-листа")
async def admin_list_btn(message: types.Message):
    if not is_admin(message.from_user.username):
        return
    if not whitelist:
        await message.answer("📋 Вайт-лист пуст.")
    else:
        text = "📋 *Вайт-лист:*\n\n" + "\n".join([f"• @{u}" for u in whitelist])
        await message.answer(text, parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "➕ Добавить в вайт-лист")
async def admin_add_btn(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.username):
        return
    await state.set_state(AdminState.waiting_for_add_username)
    await message.answer("✍️ Введите username:")

@dp.message(AdminState.waiting_for_add_username)
async def admin_add_user(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.username):
        await state.clear()
        return
    target = message.text.strip().replace("@", "")
    if target in whitelist:
        await message.answer(f"⚠️ @{target} уже в списке.")
    else:
        whitelist.append(target)
        save_whitelist(whitelist)
        await message.answer(f"✅ @{target} добавлен!")
    await state.clear()

@dp.message(lambda msg: msg.text == "❌ Удалить из вайт-листа")
async def admin_remove_btn(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.username):
        return
    await state.set_state(AdminState.waiting_for_remove_username)
    await message.answer("✍️ Введите username для удаления:")

@dp.message(AdminState.waiting_for_remove_username)
async def admin_remove_user(message: types.Message, state: FSMContext):
    if not is_admin(message.from_user.username):
        await state.clear()
        return
    target = message.text.strip().replace("@", "")
    if target not in whitelist:
        await message.answer(f"⚠️ @{target} не найден.")
    else:
        whitelist.remove(target)
        save_whitelist(whitelist)
        await message.answer(f"✅ @{target} удален!")
    await state.clear()

@dp.message(lambda msg: msg.text == "📊 Статистика")
async def admin_stats_btn(message: types.Message):
    if not is_admin(message.from_user.username):
        return
    await message.answer(
        f"📊 *Статистика*\n\n"
        f"👥 Вайт-лист: {len(whitelist)}\n"
        f"🔐 По паролю: {len(authorized_users)}",
        parse_mode="Markdown"
    )

@dp.message(lambda msg: msg.text == "🔙 В главное меню")
async def admin_back_btn(message: types.Message):
    if not is_admin(message.from_user.username):
        return
    await message.answer("🔙 Возврат", reply_markup=main_keyboard)

# ===== ОСТАЛЬНЫЕ КОМАНДЫ =====
@dp.message(Command("ask"))
async def cmd_ask(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if not is_authorized(user_id, username):
        await message.answer("🔐 Введите /login")
        return
    
    question = message.text.replace("/ask", "").strip()
    if not question:
        await message.answer("❓ /ask [вопрос]")
        return
    
    await bot.send_chat_action(message.chat.id, "typing")
    history = user_history.get(user_id, [])
    response = await ask_openrouter(question, history)
    
    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].append({"role": "user", "content": question})
    user_history[user_id].append({"role": "assistant", "content": response})
    if len(user_history[user_id]) > 20:
        user_history[user_id] = user_history[user_id][-20:]
    
    await message.answer(f"🤖 {response}")

@dp.message(Command("clear"))
async def cmd_clear(message: types.Message):
    user_id = message.from_user.id
    if user_id in user_history:
        user_history[user_id] = []
    await message.answer("🗑️ История очищена!")

@dp.message(Command("help"))
async def cmd_help(message: types.Message):
    await message.answer(
        "📚 *Команды*\n\n"
        "/login — вход по паролю\n"
        "/ask [вопрос] — вопрос ChatGPT\n"
        "/clear — очистить историю\n"
        "/info — о боте\n"
        "/help — справка",
        parse_mode="Markdown"
    )

@dp.message(Command("info"))
async def cmd_info(message: types.Message):
    await message.answer(
        "🤖 *OpenRouter ChatGPT Bot*\n"
        "👨‍💻 Создатель: Тороп Никита\n"
        "🔧 Версия: 3.0 (с админ-панелью)",
        parse_mode="Markdown"
    )

@dp.message(lambda msg: msg.text == "💬 Задать вопрос")
async def btn_ask(message: types.Message):
    await message.answer("✍️ Напишите вопрос или используйте /ask")

@dp.message(lambda msg: msg.text == "ℹ️ Помощь")
async def btn_help(message: types.Message):
    await cmd_help(message)

@dp.message(lambda msg: msg.text == "👨‍💻 О создателе")
async def btn_creator(message: types.Message):
    await message.answer("👨‍💻 *Тороп Никита*\nРазработчик Telegram ботов", parse_mode="Markdown")

@dp.message(lambda msg: msg.text == "🗑️ Очистить историю")
async def btn_clear(message: types.Message):
    await cmd_clear(message)

@dp.message()
async def handle_message(message: types.Message):
    user_id = message.from_user.id
    username = message.from_user.username
    
    if message.text.startswith("/"):
        return
    
    if message.text in ["💬 Задать вопрос", "ℹ️ Помощь", "👨‍💻 О создателе", "🗑️ Очистить историю",
                       "📋 Список вайт-листа", "➕ Добавить в вайт-лист", "❌ Удалить из вайт-листа",
                       "📊 Статистика", "🔙 В главное меню"]:
        return
    
    if not is_authorized(user_id, username):
        await message.answer("🔐 Введите /login")
        return
    
    await bot.send_chat_action(message.chat.id, "typing")
    history = user_history.get(user_id, [])
    response = await ask_openrouter(message.text, history)
    
    if user_id not in user_history:
        user_history[user_id] = []
    user_history[user_id].append({"role": "user", "content": message.text})
    user_history[user_id].append({"role": "assistant", "content": response})
    if len(user_history[user_id]) > 20:
        user_history[user_id] = user_history[user_id][-20:]
    
    await message.answer(f"🤖 {response}")

# ===== ЗАПУСК =====
async def main():
    print("=" * 50)
    print("🤖 БОТ ЗАПУЩЕН")
    print(f"👨‍💻 Админ: @{ADMIN_USERNAME}")
    print(f"🔐 Пароль: {PASSWORD}")
    print(f"📋 Вайт-лист: {len(whitelist)} пользователей")
    print("=" * 50)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())