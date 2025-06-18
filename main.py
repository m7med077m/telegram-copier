import asyncio
import logging
import time
import os
import re
from pyrogram import Client, filters
from pyrogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from config import API_ID, API_HASH, BOT_TOKEN, LOG_LEVEL, LOG_FORMAT
from session_handler import SessionHandler
from user_manager import UserManager
from message_handler import MessageHandler
from button_handler import ButtonHandler
from utils import validate_phone_number, parse_message_range

# Configure logging
logging.basicConfig(level=getattr(logging, LOG_LEVEL), format=LOG_FORMAT)
logger = logging.getLogger(__name__)

# Initialize components
session_handler = SessionHandler()
user_manager = UserManager()
message_handler = MessageHandler(session_handler, user_manager)
button_handler = ButtonHandler(session_handler, user_manager, message_handler)

# Create bot client
app = Client("copier_bot", api_id=API_ID, api_hash=API_HASH, bot_token=BOT_TOKEN)

def extract_message_id_from_link(link):
    """Extract the message ID from a Telegram message link."""
    match = re.search(r'/([0-9]+)$', link)
    if match:
        return int(match.group(1))
    return None

@app.on_message(filters.command("start"))
async def start_command(client: Client, message: Message):
    """Handle /start command and reset all copy/session parameters"""
    try:
        user_id = message.from_user.id
        logger.info(f"Start command from user {user_id}")
        
        # Initialize user in database
        user_manager.get_or_create_user(user_id)
        
        # Reset all copy/session parameters
        session_handler.update_user_session(user_id, {
            'source_channel': None,
            'source_title': None,
            'target_channel': None,
            'target_title': None,
            'start_msg_id': None,
            'end_msg_id': None,
            'state': 'main_menu'
        })
        
        # Show main menu
        from pyrogram.types import CallbackQuery
        fake_callback = type('CallbackQuery', (), {
            'from_user': message.from_user,
            'edit_message_text': message.reply,
            'answer': lambda: None
        })()
        
        await button_handler.show_main_menu(fake_callback)
        
    except Exception as e:
        logger.error(f"Error in start command: {e}")
        await message.reply("❌ An error occurred. Please try again.")

@app.on_message(filters.command("stop"))
async def stop_command(client: Client, message: Message):
    """Handle /stop command to cancel ongoing copy operations"""
    try:
        user_id = message.from_user.id
        session = session_handler.get_user_session(user_id)
        
        # Set cancellation flag
        session_handler.update_user_session(user_id, {'is_cancelled': True})
        await message.reply("🛑 Cancelling copy operation... Please wait for the current message to finish.")
        
    except Exception as e:
        logger.error(f"Error in stop command: {e}")
        await message.reply("❌ An error occurred while trying to stop the operation.")

# --- Button-based message range selection ---
async def show_range_selection_menu(callback_query):
    """Show buttons for range selection: Copy all, Set start, Set end"""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Copy all channel", callback_data="range_all")],
        [InlineKeyboardButton("🔢 Set start", callback_data="range_set_start")],
        [InlineKeyboardButton("🔢 Set end", callback_data="range_set_end")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
    ])
    await callback_query.edit_message_text(
        "Select message range to copy:",
        reply_markup=keyboard
    )

async def show_range_selection_menu_for_message(message):
    """Show range selection menu as a new message (for use in text_handler)."""
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📋 Copy all channel", callback_data="range_all")],
        [InlineKeyboardButton("🔢 Set start", callback_data="range_set_start")],
        [InlineKeyboardButton("🔢 Set end", callback_data="range_set_end")],
        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
    ])
    await message.reply(
        "Select message range to copy:",
        reply_markup=keyboard
    )

async def get_channel_message_id_range(client, channel_id):
    """Fetch the minimum and maximum message IDs in a channel."""
    min_id = None
    max_id = None
    # Get the latest message (max_id)
    async for message in client.get_chat_history(channel_id, limit=1):
        max_id = message.id
    # Get the oldest message (min_id) by iterating to the end
    async for message in client.get_chat_history(channel_id):
        min_id = message.id  # This will end up as the oldest
    return min_id, max_id

