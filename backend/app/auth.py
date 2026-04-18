"""
JWT verification using the Supabase JWT secret.
Every request to /chat is verified against this.
"""
import jwt
from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from app.config import settings

_bearer = HTTPBearer(auto_error=False)


def verify_token(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> dict:
    """
    Decode and verify the Supabase JWT.
    Returns the payload dict (contains sub = user UUID, email, etc.)
    Raises 401 if invalid or missing.
    """
    # If no JWT secret configured → dev mode, allow everything
    if not settings.SUPABASE_JWT_SECRET:
        return {"sub": "dev-user", "email": "dev@localhost", "dev_mode": True}

    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = jwt.decode(
            credentials.credentials,
            settings.SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            options={"verify_aud": False},   # Supabase uses "authenticated" as aud
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {e}")


def get_optional_user(credentials: HTTPAuthorizationCredentials = Security(_bearer)) -> dict | None:
    """Like verify_token but doesn't raise — for optional auth routes."""
    try:
        return verify_token(credentials)
    except HTTPException:
        return None


def get_current_user_id(token_payload: dict = Depends(verify_token)) -> str:
    """
    FastAPI dependency: extracts the authenticated user's UUID from the JWT.

    Usage in routes:
        @router.post("/chat")
        async def chat(user_id: str = Depends(get_current_user_id)):
            ...

    Returns the `sub` claim from the JWT, which is the user's UUID
    in Supabase's auth.users table. All DB writes should use this ID.

    In dev mode (no JWT secret configured), returns the dev user UUID.
    """
    user_id = token_payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token missing 'sub' claim",
        )
    return user_id
