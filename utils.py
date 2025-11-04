import random, hashlib, secrets
from datetime import datetime, timedelta

class PasswordManager:
    @staticmethod
    def hash_password(password):
        salt = secrets.token_hex(32)
        h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
        return f"{salt}${h.hex()}"
    @staticmethod
    def verify_password(password, password_hash):
        try:
            salt, h = password_hash.split('$')
            new_h = hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 100000)
            return new_h.hex() == h
        except:
            return False
    @staticmethod
    def generate_session_token():
        return secrets.token_urlsafe(32)

class CCGenerator:
    @staticmethod
    def parse_cc_base(ccbase):
        sep = ',' if ',' in ccbase else '|' if '|' in ccbase else None
        if not sep:
            return None, "Formato desconocido"
        parts = ccbase.strip().split(sep)
        if len(parts) < 4 or len(parts[0]) < 12:
            return None, "Formato inválido"
        return (parts[0], parts[1], parts[2], parts[3], sep), None
    @staticmethod
    def generate_luhn_digit(partial):
        digits = [int(d) for d in str(partial)]
        odd = digits[-1::-2]
        even = digits[-2::-2]
        s = sum(odd)
        for d in even:
            s += sum([int(x) for x in str(d * 2)])
        return (10 - (s % 10)) % 10
    @staticmethod
    def generate_variants(ccbase, count=20):
        parsed, err = CCGenerator.parse_cc_base(ccbase)
        if err:
            return [], err
        cc, month, year, cvv, sep = parsed
        variants = []
        bin_len = 6 if len(cc) > 15 else 4
        bin_number = cc[:-bin_len]
        for i in range(count):
            random_digits = ''.join([str(random.randint(0, 9)) for _ in range(bin_len - 1)])
            partial = bin_number + random_digits
            luhn = CCGenerator.generate_luhn_digit(str(partial) + '0')
            complete = partial + str(luhn)
            random_cvv = random.randint(100, 999)
            variant = f"{complete}{sep}{month}{sep}{year}{sep}{random_cvv}"
            if variant not in variants:
                variants.append(variant)
        return variants, None
