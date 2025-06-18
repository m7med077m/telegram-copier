import asyncio
import logging
import time
import re
import os
from typing import Optional, Callable, Tuple
from pyrogram import Client
from pyrogram.types import Message
from pyrogram.errors import FloodWait, UserAlreadyParticipant, InviteHashExpired, InviteHashInvalid
from config import PROGRESS_UPDATE_INTERVAL, MAX_RETRIES, RETRY_DELAY

logger = logging.getLogger(__name__)

class MessageHandler:
    def __init__(self, session_handler, user_manager):
        self.session_handler = session_handler
        self.user_manager = user_manager

    def clean_channel_input(self, channel: str) -> tuple[str, str]:
        """Clean and normalize channel input, return (cleaned_input, input_type)"""
        channel = channel.strip()
        
        # Check for invitation link
        invite_match = re.search(r't\.me/(?:\+|joinchat/)([A-Za-z0-9_-]+)', channel)
        if invite_match:
            return invite_match.group(1), 'invite'
        
        # Remove https://t.me/ prefix for regular channels
        if channel.startswith('https://t.me/'):
            channel = channel.replace('https://t.me/', '')
        
        # Remove @ prefix for usernames
        if channel.startswith('@'):
            channel = channel[1:]
        
        # If it's a numeric ID, ensure it has the proper prefix
        if channel.lstrip('-').isdigit():
            # Add -100 prefix if it's a channel ID and doesn't have it
            if not channel.startswith('-100') and len(channel) > 3:
                channel = f"-100{channel.lstrip('-')}"
            return channel, 'id'
        
        # For usernames, return without @ 
        return channel, 'username'

    async def join_channel_by_invite(self, client: Client, invite_hash: str) -> tuple[bool, str, str]:
        """
        Join channel using invite link and return (success, channel_id, channel_title)
        """
        try:
            logger.info(f"Attempting to join channel with invite hash: {invite_hash}")
            
            # Join the channel using invite link
            chat = await client.join_chat(f"https://t.me/+{invite_hash}")
            
            logger.info(f"Successfully joined channel: {chat.title} (ID: {chat.id})")
            return True, str(chat.id), chat.title
            
        except UserAlreadyParticipant:
            # Already a member, try to get chat info
            try:
                # Try to get chat info using the invite link
                chat = await client.get_chat(f"https://t.me/+{invite_hash}")
                return True, str(chat.id), chat.title
            except Exception as e:
                logger.error(f"Error resolving chat from invite: {e}")
                # Try to find the chat in user's dialogs
                try:
                    async for dialog in client.get_dialogs():
                        if dialog.chat.type in ["channel", "supergroup"]:
                            # Check if this chat matches the invite hash
                            try:
                                invite_link = await client.get_chat_invite_link(dialog.chat.id)
                                if invite_hash in invite_link.invite_link:
                                    return True, str(dialog.chat.id), dialog.chat.title
                            except:
                                continue
                    return False, "", "Could not find the channel. Please try using the channel's username or ID."
                except Exception as e:
                    logger.error(f"Error searching dialogs: {e}")
                    return False, "", "Could not find the channel. Please try using the channel's username or ID."
                
        except InviteHashExpired:
            return False, "", "Invitation link has expired"
            
        except InviteHashInvalid:
            return False, "", "Invalid invitation link"
            
        except Exception as e:
            logger.error(f"Error joining channel with invite {invite_hash}: {e}")
            return False, "", f"Failed to join channel: {str(e)}"

    async def validate_channel_access(self, client: Client, channel_input: str) -> tuple[bool, str, str]:
        """Validate channel access and return (success, channel_id, channel_title)"""
        try:
            # Clean the channel input
            cleaned_channel, input_type = self.clean_channel_input(channel_input)
            if not cleaned_channel:
                return False, "", "❌ Invalid channel format. Please provide a valid channel username or ID."
            
            # Handle invitation links
            if input_type == 'invite':
                return await self.join_channel_by_invite(client, cleaned_channel)
            
            # Method 1: Try direct access with proper channel ID format
            try:
                if input_type == 'username':
                    chat = await client.get_chat(f"@{cleaned_channel}")
                else:  # ID
                    # Ensure proper channel ID format
                    if not cleaned_channel.startswith('-100'):
                        cleaned_channel = f"-100{cleaned_channel.lstrip('-')}"
                    chat = await client.get_chat(cleaned_channel)
            except Exception as e:
                logger.warning(f"Direct access failed: {e}")
                chat = None
            
            # Method 2: Search in dialogs if direct access failed
            if not chat:
                try:
                    async for dialog in client.get_dialogs():
                        if dialog.chat.type in ["channel", "supergroup"]:
                            if (input_type == 'username' and dialog.chat.username == cleaned_channel) or \
                               (input_type == 'id' and str(dialog.chat.id) == cleaned_channel):
                                chat = dialog.chat
                                break
                except Exception as e:
                    logger.warning(f"Dialog search failed: {e}")
            
            if not chat:
                return False, "", "❌ Channel not found or no access. Please check the channel name/ID and ensure you're a member."
            
            # Enhanced debug log for chat type and info
            if chat:
                logger.info(f"validate_channel_access: chat.id={chat.id}, chat.title={getattr(chat, 'title', None)}, chat.type={getattr(chat, 'type', None)}, chat.type(repr)={repr(getattr(chat, 'type', None))}, chat.type(type)={type(getattr(chat, 'type', None))}")
            # Fix: Accept both string and enum types for chat.type
            chat_type_val = getattr(chat, 'type', '')
            chat_type_str = str(chat_type_val)
            # Accept if chat.type is string or enum with value 'channel' or 'supergroup'
            if hasattr(chat_type_val, 'value'):
                chat_type_str = chat_type_val.value
            if not ("channel" in chat_type_str or "supergroup" in chat_type_str):
                return False, "", f"❌ The provided chat is not a channel or supergroup. (type={chat_type_str})"
            
            try:
                # Try to get channel info to verify access
                await client.get_chat_member(chat.id, "me")
                return True, str(chat.id), chat.title
            except Exception as e:
                logger.warning(f"Access verification failed: {e}")
                return False, "", "❌ No access to the channel. Please ensure you're a member and have necessary permissions."
                
        except Exception as e:
            logger.error(f"Channel validation error: {e}")
            return False, "", f"❌ Error validating channel: {str(e)}"

    async def copy_messages(self, user_id: int, source_id: str, target_id: str, start_msg_id: int, end_msg_id: int, progress_callback: Optional[Callable] = None, status_message=None) -> tuple[bool, str]:
        """Copy messages from source to target channel by downloading and re-uploading, with detailed monitoring and temp cleanup."""
        try:
            client = await self.session_handler.get_user_client(user_id)
            if not client:
                return False, "❌ No active session found. Please create a session first."

            copied = 0
            failed = 0
            total = end_msg_id - start_msg_id + 1
            temp_dir = "temp_downloads"
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            logger.info(f"Starting copy operation: {total} messages from {source_id} to {target_id}")
            status_msg = status_message
            avg_upload_speeds = []
            stats = self.user_manager.get_user_stats(user_id)
            is_free_user = not (stats['is_owner'] or stats['is_vip'])
            
            for idx, msg_id in enumerate(range(start_msg_id, end_msg_id + 1), 1):
                # Check if operation was cancelled
                session = self.session_handler.get_user_session(user_id)
                if session.get('is_cancelled'):
                    # Cleanup temp files before returning
                    for file in os.listdir(temp_dir):
                        file_path = os.path.join(temp_dir, file)
                        try:
                            if os.path.isfile(file_path):
                                os.remove(file_path)
                        except Exception as e:
                            logger.warning(f"Error removing file {file_path}: {e}")
                    return True, f"🛑 Copy operation cancelled by user. Copied {copied} messages before cancellation."
                
                # Check message limit for free users
                if is_free_user and stats['message_count'] >= stats['message_limit']:
                    from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton
                    keyboard = InlineKeyboardMarkup([
                        [InlineKeyboardButton("⭐ Upgrade to VIP", callback_data="show_vip_upgrade")],
                        [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
                    ])
                    if status_msg:
                        await status_msg.edit_text(
                            f"❌ You have reached your daily free message limit.\n\nUpgrade to VIP for unlimited copying!",
                            reply_markup=keyboard
                        )
                    return True, ""
                try:
                    message = await client.get_messages(source_id, msg_id)
                    if not message or message.empty:
                        failed += 1
                        continue

                    details = [
                        f"📝 Processing message {msg_id} ({idx}/{total})...",
                        f"📅 Date: {message.date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(message, 'date') else ''}"
                    ]
                    file = None
                    media_type = None
                    file_size = None
                    if message.media:
                        media_type = message.media.value if hasattr(message.media, 'value') else str(message.media)
                        details.append(f"📎 Type: {media_type}")
                        if hasattr(message, 'video') and message.video:
                            file_size = message.video.file_size
                            details.append(f"🎥 Video: {file_size / (1024*1024):.1f}MB")
                            details.append(f"⏱️ Duration: {message.video.duration}s")
                            details.append(f"📐 Resolution: {message.video.width}x{message.video.height}")
                        elif hasattr(message, 'document') and message.document:
                            file_size = message.document.file_size
                            details.append(f"📄 Document: {message.document.file_name}")
                            details.append(f"📦 Size: {file_size / (1024*1024):.1f}MB")
                        elif hasattr(message, 'photo') and message.photo:
                            file_size = message.photo.file_size
                            details.append(f"🖼️ Photo: {file_size / (1024*1024):.1f}MB")
                        elif hasattr(message, 'audio') and message.audio:
                            file_size = message.audio.file_size
                            details.append(f"🎵 Audio: {file_size / (1024*1024):.1f}MB")
                            details.append(f"⏱️ Duration: {message.audio.duration}s")
                        if message.caption:
                            caption_preview = message.caption[:50] + "..." if len(message.caption) > 50 else message.caption
                            details.append(f"📝 Caption: {caption_preview}")
                        # --- Fix photo extension ---
                        ext = ".jpg" if media_type == "photo" else f".tmp"
                        temp_file = os.path.join(temp_dir, f"temp_{msg_id}_{media_type}{ext}")
                        # Download with progress
                        last_edit_time = time.time()
                        min_edit_interval = 1
                        download_size = file_size or 0
                        download_speed_samples = []
                        max_samples = 10
                        last_download_bytes = 0
                        download_start_time = time.time()
                        async def progress_callback_dl(current, total_size):
                            nonlocal last_edit_time, download_size, download_speed_samples, last_download_bytes
                            now = time.time()
                            download_size = total_size
                            time_diff = now - download_start_time
                            bytes_diff = current - last_download_bytes
                            download_speed = bytes_diff / (now - last_edit_time) if now - last_edit_time > 0 else 0
                            download_speed_mb = download_speed / (1024 * 1024)
                            download_speed_samples.append(download_speed_mb)
                            if len(download_speed_samples) > max_samples:
                                download_speed_samples.pop(0)
                            avg_download_speed = sum(download_speed_samples) / len(download_speed_samples) if download_speed_samples else 0
                            if now - last_edit_time >= min_edit_interval:
                                percentage = current * 100 / total_size if total_size else 0
                                bar_length = 30
                                filled_length = int(bar_length * current // total_size) if total_size else 0
                                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                                status_text = (
                                    f"📝 Processing message {msg_id} ({idx}/{total})...\n"
                                    f"📅 Date: {message.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                    + "\n".join(details) + "\n"
                                    f"📥 Download Progress:\n[{bar}] {percentage:.1f}%\nSize: {current/(1024*1024):.1f}MB / {total_size/(1024*1024):.1f}MB\n"
                                    f"⬇️ Current Speed: {download_speed_mb:.1f} MB/s\n"
                                    f"⬇️ Average Speed: {avg_download_speed:.1f} MB/s\n"
                                    f"✓ Success: {copied}\n❌ Failed: {failed}"
                                )
                                if status_msg:
                                    try:
                                        await status_msg.edit_text(status_text)
                                    except Exception:
                                        pass
                                last_edit_time = now
                                last_download_bytes = current
                        file = await client.download_media(message, file_name=temp_file, progress=progress_callback_dl)
                        if not file:
                            failed += 1
                            continue
                        # Upload with progress
                        media_handlers = {
                            "photo": client.send_photo,
                            "video": client.send_video,
                            "document": client.send_document,
                            "audio": client.send_audio,
                            "voice": client.send_voice,
                            "animation": client.send_animation,
                            "sticker": client.send_sticker,
                            "video_note": client.send_video_note
                        }
                        handler = media_handlers.get(media_type)
                        send_kwargs = {"caption": message.caption if hasattr(message, 'caption') else ''}
                        if media_type == "video" and hasattr(message, 'video'):
                            send_kwargs["duration"] = getattr(message.video, "duration", None)
                            send_kwargs["width"] = getattr(message.video, "width", None)
                            send_kwargs["height"] = getattr(message.video, "height", None)
                        if media_type == "document" and hasattr(message, 'document'):
                            send_kwargs["file_name"] = getattr(message.document, "file_name", None)
                        # Upload progress
                        upload_start = time.time()
                        upload_last = upload_start
                        upload_bytes = 0
                        upload_speed_samples = []
                        async def progress_callback_ul(current, total_size):
                            nonlocal upload_last, upload_bytes, upload_speed_samples, last_edit_time
                            now = time.time()
                            if now - upload_last >= min_edit_interval:
                                percentage = current * 100 / download_size if download_size else 0
                                bar_length = 30
                                filled_length = int(bar_length * current // download_size) if download_size else 0
                                bar = '█' * filled_length + '░' * (bar_length - filled_length)
                                speed = (current - upload_bytes) / (now - upload_last) / (1024*1024) if now - upload_last > 0 else 0
                                upload_speed_samples.append(speed)
                                if len(upload_speed_samples) > 10:
                                    upload_speed_samples.pop(0)
                                avg_speed = sum(upload_speed_samples) / len(upload_speed_samples) if upload_speed_samples else 0
                                upload_status = (
                                    f"📝 Processing message {msg_id} ({idx}/{total})...\n"
                                    f"📅 Date: {message.date.strftime('%Y-%m-%d %H:%M:%S')}\n"
                                    + "\n".join(details) + "\n"
                                    f"📤 Upload Progress:\n[{bar}] {percentage:.1f}%\nSize: {current/(1024*1024):.1f}MB / {download_size/(1024*1024):.1f}MB\n"
                                    f"⬆️ Current Speed: {speed:.1f} MB/s\n"
                                    f"⬆️ Average Speed: {avg_speed:.1f} MB/s\n"
                                    f"✓ Success: {copied}\n❌ Failed: {failed}"
                                )
                                if status_msg:
                                    try:
                                        await status_msg.edit_text(upload_status)
                                    except Exception:
                                        pass
                                upload_last = now
                                upload_bytes = current
                        # Send the media
                        sent_message = await handler(target_id, file, **send_kwargs, progress=progress_callback_ul)
                        if sent_message:
                            copied += 1
                            # Increment message count for free users
                            stats = self.user_manager.get_user_stats(user_id)
                            if not (stats['is_owner'] or stats['is_vip']):
                                self.user_manager.increment_message_count(user_id)
                        else:
                            failed += 1
                    # If the message has no media, but has text, copy the text message
                    if not message.media and (message.text or message.caption):
                        text_content = message.text or message.caption
                        await client.send_message(target_id, text_content)
                        copied += 1
                        # Increment message count for free users
                        stats = self.user_manager.get_user_stats(user_id)
                        if not (stats['is_owner'] or stats['is_vip']):
                            self.user_manager.increment_message_count(user_id)
                        continue
                except Exception as e:
                    logger.error(f"Error processing message {msg_id}: {e}")
                    failed += 1

            # Final status update
            if status_msg:
                final_status = f"✅ Copy complete: {copied} messages copied, {failed} failed."
                await status_msg.edit_text(final_status)

            # Cleanup: Remove temp files
            for file in os.listdir(temp_dir):
                file_path = os.path.join(temp_dir, file)
                try:
                    if os.path.isfile(file_path):
                        os.remove(file_path)
                except Exception as e:
                    logger.warning(f"Error removing file {file_path}: {e}")
            
            return True, f"✅ Successfully copied {copied} messages."
        
        except Exception as e:
            logger.error(f"Error in copy_messages: {e}")
            return False, f"❌ Error during message copy: {str(e)}"
