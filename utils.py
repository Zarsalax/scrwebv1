"""
UTILIDADES
"""
import random
import hashlib
import secrets
from datetime import datetime, timedelta

class LuhnValidator:
    @staticmethod
    def calculate_checksum(card_number):
        digits = [int(d) for d in str(card_number)]
        odd_digits = digits[-1::-2]
        even_digits = digits[-2::-2]
        checksum = sum(odd_digits)
        for d in even_digits:
            checksum += sum([int(x) for x in str(d * 2)])
        return checksum % 10

    @staticmethod
    def generate_luhn_digit(partial_card):
        check_digit = LuhnValidator.calculate_checksum(str(partial_card) + '0')
        return (10 - check_digit) % 10

    @staticmethod
    def validate_card(card_number):
        return LuhnValidator.calculate_checksum(card_number) == 0

class DateValidator:
    @staticmethod
    def get_current_date():
        now = datetime.now()
        return f"{now.month:02d}/{now.year % 100:02d}"

    @staticmethod
    def is_date_valid(month, year):
        try:
            month = int(month)
            year = int(year)
            if year <= 30:
                year += 2000
            elif year <= 99:
                year += 1900
            if month == 12:
                expiry_date = datetime(year + 1, 1, 1) - timedelta(days=1)
            else:
                expiry_date = datetime(year, month + 1, 1) - timedelta(days=1)
            return expiry_date >= datetime.now()
        except:
            return False

    @staticmethod
    def generate_random_valid_date():
        now = datetime.now()
        days_ahead = random.randint(0, 365 * 5)
        future_date = now + timedelta(days=days_ahead)
        return f"{future_date.month:02d}", str(future_date.year)

class CCGenerator:
    @staticmethod
    def parse_cc_base(ccbase):
        if ',' in ccbase:
            separator = ','
        elif '|' in ccbase:
            separator = '|'
        else:
            return None, "Formato desconocido"

        parts = ccbase.strip().split(separator)
        if len(parts) < 4:
            return None, "Formato inválido"

        cardnumber, month, year, cvv = parts[0], parts[1], parts[2], parts[3]

        if len(cardnumber) < 12:
            return None, "Tarjeta muy corta"

        return (cardnumber, month, year, cvv, separator), None

    @staticmethod
    def generate_variants(ccbase, count=20):
        parsed, error = CCGenerator.parse_cc_base(ccbase)
        if error:
            return [], error

        cardnumber, month, year, cvv, separator = parsed

        if not DateValidator.is_date_valid(month, year):
            month, year = DateValidator.generate_random_valid_date()

        variants = []

        if len(cardnumber) > 15:
            bin_number = cardnumber[:-6]
            for i in range(count):
                random_digits = ''.join([str(random.randint(0, 9)) for _ in range(5)])
                partial = bin_number + random_digits
                luhn_digit = LuhnValidator.generate_luhn_digit(partial)
                complete = partial + str(luhn_digit)
                rcvv = random.randint(100, 999)
                variant = f"{complete}{separator}{month}{separator}{year}{separator}{rcvv}"
                if variant not in variants:
                    variants.append(variant)
        else:
            bin_number = cardnumber[:-4]
            for i in range(count):
                random_digits = ''.join([str(random.randint(0, 9)) for _ in range(3)])
                partial = bin_number + random_digits
                luhn_digit = LuhnValidator.generate_luhn_digit(partial)
                complete = partial + str(luhn_digit)
                rcvv = random.randint(100, 999)
                variant = f"{complete}{separator}{month}{separator}{year}{separator}{rcvv}"
                if variant not in variants:
                    variants.append(variant)

        return variants, None

class PasswordManager:
    @staticmethod
    def hash_password(password):
        salt = secrets.token_hex(32)
        pwd_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${pwd_hash.hex()}"

    @staticmethod
    def verify_password(password, password_hash):
        try:
            salt, pwd_hash = password_hash.split('$')
            new_hash = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return new_hash.hex() == pwd_hash
        except:
            return False

    @staticmethod
    def generate_session_token():
        return secrets.token_urlsafe(32)
