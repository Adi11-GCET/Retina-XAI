import os
import re
import time
import hashlib
import secrets
import logging
import urllib.request
import urllib.parse
import json

logger = logging.getLogger('retina_xai.otp')

# Default demonstration OTP code for evaluation/development only
DEMO_OTP = "652070"
OTP_EXPIRY_SECONDS = 300       # 5 minutes
RESEND_COOLDOWN_SECONDS = 60   # 60 seconds cooldown between resends
MAX_VERIFY_ATTEMPTS = 5        # Lock OTP after 5 failed attempts
MAX_SEND_PER_WINDOW = 5        # Max 5 OTP requests per phone in window
SEND_WINDOW_SECONDS = 900      # 15 minutes window
MAX_IP_SEND_PER_WINDOW = 10    # Max 10 OTP requests per IP in window
IP_SEND_WINDOW_SECONDS = 900   # 15 minutes window

# -------------------------------------------------------------------
# Mode & Environment Helpers
# -------------------------------------------------------------------

def is_production_mode() -> bool:
    """
    Returns True if running in production mode.
    Triggered when:
      - AUTH_MODE=production
      - FLASK_ENV=production
      - DEMO_OTP_ENABLED=false
    """
    auth_mode = os.environ.get('AUTH_MODE', '').strip().lower()
    flask_env = os.environ.get('FLASK_ENV', '').strip().lower()
    demo_otp = os.environ.get('DEMO_OTP_ENABLED', '').strip().lower()

    if auth_mode == 'production' or flask_env == 'production':
        return True
    if demo_otp in ('false', '0', 'no'):
        return True
    return False

def is_demo_otp_allowed() -> bool:
    """
    Returns True only if the universal/demo OTP code (652070) is permitted.
    STRICT RULE: In production mode, universal demo OTP is NEVER allowed.
    In development/testing, it is allowed unless DEMO_OTP_ENABLED is explicitly false.
    """
    demo_otp = os.environ.get('DEMO_OTP_ENABLED', '').strip().lower()
    if demo_otp in ('false', '0', 'no'):
        return False
    if is_production_mode():
        return False
    return True

def normalize_phone_number(raw_phone: str) -> str:
    """
    Normalizes input phone number to standard +91XXXXXXXXXX format.
    Handles inputs like: '9876543210', '+91 98765 43210', '09876543210', etc.
    Returns normalized string or raises ValueError.
    """
    if not raw_phone:
        raise ValueError("Mobile number is required.")
    
    cleaned = re.sub(r'[\s\-\(\)]', '', str(raw_phone).strip())
    
    # Check Indian formats
    if re.match(r'^\+91[6-9]\d{9}$', cleaned):
        return cleaned
    elif re.match(r'^91[6-9]\d{9}$', cleaned):
        return f"+{cleaned}"
    elif re.match(r'^0[6-9]\d{9}$', cleaned):
        return f"+91{cleaned[1:]}"
    elif re.match(r'^[6-9]\d{9}$', cleaned):
        return f"+91{cleaned}"
    
    # General international E.164 format fallback
    if re.match(r'^\+[1-9]\d{7,14}$', cleaned):
        return cleaned

    raise ValueError("Please enter a valid 10-digit mobile number.")

def hash_otp(otp_code: str, salt: str = "") -> str:
    """Creates a SHA-256 hash of the OTP for secure temporary memory storage."""
    payload = f"{salt}:{otp_code}".encode('utf-8')
    return hashlib.sha256(payload).hexdigest()

# -------------------------------------------------------------------
# Provider Abstraction
# -------------------------------------------------------------------

class BaseOtpProvider:
    """Abstract base class for SMS OTP dispatch gateways."""
    def send_otp(self, phone_number: str, otp_code: str) -> tuple[bool, str]:
        raise NotImplementedError

    def is_configured(self) -> bool:
        return False

class UnavailableOtpProvider(BaseOtpProvider):
    """
    Fail-safe provider used in production mode when SMS credentials are not configured.
    Never fakes real SMS delivery and strictly fails safe.
    """
    def __init__(self, reason: str = "OTP service is currently unavailable. Please try again later."):
        self.reason = reason

    def send_otp(self, phone_number: str, otp_code: str) -> tuple[bool, str]:
        logger.warning(
            f"SMS dispatch blocked in production: Credentials unconfigured for target phone {phone_number[-4:]}."
        )
        return False, self.reason

    def is_configured(self) -> bool:
        return False

