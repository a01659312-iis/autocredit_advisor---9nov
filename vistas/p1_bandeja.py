"""P1 · Bandeja de solicitudes · Adrián (analista).
Decisión: ¿qué solicitud atiendo primero?"""
from datetime import date

import pandas as pd
import streamlit as st

from src import almacen, auth, config as C, servicios, ui
from src.simulacion import texto_hace
from src.ui import pct

usuario = auth.exigir_acceso("P1")
ui.cabecera("P1", usuario, extra=f"solo lo asignado a {usuario.analista_id}")

cola, _ = servicios.cola_analista(usuario)
hoy = date.today().isoformat()
decididas = almacen.decisiones(fecha=hoy, analista_id=usuario.analista_id)
media_pd = servicios.modelo().tasa_base

# --- Aviso de cambio de política (gerencia → analista) -------------------------
avisos = servicios.avisos_politica(usuario, cola)
if avisos:
    with st.container(border=True):
        st.markdown(f"#### 🔔 La gerencia cambió {'un corte' if len(avisos) == 1 else f'{len(avisos)} cortes'} "
                    "de política")
        for a in avisos:
            sentido = "▼ más estricto" if a["ahora"] < a["antes"] else "▲ más flexible"
            st.markdown(f"**{a['segmento']}**: el corte de PD cambió de **{a['antes']:.1%} → {a['ahora']:.1%}** "
                        f"({sentido}) · {a['autor']} a las {a['hora']}" + (" · reversión" if a["revertida"] else ""))
            if a["cambios"]:
                cambios = pd.DataFrame([{
                    "Folio": c["folio"], "PD*": pct(c["pd"]),
                    "Antes": f"{C.ICONO_SUGERENCIA[c['antes']]} {c['antes']}",
                    "Ahora": f"{C.ICONO_SUGERENCIA[c['ahora']]} {c['ahora']}",
                } for c in a["cambios"]])
                st.dataframe(cambios, hide_index=True)
            else:
                st.caption("Ninguna de tus solicitudes pendientes cambia de sugerencia.")
        st.button("Entendido", type="primary", icon=":material/done_all:",
                  on_click=almacen.marcar_avisos_vistos, args=(usuario.email, [a["id"] for a in avisos]))

# --- KPIs (arriba de todo) ------------------------------------------------------
k1, k2, k3, k4 = st.columns(4)
pendientes = cola[cola["ESTADO_SOLICITUD"] == "Pendiente"]
altos = int((pendientes["NIVEL"] == "Alto").sum())
k1.metric("⏳ Pendientes**", len(pendientes), border=True,
          delta=f"{altos} en riesgo alto 🔴" if altos else "ninguna en riesgo alto", delta_color="off",
          delta_arrow="off", help="Solicitudes asignadas a tu ANALISTA_ID que esperan decisión.")
k2.metric("📄 En espera de documento**", int((cola["ESTADO_SOLICITUD"] == "En espera de documento").sum()),
          border=True, help="Pediste un documento porque faltaba un dato clave.")
k3.metric("✅ Resueltas hoy", len(decididas), border=True,
          help="Decisiones que registraste hoy en la ficha (bitácora real del tablero).")
if len(decididas):
    minutos = decididas["duracion_seg"].median() / 60
    ok = minutos <= C.META_MINUTOS_DECISION
    k4.metric("Tiempo mediano por decisión", f"{minutos:.1f} min", border=True,
              delta=f"{'🟢 dentro' if ok else '🔴 fuera'} de la meta de {C.META_MINUTOS_DECISION} min",
              delta_color="off", delta_arrow="off")
else:
    k4.metric("Tiempo mediano por decisión", "—", border=True,
              help=f"Aparece al registrar tu primera decisión. Meta: menos de {C.META_MINUTOS_DECISION} min.")


# --- Filtros y botón principal en un solo renglón -------------------------------
def _restablecer():
    st.session_state["p1_f1"] = C.FILTROS["F1"]["defecto"]
    st.session_state["p1_f2"] = list(C.FILTROS["F2"]["defecto"])


f1, f2, f3 = st.columns([1.45, 1, 0.8], vertical_alignment="bottom")
CORTO = {"Pendiente": "Pendiente", "En espera de documento": "En espera", "Resuelta hoy": "Resuelta hoy"}
with f1:
    estado = ui.filtro("F1", "p1_f1", widget="segmented", required=True,
                       format_func=lambda e: f"{C.ICONO_ESTADO[e]} {CORTO[e]}")
with f2:
    niveles = ui.filtro("F2", "p1_f2", widget="pills", format_func=lambda n: f"{C.ICONO_NIVEL[n]} {n}")

vista = cola[(cola["ESTADO_SOLICITUD"] == estado) & (cola["NIVEL"].isin(niveles or []))]
vista = vista.sort_values(["PD", "RECIBIDA_MIN"], ascending=[False, False])


def _abrir_primera():
    st.session_state["folio_actual"] = vista.iloc[0]["FOLIO"]


