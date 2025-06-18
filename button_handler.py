import asyncio
import logging
from typing import Optional
from pyrogram.types import CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from pyrogram.errors import FloodWait
from utils import validate_phone_number, parse_message_range, format_speed, format_time

logger = logging.getLogger(__name__)

class ButtonHandler:
    def __init__(self, session_handler, user_manager, message_handler):
        self.session_handler = session_handler
        self.user_manager = user_manager
        self.message_handler = message_handler

    async def handle_callback(self, callback_query: CallbackQuery):
        """Handle all callback queries"""
        try:
            await callback_query.answer()
            data = callback_query.data
            
            if data == "main_menu":
                await self.show_main_menu(callback_query)
            elif data == "create_session":
                await self.show_session_creation_menu(callback_query)
            elif data == "session_phone":
                await self.handle_phone_session_creation(callback_query)
            elif data == "session_string":
                await self.handle_string_session_creation(callback_query)
            elif data == "view_session":
                await self.show_session_info(callback_query)
            elif data == "delete_session":
                await self.handle_session_deletion(callback_query)
            elif data == "set_source":
                await self.handle_source_channel_setup(callback_query)
            elif data == "set_target":
                await self.handle_target_channel_setup(callback_query)
            elif data == "set_range":
                await self.handle_message_range_setup(callback_query)
            elif data == "start_copy":
                await self.handle_copy_start(callback_query)
            elif data == "view_stats":
                await self.show_user_stats(callback_query)
            elif data == "upgrade_vip":
                await self.show_vip_upgrade(callback_query)
            elif data == "vip_benefits":
                await self.show_vip_benefits(callback_query)
            elif data == "payment_methods":
                await self.show_payment_methods(callback_query)
            elif data == "admin_panel" and self.user_manager.is_owner(callback_query.from_user.id):
                await self.show_admin_panel(callback_query)
            elif data == "promote_vip" and self.user_manager.is_owner(callback_query.from_user.id):
                await self.handle_vip_promotion(callback_query)
            elif data == "demote_vip" and self.user_manager.is_owner(callback_query.from_user.id):
                await self.handle_vip_demotion(callback_query)
            elif data == "set_free_limit" and self.user_manager.is_owner(callback_query.from_user.id):
                await self.handle_set_free_limit(callback_query)
            elif data == "broadcast" and self.user_manager.is_owner(callback_query.from_user.id):
                await self.handle_broadcast_start(callback_query)
            elif data == "user_stats" and self.user_manager.is_owner(callback_query.from_user.id):
                await self.handle_user_stats(callback_query)
            elif data == "reset_user_limit" and self.user_manager.is_owner(callback_query.from_user.id):
                await self.handle_reset_user_limit(callback_query)
            elif data == "personal_copy":
                await self.handle_personal_copy(callback_query)
            elif data == "how_to_use":
                await self.show_how_to_use(callback_query)
            elif data == "how_to_use_ar":
                await self.show_how_to_use_arabic(callback_query)
            else:
                await callback_query.edit_message_text("Unknown command. Please try again.")
                
        except Exception as e:
            logger.error(f"Error in callback handler: {e}")
            try:
                await callback_query.edit_message_text("❌ An error occurred. Please try again.")
            except:
                pass

    async def show_main_menu(self, callback_query: CallbackQuery):
        """Show main menu with current status"""
        try:
            user_id = callback_query.from_user.id
            logger.info(f"Loading main menu for user {user_id}")
            
            # Get session data safely
            try:
                session = self.session_handler.get_user_session(user_id)
            except Exception as e:
                logger.error(f"Error getting session for user {user_id}: {e}")
                session = {}
            
            # Check if user has active session
            has_session = False
            try:
                client = await self.session_handler.get_user_client(user_id)
                has_session = client is not None
                logger.info(f"User {user_id} session status: {has_session}")
            except Exception as e:
                logger.warning(f"Error checking client for user {user_id}: {e}")
                has_session = False
            
            # Get current settings safely
            source_title = session.get('source_title') or 'Not set'
            target_title = session.get('target_title') or 'Not set'
            source_id = session.get('source_channel')
            target_id = session.get('target_channel')
            start_msg = session.get('start_msg_id') or 'Not set'
            end_msg = session.get('end_msg_id') or 'Not set'
            
            # Status text
            status_text = "🤖 **Telegram Message Copier Bot**\n\n"
            status_text += f"📱 **Session:** {'✅ Active' if has_session else '❌ Not created'}\n"
            status_text += f"📥 **Source:** {source_title}\n"
            if source_id:
                status_text += f"   ID: `{source_id}`\n"
            status_text += f"📤 **Target:** {target_title}\n"
            if target_id:
                status_text += f"   ID: `{target_id}`\n"
            status_text += f"📊 **Range:** {start_msg} - {end_msg}\n"
            
            if start_msg != 'Not set' and end_msg != 'Not set':
                try:
                    total = int(end_msg) - int(start_msg) + 1
                    status_text += f"📈 **Total Messages:** {total}\n"
                except:
                    pass
            
            # User stats
            try:
                stats = self.user_manager.get_user_stats(user_id)
                if stats['is_owner']:
                    status_text += f"\n👑 **Owner Account**"
                elif stats['is_vip']:
                    status_text += f"\n⭐ **VIP Account**"
                else:
                    status_text += f"\n🆓 **Free Account**"
                    status_text += f"\n📨 **Messages Used:** {stats['message_count']}/{stats['message_limit']}"
            except Exception as e:
                logger.warning(f"Error getting user stats for {user_id}: {e}")
                status_text += f"\n🆓 **Free Account**"
            
            # Create keyboard
            keyboard = []
            
            # Add How to Use button at the top
            keyboard.append([InlineKeyboardButton("📖 How to Use", callback_data="how_to_use")])
            
            # Session management
            if has_session:
                keyboard.append([InlineKeyboardButton("🔍 View Session", callback_data="view_session")])
                keyboard.append([InlineKeyboardButton("🗑 Delete Session", callback_data="delete_session")])
            else:
                keyboard.append([InlineKeyboardButton("🔑 Create Session", callback_data="create_session")])
            
            # Channel setup (only if session exists)
            if has_session:
                keyboard.append([
                    InlineKeyboardButton("📥 Set Source", callback_data="set_source"),
                    InlineKeyboardButton("📤 Set Target", callback_data="set_target")
                ])
                keyboard.append([InlineKeyboardButton("📊 Set Range", callback_data="set_range")])
                
                # Copy button (only if all settings are configured)
                if all([source_id, target_id, start_msg != 'Not set', end_msg != 'Not set']):
                    keyboard.append([InlineKeyboardButton("🚀 Start Copying", callback_data="start_copy")])
            
            # Stats and VIP
            keyboard.append([
                InlineKeyboardButton("📈 My Stats", callback_data="view_stats"),
                InlineKeyboardButton("⭐ Upgrade VIP", callback_data="upgrade_vip")
            ])
            
            # New button for personal copy
            keyboard.append([InlineKeyboardButton("📩 Copy Message(s) to Me", callback_data="personal_copy")])
            
            try:
                if self.user_manager.is_owner(user_id):
                    keyboard.append([InlineKeyboardButton("⚙️ Admin Panel", callback_data="admin_panel")])
            except Exception as e:
                logger.warning(f"Error checking owner status for {user_id}: {e}")
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await callback_query.edit_message_text(status_text, reply_markup=reply_markup,  )
            logger.info(f"Main menu loaded successfully for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error showing main menu for user {callback_query.from_user.id}: {e}")
            try:
                simple_keyboard = [[InlineKeyboardButton("🔑 Create Session", callback_data="create_session")]]
                reply_markup = InlineKeyboardMarkup(simple_keyboard)
                await callback_query.edit_message_text(
                    "🤖 **Telegram Message Copier Bot**\n\n❌ Error loading full menu. Please start by creating a session.",
                    reply_markup=reply_markup,
                     
                )
            except Exception as fallback_error:
                logger.error(f"Fallback menu also failed: {fallback_error}")
                await callback_query.edit_message_text("❌ System error. Please restart the bot with /start")

    async def show_session_creation_menu(self, callback_query: CallbackQuery):
        """Show session creation options"""
        text = "🔑 **Create Session**\n\n"
        text += "Choose how you want to create your session:\n\n"
        text += "📱 **Phone Number:** Use your phone number to create a new session\n"
        text += "📄 **Session String:** Import an existing session string"
        
        keyboard = [
            [InlineKeyboardButton("📱 Phone Number", callback_data="session_phone")],
            [InlineKeyboardButton("📄 Session String", callback_data="session_string")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def handle_phone_session_creation(self, callback_query: CallbackQuery):
        """Handle phone number session creation"""
        user_id = callback_query.from_user.id
        self.session_handler.update_user_session(user_id, {'state': 'awaiting_phone'})
        
        text = "📱 **Phone Number Session**\n\n"
        text += "Please send your phone number in international format.\n"
        text += "Example: `+1234567890`\n\n"
        text += "⚠️ Make sure to include the country code with the + sign."
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="create_session")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def handle_string_session_creation(self, callback_query: CallbackQuery):
        """Handle session string import"""
        user_id = callback_query.from_user.id
        self.session_handler.update_user_session(user_id, {'state': 'awaiting_session_string'})
        
        text = "📄 **Session String Import**\n\n"
        text += "Please send your session string.\n\n"
        text += "⚠️ **Important:** Never share your session string with others!\n"
        text += "Anyone with your session string can access your Telegram account."
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="create_session")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def show_session_info(self, callback_query: CallbackQuery):
        """Show current session information"""
        try:
            user_id = callback_query.from_user.id
            logger.info(f"Loading session info for user {user_id}")
            
            try:
                client = await self.session_handler.get_user_client(user_id)
            except Exception as e:
                logger.error(f"Error getting client for user {user_id}: {e}")
                client = None
            
            if not client:
                text = "❌ No active session found."
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
            else:
                try:
                    me = await client.get_me()
                    text = "🔍 **Session Information**\n\n"
                    text += f"👤 **Name:** {(me.first_name or '')} {(me.last_name or '')}".strip()
                    text += f"\n📱 **Phone:** {me.phone_number or 'Not available'}"
                    text += f"\n🆔 **User ID:** `{me.id}`"
                    text += f"\n📧 **Username:** @{me.username or 'Not set'}"
                    text += f"\n✅ **Status:** Connected"
                    
                    # Get session details safely
                    try:
                        session = self.session_handler.get_user_session(user_id)
                        last_active = session.get('last_active', 'Unknown')
                        if isinstance(last_active, (int, float)):
                            from datetime import datetime
                            last_active = datetime.fromtimestamp(last_active).strftime('%Y-%m-%d %H:%M:%S')
                        text += f"\n📅 **Last Active:** {last_active}"
                    except Exception as e:
                        logger.warning(f"Error getting session details: {e}")
                    
                except Exception as e:
                    logger.error(f"Error getting session info for user {user_id}: {e}")
                    text = f"❌ Error getting session info: {str(e)}"
                
                keyboard = [
                    [InlineKeyboardButton("🗑 Delete Session", callback_data="delete_session")],
                    [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
                ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await callback_query.edit_message_text(text, reply_markup=reply_markup,  )
            
        except Exception as e:
            logger.error(f"Error showing session info: {e}")
            try:
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await callback_query.edit_message_text(
                    "❌ Error loading session info. Please try again.",
                    reply_markup=reply_markup
                )
            except:
                pass

    async def handle_session_deletion(self, callback_query: CallbackQuery):
        """Handle session deletion"""
        try:
            user_id = callback_query.from_user.id
            logger.info(f"Deleting session for user {user_id}")
            
            # Clear session completely
            await self.session_handler.clear_user_session(user_id)
            
            text = "✅ **Session Deleted**\n\n"
            text += "Your session has been completely removed.\n"
            text += "All stored data (channels, message ranges) has been cleared.\n\n"
            text += "You can create a new session anytime."
            
            keyboard = [
                [InlineKeyboardButton("🔑 Create New Session", callback_data="create_session")],
                [InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]
            ]
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            await callback_query.edit_message_text(text, reply_markup=reply_markup,  )
            logger.info(f"Session deleted successfully for user {user_id}")
            
        except Exception as e:
            logger.error(f"Error deleting session for user {callback_query.from_user.id}: {e}")
            try:
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await callback_query.edit_message_text(
                    "❌ Error deleting session. Please try again.",
                    reply_markup=reply_markup
                )
            except:
                pass

    async def handle_source_channel_setup(self, callback_query: CallbackQuery):
        """Handle source channel setup"""
        user_id = callback_query.from_user.id
        self.session_handler.update_user_session(user_id, {'state': 'awaiting_source_channel'})
        
        text = "📥 **Set Source Channel**\n\n"
        text += "Send the source channel information:\n\n"
        text += "✅ **Supported formats:**\n"
        text += "• Channel username: `@channelname`\n"
        text += "• Channel link: `https://t.me/channelname`\n"
        text += "• Channel ID: `-1001234567890`\n"
        text += "• Invitation link: `https://t.me/+AbCdEfGhIj`\n"
        text += "• Message link: `https://t.me/c/123456789/1` or `https://t.me/channelname/1`\n\n"
        text += "💡 **For private channels:** Use invitation links or message links for best results"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def handle_target_channel_setup(self, callback_query: CallbackQuery):
        """Handle target channel setup"""
        user_id = callback_query.from_user.id
        self.session_handler.update_user_session(user_id, {'state': 'awaiting_target_channel'})
        
        text = "📤 **Set Target Channel**\n\n"
        text += "Send the target channel information:\n\n"
        text += "✅ **Supported formats:**\n"
        text += "• Channel username: `@channelname`\n"
        text += "• Channel link: `https://t.me/channelname`\n"
        text += "• Channel ID: `-1001234567890`\n"
        text += "• **Invitation link: `https://t.me/+AbCdEfGhIj`**\n\n"
        text += "⚠️ **Note:** You must be admin in the target channel to copy messages"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def handle_message_range_setup(self, callback_query: CallbackQuery):
        """Handle message range setup"""
        user_id = callback_query.from_user.id
        self.session_handler.update_user_session(user_id, {'state': 'awaiting_message_range'})
        
        text = "📊 **Set Message Range**\n\n"
        text += "Send the message range you want to copy:\n\n"
        text += "**Format:** `start_id-end_id`\n"
        text += "**Examples:**\n"
        text += "• `1-100` - Copy messages 1 to 100\n"
        text += "• `50-150` - Copy messages 50 to 150\n"
        text += "• `1000-2000` - Copy messages 1000 to 2000\n\n"
        text += "💡 **Tip:** Check the source channel to find the message IDs you want"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def handle_copy_start(self, callback_query: CallbackQuery):
        """Handle copy operation start"""
        try:
            user_id = callback_query.from_user.id
            session = self.session_handler.get_user_session(user_id)
            
            # Validate all required data
            source_id = session.get('source_channel')
            target_id = session.get('target_channel')
            start_msg_id = session.get('start_msg_id')
            end_msg_id = session.get('end_msg_id')
            
            if not all([source_id, target_id, start_msg_id, end_msg_id]):
                text = "❌ **Missing Information**\n\n"
                text += "Please configure all settings before starting:\n"
                if not source_id:
                    text += "• Source channel not set\n"
                if not target_id:
                    text += "• Target channel not set\n"
                if not start_msg_id or not end_msg_id:
                    text += "• Message range not set\n"
                
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await callback_query.edit_message_text(text, reply_markup=reply_markup,  )
                return
            
            # Check user limits
            if not self.user_manager.can_send_messages(user_id):
                text = "❌ **Message Limit Reached**\n\n"
                text += "You have reached your daily message limit.\n"
                text += "Upgrade to VIP for unlimited messages!"
                
                keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await callback_query.edit_message_text(text, reply_markup=reply_markup,  )
                return
            
            # Show copy confirmation
            source_title = session.get('source_title', 'Unknown')
            target_title = session.get('target_title', 'Unknown')
            total_messages = end_msg_id - start_msg_id + 1
            
            text = "🚀 **Ready to Copy**\n\n"
            text += f"📥 **From:** {source_title}\n"
            text += f"📤 **To:** {target_title}\n"
            text += f"📊 **Range:** {start_msg_id} - {end_msg_id}\n"
            text += f"📈 **Total:** {total_messages} messages\n\n"
            text += "⚡ Starting copy operation..."
            
            await callback_query.edit_message_text(text,  )
            
            # Start copying in background
            asyncio.create_task(self._perform_copy_operation(callback_query, user_id, source_id, target_id, start_msg_id, end_msg_id))
            
        except Exception as e:
            logger.error(f"Error starting copy: {e}")
            await callback_query.edit_message_text("❌ Error starting copy operation.")

    async def _perform_copy_operation(self, callback_query: CallbackQuery, user_id: int, source_id: str, target_id: str, start_msg_id: int, end_msg_id: int):
        """Perform the actual copy operation"""
        try:
            # Progress callback
            async def progress_callback(copied, failed, total):
                try:
                    progress_text = f"🔄 **Copying in Progress**\n\n"
                    progress_text += f"✅ **Copied:** {copied}\n"
                    progress_text += f"❌ **Failed:** {failed}\n"
                    progress_text += f"📊 **Total:** {total}\n"
                    progress_text += f"📈 **Progress:** {((copied + failed) / total * 100):.1f}%"
                    
                    await callback_query.edit_message_text(progress_text,  )
                except:
                    pass
            
            success, result = await self.message_handler.copy_messages(
                user_id, source_id, target_id, start_msg_id, end_msg_id, progress_callback
            )
            
            # Show final result
            if success:
                text = f"✅ **Copy Completed!**\n\n{result}"
            else:
                text = f"❌ **Copy Failed**\n\n{result}"
            
            keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await callback_query.edit_message_text(text, reply_markup=reply_markup,  )
            
        except Exception as e:
            logger.error(f"Error in copy operation: {e}")
            try:
                text = f"❌ **Copy Failed**\n\nError: {str(e)}"
                keyboard = [[InlineKeyboardButton("🔙 Main Menu", callback_data="main_menu")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await callback_query.edit_message_text(text, reply_markup=reply_markup,  )
            except:
                pass

    async def show_user_stats(self, callback_query: CallbackQuery):
        """Show user statistics"""
        try:
            user_id = callback_query.from_user.id
            stats = self.user_manager.get_user_stats(user_id)
            
            text = "📈 **Your Statistics**\n\n"
            
            if stats['is_owner']:
                text += "👑 **Account Type:** Owner\n"
                text += "📨 **Messages:** Unlimited\n"
                text += f"⚡ **Speed:** {stats['speed_limit']:.1f} MB/s\n"
            elif stats['is_vip']:
                text += "⭐ **Account Type:** VIP\n"
                text += "📨 **Messages:** Unlimited\n"
                text += f"⚡ **Speed:** {stats['speed_limit']:.1f} MB/s\n"
            else:
                text += "🆓 **Account Type:** Free\n"
                text += f"📨 **Messages Used:** {stats['message_count']}/{stats['message_limit']}\n"
                text += f"📨 **Remaining:** {stats['remaining_messages']}\n"
                text += f"⚡ **Speed:** {stats['speed_limit']:.1f} MB/s\n"
            
            text += f"\n💾 **Total Sent:** {stats['message_count']}"
            
            keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await callback_query.edit_message_text(text, reply_markup=reply_markup,  )
            
        except Exception as e:
            logger.error(f"Error showing stats: {e}")
            await callback_query.edit_message_text("❌ Error loading statistics.")

    async def show_admin_panel(self, callback_query: CallbackQuery):
        """Show admin panel (owner only)"""
        text = "⚙️ **Admin Panel**\n\n"
        text += "👑 **Owner Controls:**\n"
        text += "• Promote users to VIP\n"
        text += "• Remove VIP status\n"
        text += "• Change message limit for free users\n"
        text += "• Broadcast message to all users\n"
        text += "• View user statistics"
        
        keyboard = [
            [InlineKeyboardButton("⭐ Promote to VIP", callback_data="promote_vip")],
            [InlineKeyboardButton("❌ Remove VIP", callback_data="demote_vip")],
            [InlineKeyboardButton("✏️ Set Free User Limit", callback_data="set_free_limit")],
            [InlineKeyboardButton("📢 Broadcast", callback_data="broadcast")],
            [InlineKeyboardButton("📊 User Stats", callback_data="user_stats")],
            [InlineKeyboardButton("🔄 Reset User Limit", callback_data="reset_user_limit")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def handle_vip_promotion(self, callback_query: CallbackQuery):
        """Handle VIP promotion"""
        user_id = callback_query.from_user.id
        self.session_handler.update_user_session(user_id, {'state': 'awaiting_vip_promotion'})
        
        text = "⭐ **Promote to VIP**\n\n"
        text += "Send the user ID to promote to VIP status.\n"
        text += "Example: `123456789`"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def handle_vip_demotion(self, callback_query: CallbackQuery):
        """Handle VIP demotion"""
        user_id = callback_query.from_user.id
        self.session_handler.update_user_session(user_id, {'state': 'awaiting_vip_demotion'})
        
        text = "❌ **Remove VIP Status**\n\n"
        text += "Send the user ID to remove VIP status.\n"
        text += "Example: `123456789`"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def handle_set_free_limit(self, callback_query: CallbackQuery):
        """Handle setting free user message limit"""
        user_id = callback_query.from_user.id
        self.session_handler.update_user_session(user_id, {'state': 'awaiting_free_limit'})
        
        text = "✏️ **Set Free User Message Limit**\n\n"
        text += "Send the new daily message limit for free users (number):"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def handle_broadcast_start(self, callback_query: CallbackQuery):
        """Handle broadcast message to all users"""
        user_id = callback_query.from_user.id
        self.session_handler.update_user_session(user_id, {'state': 'awaiting_broadcast'})
        
        text = "📢 **Broadcast**\n\n"
        text += "Send the message you want to broadcast to all users:"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def handle_user_stats(self, callback_query: CallbackQuery):
        """Handle viewing user statistics"""
        from database import DatabaseManager
        db = DatabaseManager()
        total = db.cursor.execute('SELECT COUNT(*) FROM users').fetchone()[0]
        vips = db.cursor.execute('SELECT COUNT(*) FROM users WHERE is_vip=1').fetchone()[0]
        owners = db.cursor.execute('SELECT COUNT(*) FROM users WHERE is_owner=1').fetchone()[0]
        
        text = f"📊 **User Stats**\n\n"
        text += f"Total users: {total}\n"
        text += f"VIPs: {vips}\n"
        text += f"Owners: {owners}"
        
        keyboard = [[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def show_vip_upgrade(self, callback_query: CallbackQuery):
        """Show VIP upgrade info and options."""
        text = (
            "⭐ <b>Upgrade to VIP</b> ⭐\n\n"
            "Unlock unlimited messages, faster speed, and premium support!\n\n"
            "<b>VIP Features:</b>\n"
            "• Unlimited message copying\n"
            "• Increased speed\n"
            "• Priority support\n\n"
            "To become VIP, see payment methods or contact the admin."
        )
        keyboard = [
            [InlineKeyboardButton("💎 VIP Benefits", callback_data="vip_benefits")],
            [InlineKeyboardButton("💳 Payment Methods", callback_data="payment_methods")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await callback_query.edit_message_text(text, reply_markup=reply_markup)

    async def show_vip_benefits(self, callback_query: CallbackQuery):
        """Show VIP benefits."""
        text = (
            "💎 <b>VIP Benefits</b> 💎\n\n"
            "• Unlimited message copying\n"
            "• Increased speed (up to 1 Gb/s)\n"
            "• No daily limits\n"
            "• Priority support from the admin\n"
            "• Early access to new features\n\n"
            "Ready to upgrade? See payment methods or contact the admin."
        )
        keyboard = [
            [InlineKeyboardButton("💳 Payment Methods", callback_data="payment_methods")],
            [InlineKeyboardButton("🔙 Back", callback_data="upgrade_vip")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await callback_query.edit_message_text(text, reply_markup=reply_markup)

    async def show_payment_methods(self, callback_query: CallbackQuery):
        """Show payment methods and admin contact."""
        text = (
            "💳 <b>Payment Methods</b> 💳\n\n"
            "Lifetime VIP: <b>200 EGP</b> or <b>5$</b>\n\n"
            "<b>Binance ID 🏦:</b> <code>789564679</code>\n"
            "USDT (TRC 20) 📱: <code>TE1S4PeEws1xq5QaehdrZFW4fPZYZbYiUu</code>\n"
            "Vodafone Cash 🔴: <code>01015339426</code>\n"
            "Instapay 💳: <code>mohamed1573@instapay</code>\n\n"
            "After payment, send your user ID and payment proof to the admin.\n\n"
            "<b>Admin:</b> <a href='https://t.me/M7MED1573'>@M7MED1573</a>"
        )
        keyboard = [
            [InlineKeyboardButton("🔙 Back", callback_data="upgrade_vip")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await callback_query.edit_message_text(text, reply_markup=reply_markup)

    async def handle_reset_user_limit(self, callback_query: CallbackQuery):
        """Prompt owner to enter user ID to reset message count."""
        await callback_query.edit_message_text(
            "Send the user ID to reset their message count limit:",
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="admin_panel")]])
        )
        # Set state for the owner
        self.session_handler.update_user_session(callback_query.from_user.id, {"state": "awaiting_reset_user_id"})

    async def handle_personal_copy(self, callback_query: CallbackQuery):
        """Prompt user to send a message link or range to copy to themselves."""
        text = "📩 **Copy Messages to Me**\n\n"
        text += "Send me a message link or range to copy:\n\n"
        text += "✅ **Supported formats:**\n"
        text += "• Single message: `https://t.me/c/123456789/1`\n"
        text += "• Message range: `https://t.me/c/123456789/1-10`\n"
        text += "• Public channel: `https://t.me/channelname/1`\n\n"
        text += "💡 **Tips:**\n"
        text += "• For private channels, use message links\n"
        text += "• You can copy multiple messages by using a range\n"
        text += "• Make sure you have access to the messages"
        
        await callback_query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙 Back", callback_data="main_menu")]])
        )
        self.session_handler.update_user_session(callback_query.from_user.id, {"state": "awaiting_personal_copy_link"})

    async def show_how_to_use(self, callback_query: CallbackQuery):
        """Show comprehensive guide"""
        text = "📖 **How to Use the Bot**\n\n"
        
        text += "🤖 **What This Bot Does**\n"
        text += "This bot helps you copy messages from one Telegram channel to another. It's perfect for:\n"
        text += "• Copying content from private channels to your own channel\n"
        text += "• Backing up important messages and media\n"
        text += "• Transferring content between channels\n"
        text += "• Saving messages with all their media (photos, videos, files, etc.)\n"
        text += "• Copying messages directly to your personal chat\n\n"
        
        text += "🔑 **1. Create Session**\n"
        text += "• Click 'Create Session' in the main menu\n"
        text += "• Choose your preferred method:\n"
        text += "  - Phone Number: Enter your Telegram phone number\n"
        text += "  - Session String: Import an existing session\n"
        text += "• Follow the authentication steps:\n"
        text += "  - Enter verification code sent to your Telegram\n"
        text += "  - Enter 2FA password if enabled\n"
        text += "• Wait for session confirmation\n\n"
        
        text += "📥 **2. Set Source Channel**\n"
        text += "• Click 'Set Source' in the main menu\n"
        text += "• Send one of these formats:\n"
        text += "  - Channel username: `@channelname`\n"
        text += "  - Channel link: `https://t.me/channelname`\n"
        text += "  - Channel ID: `-1001234567890`\n"
        text += "  - Invitation link: `https://t.me/+AbCdEfGhIj`\n"
        text += "  - Message link: `https://t.me/c/123456789/1`\n"
        text += "• For private channels:\n"
        text += "  - Use message links for best results\n"
        text += "  - Make sure you're a member of the channel\n"
        text += "  - Your account must have access to the messages\n\n"
        
        text += "📤 **3. Set Target Channel**\n"
        text += "• Click 'Set Target' in the main menu\n"
        text += "• Send target channel information:\n"
        text += "  - Channel username: `@channelname`\n"
        text += "  - Channel link: `https://t.me/channelname`\n"
        text += "  - Channel ID: `-1001234567890`\n"
        text += "  - Invitation link: `https://t.me/+AbCdEfGhIj`\n"
        text += "• Important requirements:\n"
        text += "  - You must be an admin in the target channel\n"
        text += "  - Your account must have posting permissions\n"
        text += "  - Channel must allow message posting\n\n"
        
        text += "📊 **4. Set Message Range**\n"
        text += "• Click 'Set Range' in the main menu\n"
        text += "• Choose from these options:\n"
        text += "  - Copy all: Copies entire channel\n"
        text += "  - Set start: Specify first message\n"
        text += "  - Set end: Specify last message\n"
        text += "• Range formats:\n"
        text += "  - Single message: `https://t.me/c/123456789/1`\n"
        text += "  - Message range: `https://t.me/c/123456789/1-10`\n"
        text += "  - ID range: `1-100`\n"
        text += "• Tips for range selection:\n"
        text += "  - Use message links for precise selection\n"
        text += "  - Check message IDs in the source channel\n"
        text += "  - Maximum range is 1000 messages\n\n"
        
        text += "🚀 **5. Start Copying**\n"
        text += "• Click 'Start Copying' when ready\n"
        text += "• The bot will show:\n"
        text += "  - Total messages to copy\n"
        text += "  - Real-time progress\n"
        text += "  - Copy speed and time remaining\n"
        text += "  - Success/failure count\n"
        text += "• During copying:\n"
        text += "  - Don't delete the progress message\n"
        text += "  - Keep your session active\n"
        text += "  - Wait for completion message\n\n"
        
        text += "📩 **Quick Copy to Me**\n"
        text += "• Click 'Copy Message(s) to Me'\n"
        text += "• Send message link or range:\n"
        text += "  - Single message: `https://t.me/c/123456789/1`\n"
        text += "  - Message range: `https://t.me/c/123456789/1-10`\n"
        text += "  - Public channel: `https://t.me/channelname/1`\n"
        text += "• Features:\n"
        text += "  - Copies directly to your chat\n"
        text += "  - Works with private channels\n"
        text += "  - Supports message ranges\n\n"
        
        text += "💡 **Tips & Tricks**\n"
        text += "• Session Management:\n"
        text += "  - Keep your session active\n"
        text += "  - Delete session if you have issues\n"
        text += "  - Create new session if needed\n"
        text += "• Channel Access:\n"
        text += "  - Join channels before copying\n"
        text += "  - Use message links for private channels\n"
        text += "  - Check your admin permissions\n"
        text += "• Performance:\n"
        text += "  - Check your message limits in 'My Stats'\n"
        text += "  - Upgrade to VIP for unlimited copying\n"
        text += "  - Keep your session active for faster copying\n"
        text += "• Troubleshooting:\n"
        text += "  - If copying fails, try smaller ranges\n"
        text += "  - Check your account's message limits\n"
        text += "  - Ensure you have proper permissions"
        
        keyboard = [
            [InlineKeyboardButton("🇦🇪 العربية", callback_data="how_to_use_ar")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )

    async def show_how_to_use_arabic(self, callback_query: CallbackQuery):
        """Show comprehensive guide in Egyptian Arabic"""
        text = "📖 **ازاي تستخدم البوت**\n\n"
        
        text += "🤖 **البوت بيعمل ايه بالظبط**\n"
        text += "البوت ده بيساعدك تنقل الرسائل من قناة تيليجرام لقناة تانية. ممتاز لـ:\n"
        text += "• نقل المحتوى من القنوات الخاصة لقناتك\n"
        text += "• عمل نسخة احتياطية من الرسائل المهمة والوسائط\n"
        text += "• نقل المحتوى بين القنوات\n"
        text += "• حفظ الرسائل مع كل الوسائط (صور، فيديو، ملفات، الخ)\n"
        text += "• نسخ الرسائل مباشرة في الشات بتاعك\n\n"
        
        text += "🔑 **1. إنشاء Session**\n"
        text += "• اضغط على 'Create Session' في القائمة الرئيسية\n"
        text += "• اختار الطريقة اللي انت عايزها:\n"
        text += "  - Phone Number: هات رقم تيليجرام بتاعك\n"
        text += "  - Session String: استورد session موجود\n"
        text += "• اتبع الخطوات:\n"
        text += "  - هات الكود اللي هيجيلك على تيليجرام\n"
        text += "  - لو عندك 2FA هات الباسورد بتاعه\n"
        text += "• استنى تأكيد الـ session\n\n"
        
        text += "📥 **2. تعيين Source Channel**\n"
        text += "• اضغط على 'Set Source' في القائمة الرئيسية\n"
        text += "• ابعت واحد من دول:\n"
        text += "  - Channel username: `@channelname`\n"
        text += "  - Channel link: `https://t.me/channelname`\n"
        text += "  - Channel ID: `-1001234567890`\n"
        text += "  - Invitation link: `https://t.me/+AbCdEfGhIj`\n"
        text += "  - Message link: `https://t.me/c/123456789/1`\n"
        text += "• للقنوات الخاصة:\n"
        text += "  - استخدم روابط الرسائل عشان أفضل نتيجة\n"
        text += "  - تأكد إنك عضو في القناة\n"
        text += "  - تأكد إن عندك صلاحية الوصول للرسائل\n\n"
        
        text += "📤 **3. تعيين Target Channel**\n"
        text += "• اضغط على 'Set Target' في القائمة الرئيسية\n"
        text += "• ابعت معلومات القناة الهدف:\n"
        text += "  - Channel username: `@channelname`\n"
        text += "  - Channel link: `https://t.me/channelname`\n"
        text += "  - Channel ID: `-1001234567890`\n"
        text += "  - Invitation link: `https://t.me/+AbCdEfGhIj`\n"
        text += "• المطلوب:\n"
        text += "  - لازم تكون admin في القناة الهدف\n"
        text += "  - لازم عندك صلاحية النشر\n"
        text += "  - القناة لازم تسمح بالنشر\n\n"
        
        text += "📊 **4. تعيين Message Range**\n"
        text += "• اضغط على 'Set Range' في القائمة الرئيسية\n"
        text += "• اختار من دول:\n"
        text += "  - Copy all: ينسخ القناة كلها\n"
        text += "  - Set start: حدد أول رسالة\n"
        text += "  - Set end: حدد آخر رسالة\n"
        text += "• أشكال النطاق:\n"
        text += "  - رسالة واحدة: `https://t.me/c/123456789/1`\n"
        text += "  - نطاق رسائل: `https://t.me/c/123456789/1-10`\n"
        text += "  - نطاق معرفات: `1-100`\n"
        text += "• نصائح:\n"
        text += "  - استخدم روابط الرسائل عشان اختيار دقيق\n"
        text += "  - شوف معرفات الرسائل في القناة المصدر\n"
        text += "  - أقصى نطاق هو 1000 رسالة\n\n"
        
        text += "🚀 **5. بدء النسخ**\n"
        text += "• اضغط على 'Start Copying' لما تكون جاهز\n"
        text += "• البوت هيعرض:\n"
        text += "  - عدد الرسائل اللي هتتنسخ\n"
        text += "  - التقدم في الوقت الفعلي\n"
        text += "  - سرعة النسخ والوقت المتبقي\n"
        text += "  - عدد النجاح/الفشل\n"
        text += "• أثناء النسخ:\n"
        text += "  - متحذفش رسالة التقدم\n"
        text += "  - خلي الـ session شغال\n"
        text += "  - استنى رسالة الإكمال\n\n"
        
        text += "📩 **نسخ سريع**\n"
        text += "• اضغط على 'Copy Message(s) to Me'\n"
        text += "• ابعت رابط الرسالة أو النطاق:\n"
        text += "  - رسالة واحدة: `https://t.me/c/123456789/1`\n"
        text += "  - نطاق رسائل: `https://t.me/c/123456789/1-10`\n"
        text += "  - قناة عامة: `https://t.me/channelname/1`\n"
        text += "• المميزات:\n"
        text += "  - ينسخ مباشرة في الشات بتاعك\n"
        text += "  - شغال مع القنوات الخاصة\n"
        text += "  - يدعم نطاقات الرسائل\n\n"
        
        text += "💡 **نصائح وحيل**\n"
        text += "• إدارة الـ Session:\n"
        text += "  - خلي الـ session شغال\n"
        text += "  - احذف الـ session لو في مشكلة\n"
        text += "  - اعمل session جديد لو محتاج\n"
        text += "• الوصول للقنوات:\n"
        text += "  - انضم للقنوات قبل النسخ\n"
        text += "  - استخدم روابط الرسائل للقنوات الخاصة\n"
        text += "  - تأكد من صلاحيات الـ admin\n"
        text += "• الأداء:\n"
        text += "  - شوف حدود الرسائل في 'My Stats'\n"
        text += "  - اترقى لـ VIP عشان نسخ غير محدود\n"
        text += "  - خلي الـ session شغال عشان نسخ أسرع\n"
        text += "• حل المشاكل:\n"
        text += "  - لو النسخ فشل، جرب نطاقات أصغر\n"
        text += "  - شوف حدود رسائل حسابك\n"
        text += "  - تأكد إن عندك الصلاحيات المطلوبة"
        
        keyboard = [
            [InlineKeyboardButton("🇬🇧 English", callback_data="how_to_use")],
            [InlineKeyboardButton("🔙 Back", callback_data="main_menu")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await callback_query.edit_message_text(text, reply_markup=reply_markup,  )