@app.on_callback_query()
async def callback_handler(client: Client, callback_query: CallbackQuery):
    """Handle all callback queries, including range selection and copy start."""
    data = callback_query.data
    user_id = callback_query.from_user.id
    session = session_handler.get_user_session(user_id)
    # --- Range selection logic ---
    if data == "set_range":
        await show_range_selection_menu(callback_query)
        return
    if data == "range_all":
        # Get the last message ID from the source channel
        source_id = session.get('source_channel')
        if not source_id:
            await callback_query.edit_message_text("❌ Please set the source channel first.")
            return
        # Get user client
        client = await session_handler.get_user_client(user_id)
        if not client:
            await callback_query.edit_message_text("❌ No active session found. Please create a session first.")
            return
        # Fetch the last message from the source channel
        try:
            last_message = await client.get_history(source_id, limit=1)
            if last_message:
                last_msg_id = last_message[0].id
            else:
                last_msg_id = 1
        except Exception as e:
            logger.error(f"Error fetching last message: {e}")
            await callback_query.edit_message_text(
                "We've set up everything for you! 😊\n\nJust send the link or ID of the last message in the source channel to finish setup. (The start message is already set to 1 for you.)")
            session_handler.update_user_session(user_id, {'state': 'awaiting_range_end_link', 'start_msg_id': 1})
            return
        session_handler.update_user_session(user_id, {
            'start_msg_id': 1,
            'end_msg_id': last_msg_id,
            'state': 'main_menu'
        })
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Start Copying", callback_data="start_copy")],
            [InlineKeyboardButton("🔄 Reset Copy Parameters", callback_data="reset_copy")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")],
        ])
        await callback_query.edit_message_text(
            f"Message range set to all channel!\nRange: 1 - {last_msg_id}",
            reply_markup=keyboard
        )
        return
    if data == "range_set_start":
        session_handler.update_user_session(user_id, {'state': 'awaiting_range_start_link'})
        await callback_query.edit_message_text(
            "Send the link of the <b>start message</b> (forward or copy link from Telegram):",
        )
        return
    if data == "range_set_end":
        session_handler.update_user_session(user_id, {'state': 'awaiting_range_end_link'})
        await callback_query.edit_message_text(
            "Send the link of the <b>end message</b> (forward or copy link from Telegram):",
        )
        return
    if data == "show_vip_upgrade":
        await button_handler.show_vip_upgrade(callback_query)
        return
    # --- Start copy logic ---
    if data == "start_copy":
        try:
            # Always use detailed monitor system
            source_id = session.get('source_channel')
            target_id = session.get('target_channel')
            start_id = session.get('start_msg_id')
            end_id = session.get('end_msg_id')
            if not (source_id and target_id and start_id and end_id):
                await callback_query.edit_message_text("❌ Please set source, target, and message range first.")
                return
            # Show initial status message and pass it to copy_messages for progress updates
            status_msg = await callback_query.message.reply("📥 Starting copy...")
            success, result = await message_handler.copy_messages(
                user_id, source_id, target_id, start_id, end_id, status_message=status_msg
            )
            if success:
                await status_msg.reply(f"✅ Copy completed!\n\n{result}")
            else:
                await status_msg.reply(f"❌ Copy failed!\n\n{result}")
        except Exception as e:
            logger.error(f"Error in start_copy logic: {e}")
            try:
                await callback_query.message.reply(f"❌ An error occurred: {str(e)}")
            except Exception:
                pass
        finally:
            try:
                await button_handler.show_main_menu(callback_query)
            except Exception as menu_error:
                logger.error(f"Error showing main menu: {menu_error}")
        return
    # Fallback to button_handler for other callbacks
    await button_handler.handle_callback(callback_query)

