"""AutoCredit Advisor · punto de entrada.

Ejecuta:  streamlit run app.py
El rol de quien inicia sesión decide qué pantallas aparecen en la navegación
(matriz persona × pantalla del Bloque F) y cada pantalla vuelve a verificarlo.
"""
from __future__ import annotations

import streamlit as st

from src import almacen, auth, config as C, servicios, ui
from src.seguridad import PANTALLAS, ROLES, puede_ver
from src.simulacion import ESCENARIOS

st.set_page_config(page_title=C.APP_NOMBRE, page_icon=":material/speed:", layout="wide",
                   initial_sidebar_state="expanded")
ui.estilos()

DEF_PAGINAS = {
    "P1": ("vistas/p1_bandeja.py", "P1 · Bandeja", ":material/inbox:", "bandeja"),
    "P2": ("vistas/p2_ficha.py", "P2 · Ficha de solicitud", ":material/description:", "ficha"),
    "P3": ("vistas/p3_cartera.py", "P3 · Cartera por segmento", ":material/grid_view:", "cartera"),
    "P4": ("vistas/p4_monitor.py", "P4 · Monitor operativo", ":material/monitor_heart:", "monitor"),
    "P5": ("vistas/p5_estados.py", "P5 · Estados y recorridos", ":material/alt_route:", "estados"),
    "P6": ("vistas/p6_gobierno.py", "P6 · Gobierno de datos", ":material/shield_person:", "gobierno"),
}
INICIO_POR_ROL = {"analista": "P1", "gerente": "P3", "operacion": "P4"}

usuario = auth.usuario_actual()

# --- Sin sesión: solo P0 -----------------------------------------------------
if usuario is None:
    st.navigation([st.Page("vistas/p0_login.py", title="P0 · Inicio de sesión", icon=":material/login:")],
                  position="hidden").run()
    st.stop()

# --- Correo sin rol: ningún dato --------------------------------------------
if usuario.rol is None:
    st.navigation([st.Page("vistas/sin_acceso.py", title="Sin acceso", icon=":material/lock:")],
                  position="hidden").run()
    st.stop()

# --- Base ausente o con esquema inválido: estado de excepción, no traceback ---
datos_ok, error_datos = servicios.estado_datos()
if not datos_ok:
    st.title("No hay datos que mostrar")
    st.error(error_datos, icon=":material/database_off:")
    st.markdown("**Cómo recuperarse:** coloca `Base_SAS_Equipo3.csv` en la carpeta `data/` del proyecto "
                "y recarga la página. Si el archivo existe, revisa que tenga las 12 columnas esperadas.")
    st.button("Reintentar", on_click=st.cache_data.clear, type="primary")
    st.stop()

# --- Navegación según rol ----------------------------------------------------
inicio = INICIO_POR_ROL[usuario.rol]
PAGINAS = {pid: st.Page(ruta, title=titulo, icon=icono, url_path=url, default=pid == inicio)
           for pid, (ruta, titulo, icono, url) in DEF_PAGINAS.items()}
visibles = [pid for pid in PAGINAS if puede_ver(usuario.rol, pid)]
principales = [PAGINAS[p] for p in visibles if p in ("P1", "P2", "P3", "P4")]
apoyo = [PAGINAS[p] for p in visibles if p in ("P5", "P6")]
pagina = st.navigation({f"{usuario.persona} · {ROLES[usuario.rol]}": principales, "Para todos": apoyo})

pid_actual = next((pid for pid, p in PAGINAS.items() if p.url_path == pagina.url_path), inicio)
auth.registrar_actividad(pid_actual)

# Regreso tras sesión expirada: vuelve a la misma pantalla y solicitud.
if not st.session_state.get("regreso_revisado"):
    st.session_state["regreso_revisado"] = True
    regreso = almacen.tomar_regreso(usuario.email)
    if regreso and puede_ver(usuario.rol, regreso["pagina"]):
        if regreso["folio"]:
            st.session_state["folio_actual"] = regreso["folio"]
        st.session_state["aviso_regreso"] = True
        if regreso["pagina"] != pid_actual:
            st.switch_page(PAGINAS[regreso["pagina"]])

# --- Barra lateral -----------------------------------------------------------
with st.sidebar:
    st.markdown(f"### {C.APP_NOMBRE}")
    with st.container(border=True):
        st.markdown(f"**{usuario.nombre}**  \n{ROLES[usuario.rol]}")
        if usuario.analista_id:
            st.caption(f"ANALISTA_ID: {usuario.analista_id}")
        st.caption(usuario.email)
        st.badge("OIDC institucional" if auth.modo_oidc() else "Modo demostración",
                 color="green" if auth.modo_oidc() else "orange")
        st.button("Cerrar sesión", on_click=auth.salir, icon=":material/logout:", width="stretch")
    st.caption(f"La sesión expira tras {C.SESION_TIMEOUT_MIN} min sin actividad. Modelo {C.VERSION_MODELO}.")

    if not auth.modo_oidc():
        with st.expander("Controles de demostración", icon=":material/science:"):
            st.caption("Solo existen en modo demostración. Sirven para recorrer los estados de excepción.")
            if usuario.rol == "operacion":
                st.selectbox("Escenario del monitor (SIMULADO)", list(ESCENARIOS), key="escenario",
                             format_func=ESCENARIOS.get)

            def _expirar():
                st.session_state["forzar_expiracion"] = True

            st.button("Simular expiración de sesión", on_click=_expirar, width="stretch")

            def _reiniciar():
                almacen.reiniciar_demo()
                st.cache_data.clear()
                st.session_state.pop("folio_actual", None)

            st.button("Reiniciar bitácora de demo", on_click=_reiniciar, width="stretch")

pagina.run()
