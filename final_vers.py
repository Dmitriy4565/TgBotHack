import os
import re
from telethon import TelegramClient, events
from telethon.tl.types import ChannelParticipantsAdmins
from telethon.errors.rpcerrorlist import UserNotParticipantError
from telethon import Button

API_ID = '###'
API_HASH = '###'
BOT_TOKEN = '###'

client = TelegramClient('bot_session', API_ID, API_HASH).start(bot_token=BOT_TOKEN)

user_states = {}

async def update_participants_file(chat):
    """Обновление списка участников чата в файл."""
    try:
        participants = await client.get_participants(chat)

        current_participants = []
        for user in participants:
            short_name = user.username or f"{user.first_name or ''} {user.last_name or ''}".strip()
            current_participants.append(f"ID: {user.id}, Имя: {short_name}")

        filename = f"group_{chat.title}_{chat.id}_participants.txt"

        if not os.path.exists(filename):
            with open(filename, "w", encoding="utf-8") as file:
                for line in current_participants:
                    file.write(line + "\n")
            print(f"Создан файл участников для группы '{chat.title}'.")

        else:
            with open(filename, "w", encoding="utf-8") as file:
                for line in current_participants:
                    file.write(line + "\n")
            print(f"Файл участников для группы '{chat.title}' обновлен.")

    except Exception as e:
        print(f"Ошибка при обновлении файла для группы {chat.title}: {e}")

async def is_admin(chat, user_id):
    """Проверка, является ли пользователь администратором в чате."""
    try:
        permissions = await client.get_permissions(chat, user_id)
        return permissions.is_admin
    except Exception as e:
        print(f"Ошибка при проверке прав пользователя в группе {chat.title}: {e}")
        return False

async def get_group_ids_from_files():
    """Получаем ID групп из файлов участников."""
    group_ids = []
    for filename in os.listdir():
        if filename.startswith("group_") and filename.endswith("_participants.txt"):
            try:
                chat_id = int(filename.split("_")[-2])
                group_ids.append(chat_id)
            except ValueError:
                print(f"Ошибка при обработке файла: {filename} — ID чата не распознан.")
    return group_ids

async def get_admin_chats(user_id):
    """Получаем чаты, где пользователь является администратором."""
    group_ids = await get_group_ids_from_files()
    admin_chats = []
    for group_id in group_ids:
        try:
            chat = await client.get_entity(group_id)
            admins = await client.get_participants(chat, filter=ChannelParticipantsAdmins)
            if any(admin.id == user_id for admin in admins):
                admin_chats.append(chat)
                print(f"Вы администратор в чате: {chat.title} (ID: {chat.id})")
        except Exception as e:
            print(f"Ошибка при проверке чата с ID {group_id}: {e}")
    return admin_chats

@client.on(events.NewMessage(pattern='/start'))
async def start(event):
    if event.is_private:
        buttons = [
            [Button.inline("Удалить пользователя", b"remove")],
            [Button.inline("My Chats", b"my_chats")]
        ]
        await event.reply("Здравствуйте, выберите действие которое хотите сделать:", buttons=buttons)

@client.on(events.CallbackQuery(data=b"remove"))
async def remove_user_button(event):
    if event.is_private:
        await event.respond("Введите username пользователя, которого хотите удалить (@username).")
        user_states[event.sender_id] = "remove"

@client.on(events.CallbackQuery(data=b"my_chats"))
async def my_chats_button(event):
    if event.is_private:
        admin_chats = await get_admin_chats(event.sender_id)
        if not admin_chats:
            await event.respond("Вы не являетесь администратором ни в одной группе.")
            return

        chat_list = "\n".join([f"{chat.title} (ID: {chat.id})" for chat in admin_chats])
        await event.respond(f"Вы администратор в следующих группах:\n{chat_list}")

@client.on(events.NewMessage)
async def handle_username_input(event):
    if event.is_private:
        sender_id = event.sender_id
        if sender_id in user_states:
            action = user_states[sender_id]

            if event.raw_text.lower() == "my chats":
                admin_chats = await get_admin_chats(sender_id)

                if not admin_chats:
                    await event.respond("Вы не являетесь администратором ни в одной группе.")
                    del user_states[sender_id]
                    return

                for chat in admin_chats:
                    try:
                        participants = await client.get_participants(chat)
                        participant_list = "\n".join([f"{user.username}" for user in participants if user.username])
                        message = f"Группа: {chat.title}\nУчастники:\n{participant_list}"
                        await event.respond(message)
                    except Exception as e:
                        await event.respond(f"Не удалось получить участников для группы {chat.title}. Ошибка: {e}")

            else:
                username_to_input = event.raw_text.strip()

                if username_to_input.startswith('@'):
                    username_to_input = username_to_input[1:]

                admin_chats = await get_admin_chats(sender_id)
                if not admin_chats:
                    await event.respond("Вы не являетесь администратором ни в одной группе.")
                    del user_states[sender_id]
                    return
                found = False
                for filename in os.listdir():
                    if filename.startswith("group_") and filename.endswith("_participants.txt"):
                        with open(filename, "r", encoding="utf-8") as file:
                            lines = file.readlines()

                        user_to_remove = None
                        for line in lines:
                            if re.search(rf"\b{username_to_input.lower()}\b", line.lower()):
                                user_to_remove = line
                                break

                        if user_to_remove:
                            found = True
                            user_id = int(user_to_remove.split(",")[0].split(":")[1].strip())
                            chat_id = int(filename.split("_")[-2])

                            chat = next((chat for chat in admin_chats if chat.id == chat_id), None)
                            if chat:
                                try:
                                    if not await is_admin(chat, sender_id):
                                        await event.respond(f"Вы не являетесь администратором в группе {chat.title} и не можете удалять пользователей.")
                                        continue

                                    if await is_admin(chat, user_id):
                                        await event.respond(f"Пользователь @{username_to_input} является администратором в группе {chat.title} и не может быть удалён.")
                                        continue

                                    await client.kick_participant(chat.id, user_id)
                                    await event.respond(f"Пользователь @{username_to_input} был удалён из группы {chat.title}")

                                except Exception as e:
                                    await event.respond(f"Ошибка при удалении пользователя из группы {chat.title}: {e}")

                        if found:
                            with open(filename, "w", encoding="utf-8") as file:
                                for line in lines:
                                    if user_to_remove and user_to_remove not in line:
                                        file.write(line)

                if not found:
                    await event.respond(f"Пользователь с username @{username_to_input} не найден в группах.")

                del user_states[sender_id]

@client.on(events.ChatAction)
async def handle_group_changes(event):
    """Обработчик событий для изменений в группе (включая вступление участников)."""
    if event.is_private:
        return

    if event.user_id == (await client.get_me()).id:
        return

    chat = await event.get_chat()

    if event.user_joined or event.user_added:
        bot_user = await client.get_me()
        participants = await client.get_participants(chat)
        bot_in_group = any(user.id == bot_user.id for user in participants)

        if bot_in_group:
            await update_participants_file(chat)
print("Бот запущен и готов к работе...")

client.run_until_disconnected()