@app.on_message(filters.text & filters.private)
async def text_handler(client: Client, message: Message):
    try:
        user_id = message.from_user.id
        session = session_handler.get_user_session(user_id)
        
        # Reset cancellation flag at the start of any copy operation
        session_handler.update_user_session(user_id, {'is_cancelled': False})
        
        state = session.get('state', 'main_menu')
        text = message.text.strip()
        logger.info(f"Text message from user {user_id}, state: {state}, text: {text}")
        # Prevent handling /reset command here
        if text.startswith("/reset"):
            return
        # --- Admin input states ---
        if state == 'awaiting_free_limit':
            try:
                owner_id = message.from_user.id
                if not user_manager.is_owner(owner_id):
                    await message.reply("❌ You are not authorized to perform this action.")
                    return
                new_limit = int(text)
                assert new_limit > 0
                user_manager.save_free_limit(new_limit)
                # Reset message count for all free users
                from database import DatabaseManager
                db = DatabaseManager()
                users = db.cursor.execute('SELECT user_id, is_vip, is_owner FROM users').fetchall()
                reset_count = 0
                for row in users:
                    user_id, is_vip, is_owner = row
                    if not is_vip and not is_owner:
                        db.reset_message_count(user_id)
                        reset_count += 1
                await message.reply(f"✅ Free user daily message limit set to {new_limit}.\nAll free users' daily usage has been reset ({reset_count} users).")
                session_handler.update_user_session(user_id, {'state': 'main_menu'})
            except Exception:
                await message.reply("❌ Please send a valid positive integer for the new limit.")
            return
        if state == 'awaiting_broadcast':
            try:
                owner_id = message.from_user.id
                if not user_manager.is_owner(owner_id):
                    await message.reply("❌ You are not authorized to perform this action.")
                    return
                from database import DatabaseManager
                db = DatabaseManager()
                users = db.cursor.execute('SELECT user_id FROM users').fetchall()
                count = 0
                for row in users:
                    try:
                        logger.info(f"Broadcasting to user {row[0]}")
                        await app.send_message(row[0], text)
                        count += 1
                    except Exception as e:
                        logger.warning(f"Failed to send to {row[0]}: {e}")
                        continue
                await message.reply(f"✅ Broadcast sent to {count} users.")
                session_handler.update_user_session(user_id, {'state': 'main_menu'})
            except Exception as e:
                logger.error(f"Error broadcasting: {e}")
                await message.reply("❌ An error occurred. Please try again.")
            return
        # --- Existing state handlers ---
        if state == 'awaiting_range_start':
            try:
                start_id = int(text)
                if start_id < 1:
                    raise ValueError
                session_handler.update_user_session(user_id, {'start_msg_id': start_id, 'state': 'main_menu'})
                await message.reply(f"Start message ID set to {start_id}.")
                from pyrogram.types import CallbackQuery
                fake_callback = type('CallbackQuery', (), {
                    'from_user': message.from_user,
                    'edit_message_text': message.reply,
                    'answer': lambda: None
                })()
                await button_handler.show_main_menu(fake_callback)
            except Exception:
                await message.reply("Invalid start message ID. Please send a positive integer.")
            return
        if state == 'awaiting_range_end':
            try:
                end_id = int(text)
                if end_id < 1:
                    raise ValueError
                session_handler.update_user_session(user_id, {'end_msg_id': end_id, 'state': 'main_menu'})
                await message.reply(f"End message ID set to {end_id}.")
                from pyrogram.types import CallbackQuery
                fake_callback = type('CallbackQuery', (), {
                    'from_user': message.from_user,
                    'edit_message_text': message.reply,
                    'answer': lambda: None
                })()
                await button_handler.show_main_menu(fake_callback)
            except Exception:
                await message.reply("Invalid end message ID. Please send a positive integer.")
            return
        if state == 'awaiting_range_start_link':
            msg_id = extract_message_id_from_link(text)
            if msg_id:
                session_handler.update_user_session(user_id, {'start_msg_id': msg_id, 'state': 'main_menu'})
                await message.reply(f"Start message ID set to {msg_id}.")
                from pyrogram.types import CallbackQuery
                fake_callback = type('CallbackQuery', (), {
                    'from_user': message.from_user,
                    'edit_message_text': message.reply,
                    'answer': lambda: None
                })()
                await button_handler.show_main_menu(fake_callback)
            else:
                await message.reply("Invalid link. Please send a valid Telegram message link.")
            return
        if state == 'awaiting_range_end_link':
            msg_id = extract_message_id_from_link(text)
            if msg_id:
                session_handler.update_user_session(user_id, {'end_msg_id': msg_id, 'state': 'main_menu'})
                await message.reply(f"End message ID set to {msg_id}.")
                from pyrogram.types import CallbackQuery
                fake_callback = type('CallbackQuery', (), {
                    'from_user': message.from_user,
                    'edit_message_text': message.reply,
                    'answer': lambda: None
                })()
                await button_handler.show_main_menu(fake_callback)
            else:
                await message.reply("Invalid link. Please send a valid Telegram message link.")
            return
        if state == 'awaiting_phone':
            await handle_phone_input(message, text)
        elif state == 'awaiting_code':
            await handle_code_input(message, text)
        elif state == 'awaiting_password':
            await handle_password_input(message, text)
        elif state == 'awaiting_session_string':
            await handle_session_string_input(message, text)
        elif state == 'awaiting_source_channel':
            await handle_source_channel_input(message, text)
        elif state == 'awaiting_target_channel':
            await handle_target_channel_input(message, text)
        elif state == 'awaiting_message_range':
            await handle_message_range_input(message, text)
        elif state == 'awaiting_vip_promotion':
            await handle_vip_promotion_input(message, text)
        elif state == 'awaiting_vip_demotion':
            await handle_vip_demotion_input(message, text)
        elif state == 'awaiting_personal_copy_link':
            try:
                # Check free user message limit before starting
                stats = user_manager.get_user_stats(user_id)
                if not (stats['is_owner'] or stats['is_vip']) and stats['message_count'] >= stats['message_limit']:
                    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("⭐ Upgrade to VIP", callback_data="show_vip_upgrade")],
                        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
                    ])
                    await message.reply(
                        "❌ You have reached your daily free message limit. Upgrade to VIP for unlimited copying!",
                        reply_markup=keyboard
                    )
                    session_handler.update_user_session(user_id, {'state': 'main_menu'})
                    return
                import re
                from pyrogram.errors import PeerIdInvalid
                text = text.strip()
                link_pattern_private = r"https?://t\.me/c/(\d+)/(\d+)(?:-(\d+))?"
                link_pattern_public = r"https?://t\.me/([\w_]+)/([0-9]+)(?:-([0-9]+))?"
                match = re.match(link_pattern_private, text)
                is_public = False
                if not match:
                    match = re.match(link_pattern_public, text)
                    is_public = True if match else False
                if not match:
                    await message.reply(f"❌ Invalid link format.\nPlease send a valid Telegram message link or range.\nExample:\n- https://t.me/c/2434759780/6\n- https://t.me/channelname/6\n- https://t.me/c/2434759780/6-10\n- https://t.me/channelname/6-10")
                    return
                if is_public:
                    channel = match.group(1)
                    start_id = int(match.group(2))
                    end_id = int(match.group(3)) if match.group(3) else start_id
                else:
                    channel = int('-100' + match.group(1))
                    start_id = int(match.group(2))
                    end_id = int(match.group(3)) if match.group(3) else start_id
                user_client = await session_handler.get_user_client(user_id)
                if not user_client:
                    await message.reply("❌ No active session found. Please create a session first.")
                    return
                # Try to cache all peers by calling get_dialogs
                try:
                    async for dialog in user_client.get_dialogs():
                        pass
                    logger.info(f"Loaded dialogs for user {user_id}")
                except Exception as e:
                    logger.warning(f"Could not load dialogs: {e}")
                copied = 0
                failed = 0
                total = end_id - start_id + 1
                status_msg = await message.reply(f"📝 Starting copy...\nTotal: {total} messages")
                
                # Create a temporary directory for large files
                temp_dir = "temp_downloads"
                if not os.path.exists(temp_dir):
                    os.makedirs(temp_dir)
                
                # Maximum file size for in-memory handling (100MB)
                MAX_MEMORY_SIZE = 100 * 1024 * 1024  # 100MB in bytes
                
                for idx, msg_id in enumerate(range(start_id, end_id + 1), 1):
                    # Check if operation was cancelled
                    session = session_handler.get_user_session(user_id)
                    if session.get('is_cancelled'):
                        await status_msg.edit_text("🛑 Copy operation cancelled by user.")
                        break
                    
                    msg = None
                    try:
                        # Try get_chat with both numeric and username if possible
                        try:
                            await user_client.get_chat(channel)
                        except Exception as e:
                            logger.warning(f"get_chat failed for {channel}: {e}")
                        try:
                            msg = await user_client.get_messages(channel, msg_id)
                        except PeerIdInvalid:
                            await status_msg.edit_text(
                                "❌ Telegram API error: Peer ID invalid.\n\n" 
                                "Your account is a member, but Telegram sometimes restricts access by link if the peer is not cached.\n" 
                                "We tried to load all dialogs and resolve the peer, but Telegram still blocks access.\n\n" 
                                "If this works in another bot, please share details for further debugging.")
                            failed += 1
                            continue
                    except Exception as e:
                        failed += 1
                        await status_msg.edit_text(f"Failed to copy message {msg_id}: {e}\nProgress: {idx}/{total}")
                        continue
                    if not msg:
                        await status_msg.edit_text(f"Message {msg_id} not found or inaccessible.\nProgress: {idx}/{total}")
                        failed += 1
                        continue
                    details = [
                        f"📝 Processing message {msg_id} ({idx}/{total})...",
                        f"📅 Date: {msg.date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(msg, 'date') else ''}"
                    ]
                    if msg.media:
                        try:
                            # Get file size if available
                            file_size = 0
                            if hasattr(msg, 'video') and msg.video:
                                file_size = msg.video.file_size
                            elif hasattr(msg, 'document') and msg.document:
                                file_size = msg.document.file_size
                            elif hasattr(msg, 'photo') and msg.photo:
                                file_size = msg.photo.file_size
                            elif hasattr(msg, 'audio') and msg.audio:
                                file_size = msg.audio.file_size
                            
                            # Choose download method based on file size
                            if file_size > MAX_MEMORY_SIZE:
                                # For large files, use temporary file
                                temp_file = os.path.join(temp_dir, f"temp_{msg_id}_{int(time.time())}")
                                file = await user_client.download_media(msg, file_name=temp_file)
                                if file:
                                    try:
                                        await client.send_document(user_id, file, caption=msg.caption if msg.caption else None)
                                        # Clean up the temporary file immediately after sending
                                        try:
                                            os.remove(file)
                                            logger.info(f"Successfully deleted temporary file: {file}")
                                        except Exception as e:
                                            logger.warning(f"Error deleting temporary file {file}: {e}")
                                    except Exception as e:
                                        logger.error(f"Error sending file: {e}")
                                        failed += 1
                                        # Try to clean up the file if it exists
                                        try:
                                            if os.path.exists(file):
                                                os.remove(file)
                                        except Exception as cleanup_error:
                                            logger.warning(f"Error cleaning up file after error: {cleanup_error}")
                            else:
                                # For smaller files, use in-memory download
                                file = await user_client.download_media(msg, in_memory=True)
                                if file:
                                    await client.send_document(user_id, file, caption=msg.caption if msg.caption else None)
                                else:
                                    failed += 1
                                    continue
                            
                            # Add file details to status
                            details.append(f"📎 Type: {msg.media.value if hasattr(msg.media, 'value') else str(msg.media)}")
                            if hasattr(msg, 'video') and msg.video:
                                details.append(f"🎥 Video: {msg.video.file_size / (1024*1024):.1f}MB")
                                details.append(f"⏱️ Duration: {msg.video.duration}s")
                                details.append(f"📐 Resolution: {msg.video.width}x{msg.video.height}")
                            elif hasattr(msg, 'document') and msg.document:
                                details.append(f"📄 Document: {msg.document.file_name}")
                                details.append(f"📦 Size: {msg.document.file_size / (1024*1024):.1f}MB")
                            elif hasattr(msg, 'photo') and msg.photo:
                                details.append(f"🖼️ Photo: {msg.photo.file_size / (1024*1024):.1f}MB")
                            elif hasattr(msg, 'audio') and msg.audio:
                                details.append(f"🎵 Audio: {msg.audio.file_size / (1024*1024):.1f}MB")
                                details.append(f"⏱️ Duration: {msg.audio.duration}s")
                            if msg.caption:
                                caption_preview = msg.caption[:50] + "..." if len(msg.caption) > 50 else msg.caption
                                details.append(f"📝 Caption: {caption_preview}")
                            copied += 1
                        except Exception as e:
                            logger.error(f"Error processing media message {msg_id}: {e}")
                            failed += 1
                    elif msg.text or msg.caption:
                        await client.send_message(user_id, msg.text or msg.caption)
                        details.append("📝 Text message")
                        copied += 1
                    else:
                        await status_msg.edit_text(f"Message {msg_id} is of an unsupported type and was skipped.\nProgress: {idx}/{total}")
                        failed += 1
                        continue
                    await status_msg.edit_text("\n".join(details) + f"\n✓ Success: {copied}\n❌ Failed: {failed}")
                
                # Final cleanup of any remaining files
                try:
                    for file in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, file)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                                logger.info(f"Successfully deleted remaining file: {file_path}")
                        except Exception as e:
                            logger.warning(f"Error removing file {file_path}: {e}")
                    
                    # Try to remove the temp directory if it's empty
                    try:
                        os.rmdir(temp_dir)
                        logger.info(f"Successfully removed temporary directory: {temp_dir}")
                    except Exception as e:
                        logger.warning(f"Error removing temporary directory {temp_dir}: {e}")
                except Exception as e:
                    logger.error(f"Error during final cleanup: {e}")
                
                await status_msg.edit_text(f"✅ Done! {copied} messages copied, {failed} failed.")
                stats = user_manager.get_user_stats(user_id)
                if not (stats['is_owner'] or stats['is_vip']):
                    user_manager.increment_message_count(user_id, copied)
                session_handler.update_user_session(user_id, {'state': 'main_menu'})
            except Exception as e:
                logger.error(f"Error in personal copy handler: {e}")
                await message.reply("Something went wrong. Please try again or check your link.")
            return
        else:
            await message.reply("Please use the menu buttons to navigate.", 
                              reply_markup=await get_main_menu_keyboard(user_id))
    except Exception as e:
        logger.error(f"Error handling text message: {e}")
        await message.reply("❌ An error occurred. Please try again.")

