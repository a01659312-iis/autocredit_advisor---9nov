"""P0 · Inicio de sesión (las tres personas). No muestra ningún dato de negocio."""
import streamlit as st

from src import auth, config as C
from src.seguridad import ROLES

_, centro, _ = st.columns([1, 1.4, 1])
with centro:
    st.space("large")
    st.title(C.APP_NOMBRE)
    st.caption("P0 · Inicio de sesión · Evaluación de riesgo en crédito automotriz")

    if st.session_state.get("aviso_expiracion"):
        st.warning(f"Tu sesión se cerró tras {C.SESION_TIMEOUT_MIN} min sin actividad. Al volver a entrar "
                   "regresas a la misma solicitud con lo que ya habías capturado.", icon=":material/timer_off:")

    with st.container(border=True):
        st.markdown("#### Inicia sesión con tu cuenta institucional")
        if auth.modo_oidc():
            proveedor = st.secrets.get("proveedor_oidc")
            st.button("Continuar con cuenta institucional", type="primary", width="stretch",
                      on_click=(lambda: st.login(proveedor)) if proveedor else st.login)
        else:
            st.info("**Modo demostración.** No hay proveedor OIDC configurado en `.streamlit/secrets.toml`, "
                    "así que se usan cuentas de prueba. El rol de cada cuenta decide qué pantallas ve.",
                    icon=":material/science:")
            tabla = auth.tabla_roles()

            def _etiqueta(email: str) -> str:
                info = tabla[email]
                rol = ROLES.get(info.get("rol") or "", "sin rol asignado")
                extra = f" · {info['analista_id']}" if info.get("analista_id") else ""
                return f"{info['nombre']} — {rol}{extra}"

            email = st.selectbox("Cuenta de prueba", list(tabla), format_func=_etiqueta, key="login_email")
            st.button("Entrar", type="primary", width="stretch", on_click=auth.entrar_demo, args=(email,))

    st.caption(
        "Tu rol (analista, gerente u operación) decide qué pantallas ves. Si tu correo no tiene rol "
        f"asignado verás «Pide acceso a tu gerente» y ningún dato. La sesión expira tras "
        f"{C.SESION_TIMEOUT_MIN} min sin actividad."
    )
