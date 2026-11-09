"""Componentes de interfaz compartidos.

Notación de origen (recomendación 1):
    sin marca  -> dato real de Base_SAS_Equipo3.csv
    *          -> dato propio: lo calcula el equipo a partir de la base (modelo de PD, segmentos, umbrales)
    **         -> dato simulado: la base aún no lo trae; se genera para demostrar la pantalla
Cada pantalla termina con un pie que explica las marcas que usa.
"""
from __future__ import annotations

from typing import Callable

import pandas as pd
import streamlit as st

from src import config as C
from src.seguridad import PANTALLAS

# Marca por tipo de origen. La política del equipo (cortes, bandas) también es dato propio.
MARCA = {
    "REAL": "", "REAL en bitácora": "", "CALCULADO": "*", "POLÍTICA": "*", "SIMULADO": "**",
    "NO PRESENTE": "",
}
NOMBRE_ORIGEN = {  # minúsculas normales para mostrar en tablas
    "REAL": "Real", "REAL en bitácora": "Real (bitácora)", "CALCULADO": "Propio*", "POLÍTICA": "Propio*",
    "SIMULADO": "Simulado**", "NO PRESENTE": "No viene en la base", "SIMULADO + REAL de la bitácora":
    "Simulado** + bitácora",
}
# Se conserva para la matriz de gobierno (P6).
COLOR_ORIGEN = {"REAL": "green", "CALCULADO": "blue", "SIMULADO": "orange", "POLÍTICA": "violet"}
AYUDA_ORIGEN = {
    "REAL": "Sin marca: columna tal cual de Base_SAS_Equipo3.csv (80,000 créditos × 12 columnas).",
    "CALCULADO": "* Dato propio: lo calcula el equipo con la base o con el modelo de PD.",
    "SIMULADO": "** Dato simulado: la base aún no lo trae; se genera para demostrar la pantalla.",
    "POLÍTICA": "* Dato propio: umbral definido por el equipo; se calibra con datos reales.",
}


def estilos() -> None:
    st.markdown(
        """
        <style>
        .block-container {padding-top: 1.6rem; padding-bottom: 2rem; max-width: 1440px;}
        h1 {font-size: 2rem !important; padding-bottom: 0.1rem !important;}
        [data-testid="stMetricValue"] {font-size: 1.6rem;}
        [data-testid="stCaptionContainer"] p {line-height: 1.35;}
        </style>
        """,
        unsafe_allow_html=True,
    )


def marca(*origenes: str) -> str:
    """Marca escapada para markdown: '\\*' o '\\*\\*' (la más fuerte de las dadas)."""
    m = max((MARCA.get(o, "") for o in origenes), key=len, default="")
    return m.replace("*", "\\*")


def cabecera(pantalla: str, usuario, extra: str | None = None) -> None:
    p = PANTALLAS[pantalla]
    st.title(p["titulo"])
    persona = f"{usuario.persona} ({usuario.nombre_corto})" if usuario else ""
    linea = f"{pantalla} · **{persona}** · {p['decision']}"
    if extra:
        linea += f" · {extra}"
    st.caption(linea)


def titulo_grafica(pregunta: str, *origenes: str, codigo: str | None = None) -> None:
    m = marca(*origenes)
    st.markdown(f"**{pregunta}**{m}" + (f"  \n:gray[{codigo}]" if codigo else ""))


def amarre(fid_o_cid: str) -> str:
    reg = C.FILTROS.get(fid_o_cid) or C.CONTROLES[fid_o_cid]
    persona = reg["persona"].split(" (")[0]
    return f"↳ {persona} decide: {reg['decision']}"


def amarre_corto(*ids: str) -> None:
    """Un solo renglón que amarra varios filtros a la decisión de su persona (ahorra espacio)."""
    reg = C.FILTROS.get(ids[0]) or C.CONTROLES[ids[0]]
    persona = reg["persona"].split(" (")[0]
    partes = " · ".join(f"**{i}** {C.DECISION_CORTA[i]}" for i in ids)
    st.caption(f"↳ {persona} decide con estos filtros: {partes}. Pasa el cursor por ⓘ para ver la decisión completa.")


def filtro(fid: str, key: str, widget: str = "selectbox", on_change: Callable | None = None,
           mostrar_amarre: bool = False, **kw):
    """Dibuja un filtro desde el registro. La decisión completa va en la ayuda (ⓘ) y,
    para no alargar la pantalla, el amarre visible se pinta en un renglón por grupo."""
    reg = C.FILTROS[fid]
    etiqueta = f"{fid} · {reg['nombre']}"
    ayuda = f"{reg['persona']} decide: {reg['decision']} Por defecto: {reg['defecto']}."
    if key not in st.session_state:
        st.session_state[key] = reg["defecto"]
    if widget == "selectbox":
        valor = st.selectbox(etiqueta, reg["opciones"], key=key, help=ayuda, on_change=on_change, **kw)
    elif widget == "segmented":
        valor = st.segmented_control(etiqueta, reg["opciones"], key=key, help=ayuda, on_change=on_change, **kw)
    elif widget == "pills":
        valor = st.pills(etiqueta, reg["opciones"], selection_mode="multi", key=key, help=ayuda,
                         on_change=on_change, **kw)
    else:
        raise ValueError(widget)
    if mostrar_amarre:
        st.caption(amarre(fid))
    return valor