async def handle_source_channel_input(message: Message, text: str):
    """Set source channel robustly: use get_dialogs, try get_chat with both ID and username, log results, and use best available info."""
    try:
        user_id = message.from_user.id
        client = await session_handler.get_user_client(user_id)
        if not client:
            await message.reply("❌ No active session. Please create a session first.")
            return
        import re
        text = text.strip()
        link_pattern_private = r"https?://t\.me/c/(\d+)/(\d+)"
        link_pattern_public = r"https?://t\.me/([\w_]+)/([0-9]+)"
        match_private = re.match(link_pattern_private, text)
        match_public = re.match(link_pattern_public, text)
        channel_id = None
        channel_username = None
        msg_id = None

        if match_private:
            # For private channels, use the ID directly
            channel_id = int('-100' + match_private.group(1))
            msg_id = int(match_private.group(2))
            try:
                # Try to get the message directly using the channel ID
                msg = await client.get_messages(channel_id, msg_id)
                if msg and msg.chat:
                    session_handler.update_user_session(user_id, {
                        'source_channel': str(msg.chat.id),
                        'source_title': msg.chat.title,
                        'state': 'main_menu'
                    })
                    await message.reply(
                        f"✅ Source channel set successfully!\n\n"
                        f"Channel: {msg.chat.title}\nID: `{msg.chat.id}`",
                        reply_markup=await get_main_menu_keyboard(user_id)
                    )
                    return
            except Exception as e:
                logger.warning(f"Could not fetch message from private channel: {e}")
                # Continue with other methods if direct message fetch fails
        elif match_public:
            channel_username = match_public.group(1)
            msg_id = int(match_public.group(2))

        # Step 1: Load all dialogs
        try:
            dialogs = []
            async for dialog in client.get_dialogs():
                dialogs.append(dialog)
            logger.info(f"Loaded {len(dialogs)} dialogs for user {user_id}")
        except Exception as e:
            logger.warning(f"Could not load dialogs: {e}")

        # Step 2: Try get_chat with both ID and username
        chat_obj = None
        chat_error = None
        if channel_id:
            try:
                chat_obj = await client.get_chat(channel_id)
                logger.info(f"get_chat with ID {channel_id} succeeded: {chat_obj.title if chat_obj else 'No title'}")
            except Exception as e:
                logger.warning(f"get_chat with ID {channel_id} failed: {e}")
                chat_error = e
        if not chat_obj and channel_username:
            try:
                chat_obj = await client.get_chat(channel_username)
                logger.info(f"get_chat with username {channel_username} succeeded: {chat_obj.title if chat_obj else 'No title'}")
            except Exception as e:
                logger.warning(f"get_chat with username {channel_username} failed: {e}")
                chat_error = e

        # Step 3: Try to fetch the message if possible
        if chat_obj and msg_id:
            try:
                msg = await client.get_messages(chat_obj.id, msg_id)
                chat_obj = msg.chat  # Use chat from message for accuracy
                logger.info(f"Fetched message {msg_id} from chat {chat_obj.id}")
            except Exception as e:
                logger.warning(f"Could not fetch message {msg_id} from chat {chat_obj.id}: {e}")

        # Step 4: Set the source channel using best available info
        if chat_obj:
            session_handler.update_user_session(user_id, {
                'source_channel': str(chat_obj.id),
                'source_title': chat_obj.title,
                'state': 'main_menu'
            })
            await message.reply(
                f"✅ Source channel set successfully!\n\n"
                f"Channel: {chat_obj.title}\nID: `{chat_obj.id}`",
                reply_markup=await get_main_menu_keyboard(user_id)
            )
            return

        # If all else fails, but we have a channel_id, set it and warn
        if channel_id:
            session_handler.update_user_session(user_id, {
                'source_channel': str(channel_id),
                'source_title': f"Channel ID {channel_id}",
                'state': 'main_menu'
            })
            await message.reply(
                f"⚠️ Channel set by ID from link, but your session could not access the chat or message.\n"
                f"You may need to join the channel or provide an invite link for full access.\n\n"
                f"Channel ID: <code>{channel_id}</code>",
                parse_mode="html",
                reply_markup=await get_main_menu_keyboard(user_id)
            )
            return

        # fallback to old logic for username, invite, or ID
        cleaned, input_type = message_handler.clean_channel_input(text)
        result_msg = (
            "Accepted formats:\n"
            "• Channel username: @channelname\n"
            "• Channel link: https://t.me/channelname\n"
            "• Channel ID: -1001234567890\n"
            "• Invitation link: https://t.me/+AbCdEfGhIj\n"
            "• Message link: https://t.me/c/123456789/1 or https://t.me/channelname/1\n"
        )
        chat = None
        error = None
        # Try invite link
        if input_type == 'invite':
            try:
                success, channel_id, result = await message_handler.join_channel_by_invite(client, cleaned)
                if success:
                    chat = {'id': channel_id, 'title': result}
                else:
                    error = result
            except Exception as e:
                error = str(e)
        # Try username
        if not chat and (input_type == 'username' or text.startswith('@')):
            try:
                chat_obj = await client.get_chat(f"@{cleaned}")
                chat = {'id': str(chat_obj.id), 'title': chat_obj.title}
            except Exception as e:
                error = str(e)
        # Try ID
        if not chat:
            try:
                chat_obj = await client.get_chat(cleaned)
                chat = {'id': str(chat_obj.id), 'title': chat_obj.title}
            except Exception as e:
                error = str(e)
        if chat:
            session_handler.update_user_session(user_id, {
                'source_channel': chat['id'],
                'source_title': chat['title'],
                'state': 'main_menu'
            })
            await message.reply(
                f"✅ Source channel set successfully!\n\n"
                f"Channel: {chat['title']}\nID: `{chat['id']}`",
                reply_markup=await get_main_menu_keyboard(user_id)
            )
        else:
            msg = f"❌ Failed to set source channel.\nReason: {error or 'Unknown error.'}\n" + result_msg
            if input_type != 'invite':
                msg += "\nIf this is a private channel, please use an invitation link or a message link from the channel."
            await message.reply(msg)
    except Exception as e:
        logger.error(f"Error handling source channel input: {e}")
        await message.reply("❌ An error occurred while setting the source channel.")

