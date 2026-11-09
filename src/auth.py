"""Autenticación (¿quién eres?) y autorización (¿qué puedes ver?).

- Con [auth] en .streamlit/secrets.toml se usa st.login (OIDC: Google o Microsoft).
- Sin esa sección la app arranca en MODO DEMOSTRACIÓN con cuentas de prueba.
La tabla correo -> rol vive en secrets ([roles]) y nunca en el repositorio.
"""
from __future__ import annotations

import time

import streamlit as st

from src import almacen, config as C
from src.seguridad import PANTALLAS, USUARIOS_DEMO, Usuario, puede_ver


def modo_oidc() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def tabla_roles() -> dict:
    try:
        if "roles" in st.secrets:
            return {k.lower(): dict(v) for k, v in st.secrets["roles"].items()}
    except Exception:
        pass
    return USUARIOS_DEMO


def email_actual() -> str | None:
    if modo_oidc():
        return st.user.email if st.user.is_logged_in else None
    return st.session_state.get("demo_email")


def usuario_actual() -> Usuario | None:
    email = email_actual()
    if not email:
        return None
    info = tabla_roles().get(email.lower())
    if not info or not info.get("rol"):
        return Usuario(email=email, nombre=(info or {}).get("nombre", email), rol=None)
    return Usuario(email=email, nombre=info.get("nombre", email), rol=info["rol"],
                   analista_id=info.get("analista_id"))


def entrar_demo(email: str) -> None:
    st.session_state["demo_email"] = email
    st.session_state["ultima_actividad"] = time.time()
    st.session_state.pop("aviso_expiracion", None)


def salir(expirada: bool = False) -> None:
    if modo_oidc():
        st.logout()
        return
    conservar = {}
    if expirada:
        conservar["aviso_expiracion"] = True
    for k in list(st.session_state.keys()):
        del st.session_state[k]
    st.session_state.update(conservar)


def registrar_actividad(pagina: str) -> None:
    """Cierra la sesión tras SESION_TIMEOUT_MIN sin actividad y guarda dónde iba
    la persona para regresarla a la misma solicitud con lo ya capturado."""
    usuario = usuario_actual()
    ahora = time.time()
    ultima = st.session_state.get("ultima_actividad", ahora)
    forzada = st.session_state.pop("forzar_expiracion", False)
    if usuario and (forzada or ahora - ultima > C.SESION_TIMEOUT_MIN * 60):
        almacen.guardar_regreso(usuario.email, pagina, st.session_state.get("folio_actual"))
        salir(expirada=True)
        st.rerun()
    st.session_state["ultima_actividad"] = ahora


def exigir_acceso(pantalla: str) -> Usuario:
    """Defensa en profundidad: aunque la navegación ya oculta la pantalla, cada
    página vuelve a verificar el rol antes de cargar un solo dato."""
    usuario = usuario_actual()
    if usuario is None or not puede_ver(usuario.rol, pantalla):
        st.error(f"No tienes acceso a {pantalla} · {PANTALLAS[pantalla]['titulo']}. "
                 "Si lo necesitas, pide acceso a tu gerente.", icon=":material/lock:")
        st.stop()
    return usuario