with f3:
    if len(vista) and st.button("Abrir la de mayor prioridad", type="primary", help=f"Abre {vista.iloc[0]['FOLIO']} "
                                f"(PD {vista.iloc[0]['PD']:.1%}).", icon=":material/arrow_forward:",
                                on_click=_abrir_primera, width="stretch"):
        st.switch_page("vistas/p2_ficha.py")
ui.amarre_corto("F1", "F2")

ui.corte_activo(f"{C.ICONO_ESTADO[estado]} {estado} · riesgo {', '.join(niveles).lower() if niveles else 'ninguno'}",
                len(vista), len(cola), extra="solicitudes asignadas a ti**", on_reset=_restablecer, key="p1_reset")

if not niveles:
    ui.estado_vacio("No elegiste ningún nivel de riesgo",
                    "Con el filtro F2 vacío no hay solicitudes que mostrar. Elige al menos un nivel o restablece.",
                    [("Restablecer filtros", _restablecer)], key="p1_sin_nivel")
elif vista.empty and estado == "Pendiente" and len(niveles) == 3:
    ui.estado_vacio("No tienes solicitudes pendientes",
                    "Todo lo asignado a tu ANALISTA_ID está resuelto o en espera de documento.",
                    [("Ver en espera de documento",
                      lambda: st.session_state.update(p1_f1="En espera de documento"))], key="p1_vacia")
elif vista.empty:
    ui.estado_vacio("Ninguna solicitud cumple los filtros",
                    f"No hay solicitudes «{estado.lower()}» con riesgo {', '.join(niveles).lower()}.",
                    [("Restablecer filtros", _restablecer)], key="p1_sin_match")
else:
    ui.titulo_grafica("¿Qué solicitud reviso primero?", "SIMULADO", codigo="G4 · tabla con semáforo y barra de PD")

    def _vs_media(pd_):
        if pd.isna(pd_):
            return "—"
        dif = (pd_ - media_pd) * 100
        return f"{'▲' if dif > 0 else '▼'} {dif:+.1f} pp"

    tabla = pd.DataFrame({
        "Folio": vista["FOLIO"],
        "Recibida": vista["RECIBIDA_MIN"].map(texto_hace),
        "Riesgo": vista["NIVEL"].map(lambda n: f"{C.ICONO_NIVEL.get(n, '⚪')} {n}" if n else "⚪ sin PD"),
        "PD": vista["PD"] * 100,
        "Vs. media de la cartera": vista["PD"].map(_vs_media),
        "Sugerencia": [f"{C.ICONO_SUGERENCIA[s]} {s}" + (" 🔔" if s != g else "")
                       for s, g in zip(vista["SUGERENCIA"], vista["SUGERENCIA_GENERAL"])],
        "Datos": vista["CALIDAD"].map(lambda c: f"{C.ICONO_CALIDAD[c]} {c}"),
        "Corte vigente": vista["CORTE"].map(lambda c: f"{c:.1%}" + (" 🔔" if abs(c - C.CORTE_PD) > 1e-9 else "")),
    })
    seleccion = st.dataframe(
        tabla, hide_index=True, on_select="rerun", selection_mode="single-row", key="p1_tabla",
        column_config={
            "Folio": st.column_config.TextColumn("Folio**", help="Completo porque es tu caso."),
            "Recibida": st.column_config.TextColumn("Recibida**"),
            "Riesgo": st.column_config.TextColumn("Riesgo*", help=f"🔴 alto: PD ≥ corte vigente · 🟡 medio: cerca del "
                                                 f"corte · 🟢 bajo: PD < {C.LIMITE_RIESGO_BAJO:.0%}."),
            "PD": st.column_config.ProgressColumn("PD*", format="%.1f%%", min_value=0,
                                                  max_value=C.ESCALA_PD_MAX * 100, color="blue"),
            "Vs. media de la cartera": st.column_config.TextColumn(
                f"Vs. media ({media_pd:.1%})", help="Diferencia contra el incumplimiento medio de la cartera. "
                "▲ = más riesgo que la media."),
            "Sugerencia": st.column_config.TextColumn("Sugerencia del modelo*", help="🔔 = cambió por un corte "
                                                      "publicado por la gerencia."),
            "Corte vigente": st.column_config.TextColumn("Corte vigente*", help="🔔 = corte de un segmento "
                                                         "publicado por la gerencia (distinto al general de 15%)."),
        },
    )
    filas = seleccion.selection.rows if seleccion else []
    if filas:
        st.session_state["folio_actual"] = tabla.iloc[filas[0]]["Folio"]
        st.switch_page("vistas/p2_ficha.py")
    st.caption(f"Selecciona una fila para abrir su ficha. Orden: PD de mayor a menor; en empate, la más antigua. "
               f"Barra de PD en escala 0–{C.ESCALA_PD_MAX:.0%}.")

ui.pie_origen("Las variables de cada solicitud son filas reales del 25% de la base que el modelo no vio; folio, "
              "hora, estado y los tres casos con dato faltante o fuera de rango son simulados**.")