async def handle_target_channel_input(message: Message, text: str):
    """Restore previous working logic for target channel input."""
    try:
        user_id = message.from_user.id
        client = await session_handler.get_user_client(user_id)
        if not client:
            await message.reply("❌ No active session. Please create a session first.")
            return
        cleaned, input_type = message_handler.clean_channel_input(text)
        result_msg = (
            "Accepted formats:\n"
            "• Channel username: @channelname\n"
            "• Channel link: https://t.me/channelname\n"
            "• Channel ID: -1001234567890\n"
            "• Invitation link: https://t.me/+AbCdEfGhIj\n"
        )
        chat = None
        error = None
        # Try invite link first
        if input_type == 'invite':
            try:
                success, channel_id, result = await message_handler.join_channel_by_invite(client, cleaned)
                if success:
                    chat = {'id': channel_id, 'title': result}
                else:
                    error = result
            except Exception as e:
                error = str(e)
        # Try by username or ID using validate_channel_access (previous working logic)
        if not chat and (input_type == 'username' or input_type == 'id'):
            try:
                success, channel_id, result = await message_handler.validate_channel_access(client, cleaned)
                if success:
                    chat = {'id': channel_id, 'title': result}
                else:
                    error = result
            except Exception as e:
                error = str(e)
        if chat:
            try:
                member = await client.get_chat_member(chat['id'], "me")
                if not hasattr(member, 'privileges') or not member.privileges:
                    await message.reply(
                        f"⚠️ <b>Warning:</b> You may not have admin rights in this channel.\nMake sure you can post messages in the target channel.",
                        parse_mode="HTML"
                    )
            except:
                pass
            session_handler.update_user_session(user_id, {
                'target_channel': chat['id'],
                'target_title': chat['title'],
                'state': 'main_menu'
            })
            await message.reply(
                f"✅ Target channel set successfully!\n\n"
                f"Channel: {chat['title']}\nID: `{chat['id']}`",
                reply_markup=await get_main_menu_keyboard(user_id)
            )
        else:
            msg = f"❌ Failed to set target channel.\nReason: {error or 'Unknown error.'}\n" + result_msg
            if input_type != 'invite':
                msg += "\nIf this is a private channel, please use an invitation link."
            await message.reply(msg)
    except Exception as e:
        logger.error(f"Error handling target channel input: {e}")
        await message.reply("❌ An error occurred while setting the target channel.")