class MockOtpProvider(BaseOtpProvider):
    """
    Development and Demonstration OTP provider.
    Active ONLY in development/testing mode when external SMS credentials are not set.
    """
    def send_otp(self, phone_number: str, otp_code: str) -> tuple[bool, str]:
        # Never fake real SMS delivery: explicitly display simulated nature
        print(f"\n[DEVELOPMENT SIMULATED OTP] Mobile: {phone_number} | Code: {otp_code} (Universal Demo: {DEMO_OTP})\n", flush=True)
        return True, f"[SIMULATION - DEVELOPMENT MODE] Verification OTP is {otp_code}. External SMS gateway is not configured on this server."

    def is_configured(self) -> bool:
        return True

class Fast2SmsOtpProvider(BaseOtpProvider):
    """
    Fast2SMS Indian Gateway Integration.
    Reads SMS_API_KEY (or OTP_API_KEY) and SMS_SENDER_ID (or OTP_SENDER_ID).
    """
    def __init__(self):
        self.api_key = (os.environ.get('SMS_API_KEY') or os.environ.get('OTP_API_KEY') or '').strip()
        self.sender_id = (os.environ.get('SMS_SENDER_ID') or os.environ.get('OTP_SENDER_ID') or 'DRSHTI').strip()

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def send_otp(self, phone_number: str, otp_code: str) -> tuple[bool, str]:
        if not self.is_configured():
            return False, "Fast2SMS provider API key is not configured on server."
        try:
            # Fast2SMS expects 10-digit Indian number without country code
            clean_10 = phone_number[-10:]
            url = "https://www.fast2sms.com/dev/bulkV2"
            payload = json.dumps({
                "variables_values": otp_code,
                "route": "otp",
                "numbers": clean_10
            }).encode('utf-8')
            req = urllib.request.Request(url, data=payload, headers={
                'authorization': self.api_key,
                'Content-Type': 'application/json'
            })
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('return'):
                    return True, "OTP successfully dispatched via Fast2SMS."
                err_msg = data.get('message', 'Fast2SMS delivery failure.')
                if isinstance(err_msg, list):
                    err_msg = ", ".join(err_msg)
                return False, f"SMS delivery error: {err_msg}"
        except Exception as e:
            logger.error(f"Fast2SMS delivery exception: {e}")
            return False, "SMS gateway temporarily unavailable. Please retry shortly."

class TwilioOtpProvider(BaseOtpProvider):
    """
    Twilio SMS Gateway Integration.
    Reads SMS_API_KEY/TWILIO_ACCOUNT_SID, SMS_API_SECRET/TWILIO_AUTH_TOKEN, and SMS_SENDER_ID/TWILIO_PHONE_NUMBER.
    """
    def __init__(self):
        self.account_sid = (os.environ.get('SMS_API_KEY') or os.environ.get('OTP_API_KEY') or os.environ.get('TWILIO_ACCOUNT_SID') or '').strip()
        self.auth_token = (os.environ.get('SMS_API_SECRET') or os.environ.get('OTP_API_SECRET') or os.environ.get('TWILIO_AUTH_TOKEN') or '').strip()
        self.from_number = (os.environ.get('SMS_SENDER_ID') or os.environ.get('OTP_SENDER_ID') or os.environ.get('TWILIO_PHONE_NUMBER') or '').strip()

    def is_configured(self) -> bool:
        return bool(self.account_sid and self.auth_token and self.from_number)

    def send_otp(self, phone_number: str, otp_code: str) -> tuple[bool, str]:
        if not self.is_configured():
            return False, "Twilio SMS provider is not fully configured on server."
        try:
            url = f"https://api.twilio.com/2010-04-01/Accounts/{self.account_sid}/Messages.json"
            data = urllib.parse.urlencode({
                'To': phone_number,
                'From': self.from_number,
                'Body': f"Your DrishtiAI verification code is {otp_code}. Valid for 5 minutes. Do not share this code with anyone."
            }).encode('utf-8')

            req = urllib.request.Request(url, data=data)
            auth_str = f"{self.account_sid}:{self.auth_token}".encode('utf-8')
            import base64
            req.add_header("Authorization", f"Basic {base64.b64encode(auth_str).decode('ascii')}")

            with urllib.request.urlopen(req, timeout=10) as resp:
                if resp.status in (200, 201):
                    return True, "OTP successfully dispatched via Twilio."
                return False, f"Twilio rejected message dispatch (HTTP {resp.status})."
        except Exception as e:
            logger.error(f"Twilio SMS delivery exception: {e}")
            return False, "SMS gateway temporarily unavailable. Please retry shortly."

