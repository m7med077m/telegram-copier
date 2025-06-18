
import re
import logging
from typing import Tuple, Optional

logger = logging.getLogger(__name__)

def validate_phone_number(phone: str) -> Tuple[bool, str]:
    """Validate phone number format"""
    phone = phone.strip().replace(" ", "").replace("-", "")
    
    if not phone.startswith('+'):
        return False, "Phone number must start with +"
    
    if not phone[1:].isdigit():
        return False, "Phone number must contain only digits after +"
    
    if len(phone) < 10 or len(phone) > 16:
        return False, "Phone number length must be between 10-16 characters"
    
    return True, phone

def parse_message_range(range_str: str) -> Tuple[bool, Optional[int], Optional[int], str]:
    """Parse message range string"""
    try:
        range_str = range_str.strip()
        
        if '-' not in range_str:
            return False, None, None, "Please use format: start_id-end_id"
        
        parts = range_str.split('-', 1)
        if len(parts) != 2:
            return False, None, None, "Invalid format. Use: start_id-end_id"
        
        try:
            start_id = int(parts[0].strip())
            end_id = int(parts[1].strip())
        except ValueError:
            return False, None, None, "Message IDs must be numbers"
        
        if start_id <= 0 or end_id <= 0:
            return False, None, None, "Message IDs must be positive"
        
        if start_id > end_id:
            start_id, end_id = end_id, start_id
        
        return True, start_id, end_id, ""
        
    except Exception as e:
        logger.error(f"Error parsing message range: {e}")
        return False, None, None, "Error parsing range"

def format_speed(bytes_per_second: int) -> str:
    """Format speed in human readable format"""
    if bytes_per_second >= 1024 * 1024:
        return f"{bytes_per_second / (1024 * 1024):.1f} MB/s"
    elif bytes_per_second >= 1024:
        return f"{bytes_per_second / 1024:.1f} KB/s"
    else:
        return f"{bytes_per_second} B/s"

def format_time(seconds: int) -> str:
    """Format time in human readable format"""
    if seconds >= 3600:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours}h {minutes}m"
    elif seconds >= 60:
        minutes = seconds // 60
        seconds = seconds % 60
        return f"{minutes}m {seconds}s"
    else:
        return f"{seconds}s"

def clean_text(text: str) -> str:
    """Clean text for safe display"""
    if not text:
        return ""
    
    # Remove or replace problematic characters
    text = text.replace('\n', ' ').replace('\r', ' ')
    text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space
    text = text.strip()
    
    # Limit length
    if len(text) > 100:
        text = text[:97] + "..."
    
    return text
