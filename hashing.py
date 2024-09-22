import hashlib
import random

def create_short_hash(url: str):
    salt = str(random.randint(0, 9999))  # Add some randomness
    short_url = hashlib.md5((str(url) + salt).encode()).hexdigest()[:6]
    return short_url
