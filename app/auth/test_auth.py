import pytest
import os
from datetime import timedelta
from unittest.mock import patch
from app.auth.security import (
    create_access_token,
    hash_password,
    verify_password,
    get_current_user
)
from jose import jwt, JWTError
from fastapi import HTTPException, status


@pytest.fixture
def jwt_secret():
    """Fixture to provide JWT secret for testing"""
    return "test-secret-key-for-testing-only"


class TestPasswordHashing:
    """Test password hashing and verification"""
    
    def test_hash_password(self):
        """Test that password hashing works"""
        password = "test_password_123"
        hashed = hash_password(password)
        assert hashed != password
        assert len(hashed) > 0
    
    def test_verify_password_correct(self):
        """Test verifying correct password"""
        password = "test_password_123"
        hashed = hash_password(password)
        assert verify_password(password, hashed) is True
    
    def test_verify_password_incorrect(self):
        """Test verifying incorrect password"""
        password = "test_password_123"
        wrong_password = "wrong_password"
        hashed = hash_password(password)
        assert verify_password(wrong_password, hashed) is False


class TestCreateAccessToken:
    """Test JWT token creation"""
    
    @patch.dict(os.environ, {
        "JWT_SECRET_KEY": "test-secret-key",
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60"
    })
    def test_create_access_token_basic(self):
        """Test creating a basic access token"""
        data = {"sub": "1"}
        token = create_access_token(data)
        assert token is not None
        assert isinstance(token, str)
        assert len(token) > 0
    
    @patch.dict(os.environ, {
        "JWT_SECRET_KEY": "test-secret-key",
        "JWT_ALGORITHM": "HS256",
        "ACCESS_TOKEN_EXPIRE_MINUTES": "60"
    })
    def test_create_access_token_with_custom_expiry(self):
        """Test creating token with custom expiry"""
        data = {"sub": "2"}
        expires_delta = timedelta(minutes=30)
        token = create_access_token(data, expires_delta)
        assert token is not None
        assert isinstance(token, str)
    
    def test_token_contains_user_data(self):
        """Test that token contains the original data"""
        # Need to use the actual JWT_SECRET_KEY from environment
        secret_key = os.getenv("JWT_SECRET_KEY")
        if not secret_key:
            pytest.skip("JWT_SECRET_KEY not set in environment")
        
        data = {"sub": "3", "email": "test@example.com"}
        token = create_access_token(data)
        
        # Decode token to verify data with the actual secret key
        decoded = jwt.decode(
            token,
            secret_key,
            algorithms=[os.getenv("JWT_ALGORITHM", "HS256")]
        )
        assert decoded["sub"] == "3"
        assert decoded["email"] == "test@example.com"
        assert "exp" in decoded