async def handle_phone_input(message: Message, phone: str):
    """Handle phone number input"""
    try:
        user_id = message.from_user.id
        
        # Validate phone number
        if not validate_phone_number(phone):
            await message.reply("❌ Invalid phone number format. Please use international format (e.g., +1234567890).")
            return
        
        # Start phone verification
        success, result = await session_handler.start_phone_verification(user_id, phone)
        
        if success:
            await message.reply(result)
            await message.reply("Please send the verification code you received on Telegram.")
        else:
            await message.reply(result)
            
    except Exception as e:
        logger.error(f"Error handling phone input: {e}")
        await message.reply("❌ An error occurred. Please try again.")

async def handle_code_input(message: Message, code: str):
    """Handle verification code input"""
    try:
        user_id = message.from_user.id
        
        # Verify code
        success, result = await session_handler.verify_code(user_id, code)
        
        if success:
            await message.reply(result, reply_markup=await get_main_menu_keyboard(user_id))
        else:
            await message.reply(result)
            
    except Exception as e:
        logger.error(f"Error handling code input: {e}")
        await message.reply("❌ An error occurred. Please try again.")

async def handle_password_input(message: Message, password: str):
    """Handle 2FA password input"""
    try:
        user_id = message.from_user.id
        
        # Verify password
        success, result = await session_handler.verify_password(user_id, password)
        
        if success:
            await message.reply(result, reply_markup=await get_main_menu_keyboard(user_id))
        else:
            await message.reply("❌ Invalid password. Please try again.")
            
    except Exception as e:
        logger.error(f"Error handling password input: {e}")
        await message.reply("❌ An error occurred. Please try again.")