class Msg91OtpProvider(BaseOtpProvider):
    """
    MSG91 Indian SMS Gateway Integration.
    Reads SMS_API_KEY (or MSG91_AUTH_KEY) and SMS_TEMPLATE_ID (or MSG91_TEMPLATE_ID).
    """
    def __init__(self):
        self.auth_key = (os.environ.get('SMS_API_KEY') or os.environ.get('MSG91_AUTH_KEY') or '').strip()
        self.template_id = (os.environ.get('SMS_TEMPLATE_ID') or os.environ.get('MSG91_TEMPLATE_ID') or '').strip()

    def is_configured(self) -> bool:
        return bool(self.auth_key and self.template_id)

    def send_otp(self, phone_number: str, otp_code: str) -> tuple[bool, str]:
        if not self.is_configured():
            return False, "MSG91 provider is not fully configured (missing API key or Template ID)."
        try:
            clean_phone = phone_number.lstrip('+')
            url = f"https://control.msg91.com/api/v5/otp?template_id={urllib.parse.quote(self.template_id)}&mobile={urllib.parse.quote(clean_phone)}&otp={urllib.parse.quote(otp_code)}"
            req = urllib.request.Request(url, headers={
                'authkey': self.auth_key,
                'Content-Type': 'application/JSON'
            }, method='POST')
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data.get('type') == 'success':
                    return True, "OTP successfully dispatched via MSG91."
                return False, data.get('message', 'MSG91 delivery failure.')
        except Exception as e:
            logger.error(f"MSG91 SMS delivery exception: {e}")
            return False, "SMS gateway temporarily unavailable. Please retry shortly."

def get_otp_provider() -> BaseOtpProvider:
    """
    Selects the configured SMS provider.
    FAIL-SAFE RULE: In PRODUCTION mode, if credentials are unconfigured,
    returns UnavailableOtpProvider (never falls back to MockOtpProvider or demo codes).
    In DEVELOPMENT mode, falls back to MockOtpProvider.
    """
    provider_name = (os.environ.get('SMS_PROVIDER') or os.environ.get('OTP_PROVIDER') or '').strip().lower()
    prod = is_production_mode()

    if provider_name == 'twilio':
        prov = TwilioOtpProvider()
        if not prov.is_configured() and prod:
            return UnavailableOtpProvider("OTP service is currently unavailable. Please try again later.")
        return prov

    elif provider_name == 'fast2sms':
        prov = Fast2SmsOtpProvider()
        if not prov.is_configured() and prod:
            return UnavailableOtpProvider("OTP service is currently unavailable. Please try again later.")
        return prov

    elif provider_name == 'msg91':
        prov = Msg91OtpProvider()
        if not prov.is_configured() and prod:
            return UnavailableOtpProvider("OTP service is currently unavailable. Please try again later.")
        return prov

    # If provider is explicitly 'mock':
    if provider_name == 'mock':
        if prod:
            return UnavailableOtpProvider("OTP service is currently unavailable. Please try again later.")
        return MockOtpProvider()

    # If provider is unspecified:
    if prod:
        return UnavailableOtpProvider("OTP service is currently unavailable. Please try again later.")

    return MockOtpProvider()

# -------------------------------------------------------------------
# Secure In-Memory OTP Store & Multi-Level Rate Limiter
# -------------------------------------------------------------------

