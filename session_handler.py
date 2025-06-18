import os
import json
import time
import asyncio
import logging
from typing import Dict, Optional
from pyrogram import Client
from pyrogram.errors import SessionPasswordNeeded, PhoneCodeInvalid, PhoneCodeExpired
from config import API_ID, API_HASH

logger = logging.getLogger(__name__)

class SessionHandler:
    def __init__(self):
        self.sessions_file = "user_sessions.json"
        self.user_sessions = {}
        self.active_clients = {}
        self.load_sessions()
        self._cleanup_old_sessions()

    def _cleanup_old_sessions(self):
        """Clean up old session files"""
        try:
            old_files = [
                "copier_bot.session", 
                "copier_bot.session-journal", 
                "session.json",
                "telegram_copier_bot.session",
                "telegram_copier_bot.session-journal"
            ]
            
            for file in old_files:
                if os.path.exists(file):
                    try:
                        os.remove(file)
                        logger.info(f"Removed old session file: {file}")
                    except Exception as e:
                        logger.warning(f"Could not remove old session file {file}: {e}")
        except Exception as e:
            logger.error(f"Error during session cleanup: {e}")

    def load_sessions(self):
        """Load user sessions from JSON file"""
        try:
            if os.path.exists(self.sessions_file):
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.user_sessions = {int(k): v for k, v in data.items()}
                logger.info(f"Loaded {len(self.user_sessions)} user sessions")
            else:
                self.user_sessions = {}
                self.save_sessions()
        except Exception as e:
            logger.error(f"Error loading sessions: {e}")
            self.user_sessions = {}
            self.save_sessions()

    def save_sessions(self):
        """Save user sessions to JSON file"""
        try:
            # Create backup
            if os.path.exists(self.sessions_file):
                backup_file = f"{self.sessions_file}.backup"
                try:
                    os.rename(self.sessions_file, backup_file)
                except:
                    pass
            
            # Write new sessions
            temp_file = f"{self.sessions_file}.tmp"
            with open(temp_file, 'w', encoding='utf-8') as f:
                data = {str(k): v for k, v in self.user_sessions.items()}
                json.dump(data, f, indent=4, ensure_ascii=False)
            
            # Atomic replace
            os.rename(temp_file, self.sessions_file)
            
            # Remove backup if successful
            backup_file = f"{self.sessions_file}.backup"
            if os.path.exists(backup_file):
                try:
                    os.remove(backup_file)
                except:
                    pass
                    
            logger.debug("Sessions saved successfully")
        except Exception as e:
            logger.error(f"Error saving sessions: {e}")
            # Try to restore backup
            backup_file = f"{self.sessions_file}.backup"
            if os.path.exists(backup_file):
                try:
                    os.rename(backup_file, self.sessions_file)
                    logger.info("Restored session backup")
                except:
                    pass
            # Clean up temp file
            temp_file = f"{self.sessions_file}.tmp"
            if os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except:
                    pass

    def get_user_session(self, user_id: int) -> Dict:
        """Get or create user session"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {
                'state': 'main_menu',
                'source_channel': None,
                'source_title': None,
                'target_channel': None,
                'target_title': None,
                'start_msg_id': None,
                'end_msg_id': None,
                'session_string': None,
                'phone': None,
                'phone_code_hash': None,
                'last_active': time.time(),
                'created_at': time.time()
            }
            self.save_sessions()
        else:
            # Update last active time
            self.user_sessions[user_id]['last_active'] = time.time()
            
        return self.user_sessions[user_id]

    def update_user_session(self, user_id: int, data: Dict):
        """Update user session data"""
        if user_id not in self.user_sessions:
            self.user_sessions[user_id] = {}
        
        self.user_sessions[user_id].update(data)
        self.user_sessions[user_id]['last_active'] = time.time()
        self.save_sessions()
        logger.debug(f"Updated session for user {user_id}: {list(data.keys())}")

    async def clear_user_session(self, user_id: int):
        """Clear user session completely"""
        try:
            # Disconnect client if exists
            if user_id in self.active_clients:
                try:
                    client = self.active_clients[user_id]
                    if client.is_connected:
                        await client.stop()
                except Exception as e:
                    logger.warning(f"Error disconnecting client for user {user_id}: {e}")
                finally:
                    del self.active_clients[user_id]
            
            # Clear session data
            if user_id in self.user_sessions:
                del self.user_sessions[user_id]
                self.save_sessions()
                logger.info(f"Cleared session for user {user_id}")
            
            # Clean up any session files
            session_files = [
                f"user_{user_id}.session",
                f"user_{user_id}.session-journal",
                f"temp_{user_id}.session",
                f"temp_{user_id}.session-journal"
            ]
            
            for session_file in session_files:
                if os.path.exists(session_file):
                    try:
                        os.remove(session_file)
                        logger.debug(f"Removed session file: {session_file}")
                    except Exception as e:
                        logger.warning(f"Could not remove session file {session_file}: {e}")
                        
        except Exception as e:
            logger.error(f"Error clearing session for user {user_id}: {e}")

    async def create_user_client(self, user_id: int, session_string: Optional[str] = None) -> Optional[Client]:
        """Create a Pyrogram client for user"""
        try:
            # Clean up existing client
            if user_id in self.active_clients:
                try:
                    await self.active_clients[user_id].stop()
                except:
                    pass
                del self.active_clients[user_id]
            
            if session_string:
                client = Client(
                    f"user_{user_id}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    session_string=session_string,
                    workdir="."
                )
            else:
                client = Client(
                    f"user_{user_id}",
                    api_id=API_ID,
                    api_hash=API_HASH,
                    workdir="."
                )
            
            await client.start()
            
            # Test connection
            me = await client.get_me()
            logger.info(f"Created client for user {user_id} (Telegram: {me.first_name} {me.last_name or ''})")
            
            self.active_clients[user_id] = client
            return client
            
        except Exception as e:
            logger.error(f"Error creating client for user {user_id}: {e}")
            return None

    async def get_user_client(self, user_id: int) -> Optional[Client]:
        """Get existing user client or create new one"""
        # Check if we have an active client
        if user_id in self.active_clients:
            try:
                client = self.active_clients[user_id]
                # Test if client is still connected
                await client.get_me()
                return client
            except Exception as e:
                logger.warning(f"Client for user {user_id} is disconnected: {e}")
                # Remove disconnected client
                try:
                    await self.active_clients[user_id].stop()
                except:
                    pass
                del self.active_clients[user_id]
        
        # Try to create client from saved session string
        session = self.get_user_session(user_id)
        session_string = session.get('session_string')
        
        if session_string:
            logger.info(f"Attempting to restore client for user {user_id} from session string")
            return await self.create_user_client(user_id, session_string)
        
        logger.debug(f"No session available for user {user_id}")
        return None

    async def start_phone_verification(self, user_id: int, phone: str) -> tuple[bool, str]:
        """Start phone verification process"""
        try:
            # Clean up any existing temp client
            temp_client_key = f"temp_{user_id}"
            
            client = Client(
                temp_client_key,
                api_id=API_ID,
                api_hash=API_HASH,
                phone_number=phone,
                workdir="."
            )
            
            await client.connect()
            sent = await client.send_code(phone)
            
            # Store verification data
            self.update_user_session(user_id, {
                'phone': phone,
                'phone_code_hash': sent.phone_code_hash,
                'temp_client': client,
                'state': 'awaiting_code'
            })
            
            logger.info(f"Verification code sent to {phone} for user {user_id}")
            return True, "Verification code sent successfully!"
            
        except Exception as e:
            logger.error(f"Error starting phone verification for user {user_id}: {e}")
            return False, f"Error: {str(e)}"

    async def verify_code(self, user_id: int, code: str) -> tuple[bool, str]:
        """Verify phone code and create session"""
        try:
            session = self.get_user_session(user_id)
            temp_client = session.get('temp_client')
            
            if not temp_client:
                return False, "Session expired. Please start over."
            
            # Sign in with code
            await temp_client.sign_in(
                phone_number=session['phone'],
                phone_code_hash=session['phone_code_hash'],
                phone_code=code
            )
            
            # Get session string
            session_string = await temp_client.export_session_string()
            
            # Save session string
            self.update_user_session(user_id, {
                'session_string': session_string,
                'state': 'main_menu'
            })
            
            # Move client to active clients
            self.active_clients[user_id] = temp_client
            
            # Clean up temp data
            session.pop('temp_client', None)
            session.pop('phone', None)
            session.pop('phone_code_hash', None)
            
            logger.info(f"Session created successfully for user {user_id}")
            return True, "Session created successfully!"
            
        except SessionPasswordNeeded:
            self.update_user_session(user_id, {'state': 'awaiting_password'})
            return False, "Two-factor authentication enabled. Please send your password."
        except PhoneCodeInvalid:
            return False, "Invalid verification code. Please try again."
        except PhoneCodeExpired:
            return False, "Verification code expired. Please start over."
        except Exception as e:
            logger.error(f"Error verifying code for user {user_id}: {e}")
            return False, f"Error: {str(e)}"

    async def verify_password(self, user_id: int, password: str) -> tuple[bool, str]:
        """Verify 2FA password"""
        try:
            session = self.get_user_session(user_id)
            temp_client = session.get('temp_client')
            
            if not temp_client:
                return False, "Session expired. Please start over."
            
            # Check password
            await temp_client.check_password(password)
            
            # Get session string
            session_string = await temp_client.export_session_string()
            
            # Save session string
            self.update_user_session(user_id, {
                'session_string': session_string,
                'state': 'main_menu'
            })
            
            # Move client to active clients
            self.active_clients[user_id] = temp_client
            
            # Clean up temp data
            session.pop('temp_client', None)
            session.pop('phone', None)
            session.pop('phone_code_hash', None)
            
            logger.info(f"2FA verified and session created for user {user_id}")
            return True, "Session created successfully!"
            
        except Exception as e:
            logger.error(f"Error verifying password for user {user_id}: {e}")
            return False, f"Invalid password. Please try again."

    async def disconnect_all(self):
        """Disconnect all active clients"""
        for user_id, client in list(self.active_clients.items()):
            try:
                await client.stop()
                logger.info(f"Disconnected client for user {user_id}")
            except Exception as e:
                logger.warning(f"Error disconnecting client for user {user_id}: {e}")
        self.active_clients.clear()