async def handle_session_string_input(message: Message, session_string: str):
    """Handle session string input"""
    try:
        user_id = message.from_user.id
        
        # Create user client from session string
        client = await session_handler.create_user_client(user_id, session_string)
        
        if client:
            # Save session string
            session_handler.update_user_session(user_id, {
                'session_string': session_string,
                'state': 'main_menu'
            })
            
            await message.reply(
                "✅ Session created successfully!",
                reply_markup=await get_main_menu_keyboard(user_id)
            )
        else:
            await message.reply("❌ Failed to create session. Please try again.")
            
    except Exception as e:
        logger.error(f"Error handling session string input: {e}")
        await message.reply("❌ An error occurred. Please try again.")

async def handle_message_range_input(message: Message, range_text: str):
    """Handle message range input with buttons and reset option. Fixes parse mode and ensures feedback."""
    user_id = message.from_user.id
    try:
        # Parse message range
        ok, start_id, end_id, msg = parse_message_range(range_text)
        if not ok or start_id is None or end_id is None:
            await message.reply(f"❌ Invalid message range format. {msg}\nPlease use: <b>start_id-end_id</b> (e.g., 1-100)")
            return
        if start_id < 1 or end_id < 1:
            await message.reply("❌ Message IDs must be positive integers.")
            return
        if start_id > end_id:
            await message.reply("❌ Start ID cannot be greater than End ID.")
            return
        if end_id - start_id > 1000:
            await message.reply("⚠️ Range too large. Please select a range of 1000 messages or fewer.")
            return
        # Update session with message range
        session_handler.update_user_session(user_id, {
            'start_msg_id': start_id,
            'end_msg_id': end_id,
            'state': 'main_menu'
        })
        # Add buttons for copying and resetting
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🚀 Start Copying", callback_data="start_copy")],
            [InlineKeyboardButton("🔄 Reset Copy Parameters", callback_data="reset_copy")],
            [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
        ])
        await message.reply(
            f"✅ <b>Message range set successfully!</b>\n\n"
            f"<b>Range:</b> {start_id} - {end_id}",
            parse_mode="html",
            reply_markup=keyboard
        )
    except Exception as e:
        logger.error(f"Error handling message range input: {e}")
        try:
            await message.reply(f"❌ An error occurred: {e}")
        except Exception:
            pass

async def handle_vip_promotion_input(message: Message, user_id_text: str):
    try:
        owner_id = message.from_user.id
        if not user_manager.is_owner(owner_id):
            await message.reply("❌ You are not authorized to perform this action.")
            return
        try:
            user_id = int(user_id_text)
        except ValueError:
            await message.reply("❌ Invalid user ID format. Please provide a valid integer.")
            return
        success = user_manager.promote_to_vip(user_id)
        if success:
            await message.reply(f"✅ User {user_id} promoted to VIP successfully!", reply_markup=await get_main_menu_keyboard(owner_id))
            # Notify the user
            try:
                await app.send_message(
                    user_id,
                    "🎉 <b>Congratulations!</b> You are now a <b>VIP</b> user!\n\n"
                    "As a VIP, you enjoy:\n"
                    "• <b>Unlimited message copying</b>\n"
                    "• <b>Faster copy speeds</b>\n"
                    "• <b>Priority support</b>\n"
                    "• <b>No ads or restrictions</b>\n\n"
                    "Thank you for supporting our project!\n\n"
                    "<b>Enjoy all premium features!</b>",
                    reply_markup=await get_main_menu_keyboard(user_id),
                    parse_mode="html"
                )
            except Exception:
                pass
        else:
            await message.reply(f"❌ Failed to promote user {user_id} to VIP.")
    except Exception as e:
        logger.error(f"Error handling VIP promotion input: {e}")
        await message.reply("❌ An error occurred. Please try again.")

