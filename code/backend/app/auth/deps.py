"""Dépendances d'authentification : récupération de l'utilisateur courant via JWT."""
from __future__ import annotations

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session

from app.auth.security import decode_token
from app.db.models import User
from app.db.session import get_db

# tokenUrl : endpoint qui délivre le jeton (utilisé par Swagger pour « Authorize »)
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="auth/jwt/login")

_CREDENTIALS_ERROR = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Jeton invalide ou expiré",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Décode le jeton, charge l'utilisateur et vérifie qu'il est actif."""
    user_id = decode_token(token)
    if user_id is None:
        raise _CREDENTIALS_ERROR
    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise _CREDENTIALS_ERROR
    return user