def corte_activo(descripcion: str, n: int, total: int, extra: str = "",
                 on_reset: Callable | None = None, key: str = "reset") -> None:
    with st.container(border=True, horizontal=True, vertical_alignment="center"):
        pct_ = n / total * 100 if total else 0
        st.markdown(
            f":blue[**Corte activo:**] {descripcion} → **{n:,} de {total:,}** ({pct_:.1f}%)"
            + (f" · {extra}" if extra else "")
        )
        st.space("stretch")
        if on_reset:
            st.button("Restablecer", key=key, on_click=on_reset, icon=":material/restart_alt:")


def estado_vacio(titulo: str, causa: str, acciones: list[tuple[str, Callable]] | None = None,
                 icono: str = ":material/block:", key: str = "vacio") -> None:
    with st.container(border=True):
        st.markdown(f"#### {titulo}")
        st.markdown(causa)
        if acciones:
            with st.container(horizontal=True):
                for i, (texto, cb) in enumerate(acciones):
                    st.button(texto, key=f"{key}_{i}", on_click=cb, type="primary" if i == 0 else "secondary")


# ---------------------------------------------------------------------------
# Semáforo verde / amarillo / rojo (recomendación 3). Siempre ícono + texto.
# ---------------------------------------------------------------------------
ESTADOS_SEMAFORO = {
    "ok": ("En banda", "green", ":material/check_circle:"),
    "vigilar": ("Advertencia", "orange", ":material/error:"),
    "alerta": ("Fuera de banda", "red", ":material/warning:"),
    "sin_datos": ("Sin datos frescos", "gray", ":material/hourglass_empty:"),
}


def semaforo(nombre: str, valor: str, estado: str, detalle: str, delta: str | None = None,
             delta_color: str = "off", origen_tag: str = "SIMULADO") -> None:
    texto, color, icono = ESTADOS_SEMAFORO[estado]
    with st.container(border=True):
        st.badge(texto, color=color, icon=icono)
        st.metric(f"{nombre}{marca(origen_tag)}", valor, delta=delta,
                  delta_color=delta_color if estado != "sin_datos" else "off",
                  delta_arrow="auto" if delta else "off")
        st.caption(detalle)


def estado_segmento(tasa: float | None) -> tuple[str, str, str]:
    """Semáforo de incumplimiento de un segmento contra la tolerancia de la política."""
    if tasa is None or pd.isna(tasa):
        return "Sin muestra", "gray", "⚪"
    if tasa > C.TOLERANCIA_SEGMENTO:
        return "Fuera de tolerancia", "red", "🔴"
    if tasa > C.AMARILLO_SEGMENTO:
        return "Advertencia", "orange", "🟡"
    return "Dentro de tolerancia", "green", "🟢"


def flecha(delta: float, sentido: int = 1, umbral: float = 0.0) -> str:
    """▲ / ▼ según la variación; el color lo da quien llama con sentido de riesgo."""
    if abs(delta) <= umbral:
        return "＝"
    return "▲" if delta > 0 else "▼"


def ver_tabla(df: pd.DataFrame, etiqueta: str = "Ver como tabla", **kw) -> None:
    with st.expander(etiqueta):
        st.dataframe(df, hide_index=True, **kw)


def pie_origen(texto_extra: str = "", marcas: tuple[str, ...] = ("*", "**")) -> None:
    """Pie de pantalla: aclara qué significan las marcas usadas en la pantalla."""
    st.divider()
    notas = []
    if "*" in marcas:
        notas.append("\\* **Dato propio:** lo calcula el equipo a partir de la base (modelo de PD, segmentos, "
                     "cortes y bandas de política).")
    if "**" in marcas:
        notas.append("\\*\\* **Dato simulado:** la base aún no lo trae (folios, fechas, estados, decisiones); "
                     "se genera a partir de filas reales para demostrar la pantalla.")
    notas.append("Sin marca: dato real de Base_SAS_Equipo3.csv (80,000 créditos).")
    st.caption("  \n".join(notas) + (f"  \n{texto_extra}" if texto_extra else ""))


def pct(x: float | None, dec: int = 1) -> str:
    if x is None or pd.isna(x):
        return "—"
    return f"{x * 100:.{dec}f}%"