async def handle_vip_demotion_input(message: Message, user_id_text: str):
    try:
        owner_id = message.from_user.id
        if not user_manager.is_owner(owner_id):
            await message.reply("❌ You are not authorized to perform this action.")
            return
        try:
            user_id = int(user_id_text)
        except ValueError:
            await message.reply("❌ Invalid user ID format. Please provide a valid integer.")
            return
        success = user_manager.demote_from_vip(user_id)
        if success:
            await message.reply(f"✅ User {user_id} demoted from VIP successfully!", reply_markup=await get_main_menu_keyboard(owner_id))
            # Notify the user
            try:
                await app.send_message(
                    user_id,
                    "⚠️ <b>Your VIP status has been removed.</b> You are now a <b>Free User</b>.\n\n"
                    "As a free user, you can:\n"
                    "• Copy up to your daily message limit\n"
                    "• Access basic features\n\n"
                    "<b>Upgrade to VIP</b> to enjoy unlimited copying, faster speeds, priority support, and more!\n\n"
                    "Click the button below to subscribe and unlock all VIP benefits.",
                    reply_markup=await get_main_menu_keyboard(user_id),
                    parse_mode="html"
                )
            except Exception:
                pass
        else:
            await message.reply(f"❌ Failed to demote user {user_id} from VIP.")
    except Exception as e:
        logger.error(f"Error handling VIP demotion input: {e}")
        await message.reply("❌ An error occurred. Please try again.")

# --- Admin text input handlers ---
async def handle_free_limit_input(message: Message, limit_text: str):
    try:
        owner_id = message.from_user.id
        if not user_manager.is_owner(owner_id):
            await message.reply("❌ You are not authorized to perform this action.")
            return
        try:
            new_limit = int(limit_text)
            assert new_limit > 0
        except Exception:
            await message.reply("❌ Please send a valid positive integer for the new limit.")
            return
        user_manager.save_free_limit(new_limit)
        # Reset message count for all free users
        from database import DatabaseManager
        db = DatabaseManager()
        users = db.cursor.execute('SELECT user_id, is_vip, is_owner FROM users').fetchall()
        reset_count = 0
        for row in users:
            user_id, is_vip, is_owner = row
            if not is_vip and not is_owner:
                db.reset_message_count(user_id)
                reset_count += 1
        await message.reply(f"✅ Free user daily message limit set to {new_limit}.\nAll free users' daily usage has been reset ({reset_count} users).")
    except Exception as e:
        logger.error(f"Error setting free user limit: {e}")
        await message.reply("❌ An error occurred. Please try again.")

async def handle_broadcast_input(message: Message, text: str):
    try:
        owner_id = message.from_user.id
        if not user_manager.is_owner(owner_id):
            await message.reply("❌ You are not authorized to perform this action.")
            return
        from database import DatabaseManager
        db = DatabaseManager()
        users = db.cursor.execute('SELECT user_id FROM users').fetchall()
        count = 0
        for row in users:
            try:
                await app.send_message(row[0], text)
                count += 1
            except Exception:
                continue
        await message.reply(f"✅ Broadcast sent to {count} users.")
    except Exception as e:
        logger.error(f"Error broadcasting: {e}")
        await message.reply("❌ An error occurred. Please try again.")

def reset_copy_parameters(user_id):
    session_handler.update_user_session(user_id, {
        'source_channel': None,
        'source_title': None,
        'target_channel': None,
        'target_title': None,
        'start_msg_id': None,
        'end_msg_id': None,
        'state': 'main_menu'
    })

async def get_main_menu_keyboard(user_id: int):
    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
    return InlineKeyboardMarkup([[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]])

@app.on_message(filters.command("reset") & filters.private)
async def reset_user_limit(client: Client, message: Message):
    logger.info("/reset handler called")
    user_id = message.from_user.id
    # Check if sender is owner
    if not user_manager.is_owner(user_id):
        logger.info(f"User {user_id} is not owner, aborting /reset")
        await message.reply("❌ Only the owner can use this command.")
        return
    # Parse command
    parts = message.text.strip().split()
    logger.info(f"/reset command parts: {parts}")
    if len(parts) != 2 or not parts[1].isdigit():
        logger.info("/reset command usage error")
        await message.reply("Usage: /reset <user_id>")
        return
    target_user_id = int(parts[1])
    logger.info(f"Checking if user {target_user_id} exists in DB")
    user = user_manager.db.get_user(target_user_id)
    if not user:
        logger.info(f"User {target_user_id} does not exist in DB")
        await message.reply(f"❌ User {target_user_id} does not exist in the database.")
        return
    try:
        logger.info(f"Resetting message count for user {target_user_id}")
        user_manager.db.reset_message_count(target_user_id)
        await message.reply(f"✅ Message count reset for user {target_user_id}.")
    except Exception as e:
        logger.error(f"Error resetting message count for {target_user_id}: {e}")
        await message.reply("❌ Failed to reset message count.")

if __name__ == "__main__":
    logger.info("Starting Telegram Copier Bot...")
    try:
        app.run()
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Bot error: {e}")
    finally:
        logger.info("Cleaning up...")
        asyncio.run(session_handler.disconnect_all())