class OtpSessionStore:
    def __init__(self):
        # phone -> {
        #   'hashed_otp': str,
        #   'created_at': float,
        #   'attempts': int,
        #   'last_sent_at': float,
        #   'send_history': list[float]
        # }
        self._store: dict[str, dict] = {}
        # ip_address -> list of timestamps
        self._ip_store: dict[str, list[float]] = {}

    def _cleanup_expired(self):
        now = time.time()
        expired_phones = [p for p, data in self._store.items() if now - data.get('created_at', 0) > 3600]
        for p in expired_phones:
            self._store.pop(p, None)

        expired_ips = []
        for ip, history in self._ip_store.items():
            valid_history = [t for t in history if now - t < IP_SEND_WINDOW_SECONDS]
            if not valid_history:
                expired_ips.append(ip)
            else:
                self._ip_store[ip] = valid_history
        for ip in expired_ips:
            self._ip_store.pop(ip, None)

    def can_send_from_ip(self, ip_address: str) -> tuple[bool, str]:
        """Checks IP-level abuse prevention rate limiting."""
        if not ip_address:
            return True, ""
        now = time.time()
        history = [t for t in self._ip_store.get(ip_address, []) if now - t < IP_SEND_WINDOW_SECONDS]
        if len(history) >= MAX_IP_SEND_PER_WINDOW:
            return False, "Too many requests from this network. Please try again after 15 minutes."
        return True, ""

    def can_send_otp(self, phone_number: str) -> tuple[bool, str, int]:
        """
        Checks rate limiting and resend cooldown for a specific phone number.
        Returns: (can_send: bool, reason: str, remaining_cooldown_seconds: int)
        """
        self._cleanup_expired()
        now = time.time()
        record = self._store.get(phone_number)

        if not record:
            return True, "", 0

        # Cooldown check (60 seconds)
        elapsed_since_last = now - record.get('last_sent_at', 0)
        if elapsed_since_last < RESEND_COOLDOWN_SECONDS:
            remaining = int(RESEND_COOLDOWN_SECONDS - elapsed_since_last)
            return False, f"Please wait {remaining} seconds before requesting a new OTP.", remaining

        # Window abuse limit (5 per 15 minutes)
        recent_sends = [t for t in record.get('send_history', []) if now - t < SEND_WINDOW_SECONDS]
        if len(recent_sends) >= MAX_SEND_PER_WINDOW:
            return False, "Too many OTP requests for this number. Please try again after 15 minutes.", 0

        return True, "", 0

    def create_and_send_otp(self, phone_number: str, ip_address: str = None) -> tuple[bool, str, str]:
        """
        Generates 6-digit cryptographically secure OTP, records state, and invokes provider.
        Invalidates any previously active OTP for this phone.
        Enforces both IP rate limit and phone number cooldown/rate limit.
        Returns: (success: bool, message: str, generated_code_for_demo: str)
        """
        self._cleanup_expired()

        # 1. IP Rate Limiting
        if ip_address:
            can_ip, ip_reason = self.can_send_from_ip(ip_address)
            if not can_ip:
                return False, ip_reason, ""

        # 2. Phone Rate Limiting & Cooldown
        can_send, reason, _ = self.can_send_otp(phone_number)
        if not can_send:
            return False, reason, ""

        now = time.time()
        # Generate 6-digit cryptographically secure code
        otp_code = str(secrets.randbelow(900000) + 100000)
        hashed = hash_otp(otp_code, salt=phone_number)

        # 3. Provider Dispatch
        provider = get_otp_provider()
        success, prov_msg = provider.send_otp(phone_number, otp_code)

        if not success:
            return False, prov_msg, ""

        # 4. Record State & Invalidate Any Previous OTP
        record = self._store.get(phone_number, {'send_history': []})
        recent_sends = [t for t in record.get('send_history', []) if now - t < SEND_WINDOW_SECONDS]
        recent_sends.append(now)

        self._store[phone_number] = {
            'hashed_otp': hashed,
            'created_at': now,
            'attempts': 0,
            'last_sent_at': now,
            'send_history': recent_sends
        }

        # Record IP send
        if ip_address:
            ip_history = [t for t in self._ip_store.get(ip_address, []) if now - t < IP_SEND_WINDOW_SECONDS]
            ip_history.append(now)
            self._ip_store[ip_address] = ip_history

        # In development simulation mode only, return demo code
        demo_code_return = otp_code if (isinstance(provider, MockOtpProvider) and is_demo_otp_allowed()) else ""
        return True, "Verification OTP has been sent successfully.", demo_code_return

    def verify_otp(self, phone_number: str, entered_otp: str) -> tuple[bool, str]:
        """
        Verifies entered OTP against securely stored hash.
        - Single use burn on success
        - Max 5 failed attempts locks OTP
        - 5-minute expiry
        - DEMO_OTP (652070) is ONLY accepted if is_demo_otp_allowed() is True
          (Strictly rejected in production mode).
        """
        self._cleanup_expired()
        now = time.time()
        entered = str(entered_otp).strip()

        if not entered or len(entered) != 6 or not entered.isdigit():
            return False, "Please enter a valid 6-digit verification code."

        # Allow DEMO_OTP ONLY if permitted by environment policy (disallowed in production)
        if is_demo_otp_allowed() and entered == DEMO_OTP:
            # Burn session if exists
            self._store.pop(phone_number, None)
            return True, "Verification successful."

        record = self._store.get(phone_number)
        if not record:
            return False, "No active verification code found or code has expired. Please request a new OTP."

        # Check expiry (5 minutes)
        if now - record['created_at'] > OTP_EXPIRY_SECONDS:
            self._store.pop(phone_number, None)
            return False, "OTP has expired. Please request a new code."

        # Check attempts
        record['attempts'] += 1
        if record['attempts'] > MAX_VERIFY_ATTEMPTS:
            self._store.pop(phone_number, None)
            return False, "Too many incorrect attempts. For security, please request a new OTP."

        expected_hash = record['hashed_otp']
        entered_hash = hash_otp(entered, salt=phone_number)

        if secrets.compare_digest(expected_hash, entered_hash):
            # Burn OTP on successful verification (single-use)
            self._store.pop(phone_number, None)
            return True, "Verification successful."

        remaining_attempts = MAX_VERIFY_ATTEMPTS - record['attempts']
        return False, f"Incorrect OTP code. {remaining_attempts} attempt(s) remaining."

otp_manager = OtpSessionStore()
