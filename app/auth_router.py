from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlmodel import Session, select

from app.auth import (
    create_access_token,
    decode_access_token,
    hash_password,
    verify_password,
)
from app.database import get_session
from app.models import Usuario
from app.schemas import LoginRequest, Token, UsuarioCreate, UsuarioRead

router = APIRouter(prefix="/auth", tags=["Autenticación"])

# Esquema Bearer para proteger endpoints con JWT
security = HTTPBearer()


# ---------------------------------------------------------------------------
# POST /auth/register — Registrar nuevo usuario
# ---------------------------------------------------------------------------


@router.post(
    "/register",
    response_model=UsuarioRead,
    status_code=status.HTTP_201_CREATED,
    summary="Registrar usuario",
)
def register(
    payload: UsuarioCreate,
    session: Session = Depends(get_session),
) -> UsuarioRead:
    # Verificar que el email no esté en uso
    existente = session.exec(
        select(Usuario).where(Usuario.email == payload.email)
    ).first()
    if existente:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"El email '{payload.email}' ya está registrado.",
        )

    usuario = Usuario(
        nombre=payload.nombre,
        email=payload.email,
        hashed_password=hash_password(payload.password),
    )
    session.add(usuario)
    session.commit()
    session.refresh(usuario)
    return usuario


# ---------------------------------------------------------------------------
# POST /auth/login — Iniciar sesión y obtener JWT
# ---------------------------------------------------------------------------


@router.post(
    "/login",
    response_model=Token,
    summary="Iniciar sesión",
)
def login(
    payload: LoginRequest,
    session: Session = Depends(get_session),
) -> Token:
    usuario = session.exec(
        select(Usuario).where(Usuario.email == payload.email)
    ).first()

    if not usuario or not verify_password(payload.password, usuario.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales incorrectas.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    if not usuario.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cuenta inactiva. Contacta al administrador.",
        )

    token = create_access_token(data={"sub": usuario.email})
    return Token(access_token=token)


# ---------------------------------------------------------------------------
# Dependencia reutilizable: obtener usuario autenticado desde el token
# ---------------------------------------------------------------------------


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    session: Session = Depends(get_session),
) -> Usuario:
    """
    Dependencia FastAPI para proteger endpoints.
    Uso: usuario: Usuario = Depends(get_current_user)
    """
    token = credentials.credentials
    email = decode_access_token(token)

    if not email:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token inválido o expirado.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    usuario = session.exec(
        select(Usuario).where(Usuario.email == email)
    ).first()

    if not usuario or not usuario.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Usuario no encontrado o inactivo.",
        )

    return usuario


# ---------------------------------------------------------------------------
# GET /auth/me — Perfil del usuario autenticado
# ---------------------------------------------------------------------------


@router.get(
    "/me",
    response_model=UsuarioRead,
    summary="Perfil del usuario autenticado",
)
def get_me(
    current_user: Usuario = Depends(get_current_user),
) -> UsuarioRead:
    return current_user
