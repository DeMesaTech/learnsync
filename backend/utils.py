"""Utility helper functions"""
import hashlib


def hash_password(password: str) -> str:
    """Hash password using SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify if plain password matches the hash"""
    return hash_password(plain_password) == hashed_password
