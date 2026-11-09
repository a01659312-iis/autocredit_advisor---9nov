"""P3 · Cartera por segmento · Mariana (gerente de riesgo).
Decisión: endurecer o relajar la política de un segmento. Solo recibe agregados."""
from datetime import date

import pandas as pd
import streamlit as st

from src import almacen, auth, config as C, datos, graficas as G, politica, servicios, ui
from src.ui import pct

usuario = auth.exigir_acceso("P3")
ui.cabecera("P3", usuario, extra="solo agregados con n ≥ 30; ningún crédito individual")

FIDS = ["F3", "F4", "F5", "F6"]
CLAVES = {f: f"p3_{f}" for f in FIDS}
DIMENSION = {"DTI": ("SEG_DTI", "F3"), "Enganche": ("SEG_ENGANCHE", "F4"),
             "Pagos fallidos": ("SEG_PAGOS", "F5"), "Bancarrota": ("SEG_BANCARROTA", "F6"),
             "LTV": ("SEG_LTV", None)}


def _registrar_cambio(fid: str) -> None:
    orden = st.session_state.setdefault("p3_orden", [])
    if fid in orden:
        orden.remove(fid)
    if st.session_state[CLAVES[fid]] != C.TODOS:
        orden.append(fid)


def _restablecer() -> None:
    for f in FIDS:
        st.session_state[CLAVES[f]] = C.TODOS
    st.session_state["p3_orden"] = []


def _quitar_ultimo() -> None:
    orden = st.session_state.get("p3_orden", [])
    if orden:
        st.session_state[CLAVES[orden.pop()]] = C.TODOS


# --- Filtros arriba, en un renglón, con su decisión en un solo renglón ---------
for col, fid in zip(st.columns(4), FIDS):
    with col:
        ui.filtro(fid, CLAVES[fid], on_change=_registrar_cambio, args=(fid,))
ui.amarre_corto(*FIDS)

filtros = tuple((f, st.session_state[CLAVES[f]]) for f in FIDS)
segmento = politica.segmento_activo(dict(filtros))
resumen = servicios.resumen_corte(usuario.rol, filtros)
activas = almacen.politicas(solo_activas=True)
corte_vigente = politica.corte_vigente_segmento(segmento, activas)
ui.corte_activo(datos.describir_filtros(dict(filtros)), resumen["n"], resumen["total"],
                extra=f"corte de PD vigente {corte_vigente:.1%}*" + (" 🔔 publicado" if corte_vigente != C.CORTE_PD else ""),
                on_reset=_restablecer, key="p3_reset")

# --- Recorrido de error: corte vacío o con muestra insuficiente ----------------
if resumen["n"] < C.N_MINIMO:
    orden = st.session_state.get("p3_orden", [])
    culpable = f"{C.FILTROS[orden[-1]]['nombre']}: {st.session_state[CLAVES[orden[-1]]]}" if orden else "—"
    k1, k2 = st.columns(2)
    k1.metric("Créditos en el segmento", f"{resumen['n']:,}", border=True)
    k2.metric("Incumplimiento", "—", border=True,
              help="Se muestra «—» y no 0%: sin registros suficientes no hay tasa, y un 0% se leería como riesgo nulo.")
    if resumen["n"] == 0:
        ui.estado_vacio("Ningún crédito cumple los filtros",
                        f"El último que aplicaste (**{culpable}**) dejó la selección en 0.",
                        [("Quitar último filtro", _quitar_ultimo), ("Restablecer filtros", _restablecer)], key="p3_vacio")
    else:
        ui.estado_vacio(f"Muestra insuficiente (n = {resumen['n']})",
                        f"Con menos de {C.N_MINIMO} créditos la tasa no tiene sustento y no se muestra. "
                        f"El último filtro aplicado fue **{culpable}**. Ejemplo real: solo 469 créditos tienen "
                        "antecedente de bancarrota; al cruzarlos con más filtros caen fácilmente bajo 30.",
                        [("Quitar último filtro", _quitar_ultimo), ("Restablecer filtros", _restablecer)], key="p3_chica")
    st.stop()

# --- KPIs: primero la entidad (la cartera), después sus métricas ------------------
particion = servicios.particion_riesgo(usuario.rol, filtros, corte_vigente)
alto = particion[particion["Categoría"] == "Alto riesgo"].iloc[0]
bajo = particion[particion["Categoría"] == "Bajo riesgo"].iloc[0]
incumplidos = int(particion["En incumplimiento"].sum())
tasa_base = servicios.modelo().tasa_base
texto_estado, color_estado, icono_estado = ui.estado_segmento(resumen["tasa"])

k1, k2, k3, k4 = st.columns([1.3, 1, 1, 1])
with k1, st.container(border=True):
    nombre = "Cartera completa" if not segmento else "Segmento: " + datos.describir_filtros(dict(filtros))
    st.markdown(f"**{nombre}**")
    st.markdown(f"### {resumen['n']:,} créditos")
    st.caption(f"{resumen['n'] / resumen['total']:.1%} de los {resumen['total']:,} créditos de la base")
with k2:
    dif = (resumen["tasa"] - tasa_base) * 100
    st.metric(f"{icono_estado} En incumplimiento", f"{incumplidos:,} clientes", border=True,
              delta=(f"{resumen['tasa']:.1%} · {'▲' if dif > 0.05 else '▼' if dif < -0.05 else '＝'} "
                     f"{dif:+.1f} pp") if segmento else f"{resumen['tasa']:.1%} del total",
              delta_color=("inverse" if abs(dif) >= 0.05 else "off") if segmento else "off",
              delta_arrow="off",
              help=f"Clientes con incumplimiento = 1 al cierre de la base real; el delta compara contra la cartera. Semáforo: {texto_estado.lower()} "
                   f"(🟢 ≤ {C.AMARILLO_SEGMENTO:.0%} · 🟡 hasta {C.TOLERANCIA_SEGMENTO:.0%} · 🔴 más de "
                   f"{C.TOLERANCIA_SEGMENTO:.0%}).")
with k3:
    st.metric(f"🔴 Alto riesgo* (PD ≥ {corte_vigente:.1%})", f"{int(alto['Créditos']):,}", border=True,
              delta=f"{alto['% de la cartera']:.1%} del {'segmento' if segmento else 'total'}", delta_color="off",
              delta_arrow="off")
with k4:
    st.metric(f"🟢 Bajo riesgo* (PD < {corte_vigente:.1%})", f"{int(bajo['Créditos']):,}", border=True,
              delta=f"{bajo['% de la cartera']:.1%} del {'segmento' if segmento else 'total'}", delta_color="off",
              delta_arrow="off")

# --- Partición (izq) · incumplimiento por una dimensión (der) -------------------
izq, der = st.columns([1.1, 1.2], gap="medium")
with izq, st.container(border=True):
    ui.titulo_grafica("¿Cuánto del incumplimiento cae en el alto riesgo?", "CALCULADO",
                      codigo="Partición de la cartera por riesgo")
    vista_part = particion.assign(**{"Categoría": particion["Categoría"].map(
        {"Alto riesgo": "🔴 Alto riesgo", "Bajo riesgo": "🟢 Bajo riesgo"})})
    st.dataframe(
        vista_part[["Categoría", "% de la cartera", "En incumplimiento", "% del incumplimiento total"]],
        hide_index=True,
        column_config={
            "Categoría": st.column_config.TextColumn("Categoría*"),
            "% de la cartera": st.column_config.ProgressColumn("% de créditos", format="percent", min_value=0,
                                                               max_value=1, color="blue"),
            "En incumplimiento": st.column_config.NumberColumn("Incumplidos", format="localized"),
            "% de la categoría en incumplimiento": st.column_config.NumberColumn("Tasa", format="percent"),
            "% del incumplimiento total": st.column_config.ProgressColumn("% del incumplimiento", format="percent",
                                                                          min_value=0, max_value=1, color="blue"),
        })
    st.markdown(
        f"Al cierre de la base, **{incumplidos:,}** clientes ({resumen['tasa']:.1%}) cayeron en incumplimiento. "
        f"El alto riesgo es **{alto['% de la cartera']:.1%}** de los créditos pero concentra "
        f"**{alto['% del incumplimiento total']:.1%}** del incumplimiento (tasa de "
        f"{alto['% de la categoría en incumplimiento']:.1%} vs {bajo['% de la categoría en incumplimiento']:.1%} "
        "en bajo riesgo).")
    st.caption(f"Alto riesgo = PD del modelo ≥ corte vigente ({corte_vigente:.1%}). «% de créditos» y «% del "
               "incumplimiento» suman 100% entre las dos categorías; la tasa se calcula dentro de cada una.")

with der, st.container(border=True):
    ui.titulo_grafica("¿Qué grupo supera la tolerancia?", "CALCULADO", codigo="G6 · una dimensión a la vez")
    if "p3_c1" not in st.session_state:
        st.session_state["p3_c1"] = C.CONTROLES["C1"]["defecto"]
    dimension = st.segmented_control(f"C1 · {C.CONTROLES['C1']['nombre']}", C.CONTROLES["C1"]["opciones"],
                                     key="p3_c1", required=True, help=ui.amarre("C1"))
    seg_col, fid_dim = DIMENSION[dimension]
    orden = C.SEGMENTOS[seg_col]["orden"]
    if fid_dim and dict(filtros)[fid_dim] != C.TODOS:
        orden = [dict(filtros)[fid_dim]]
    barras = servicios.tasa_cruzada(usuario.rol, filtros, seg_col, None)
    G.mostrar(G.g6_barras_grupo(barras, seg_col, orden, C.TOLERANCIA_SEGMENTO, referencia=tasa_base), key="g6")
    fuera = barras[barras["tasa"] > C.TOLERANCIA_SEGMENTO]
    st.caption(f"🟢 ≤ {C.AMARILLO_SEGMENTO:.0%} · 🟡 {C.AMARILLO_SEGMENTO:.0%}–{C.TOLERANCIA_SEGMENTO:.0%} · "
               f"🔴 > {C.TOLERANCIA_SEGMENTO:.0%} · ▲/▼ frente al {tasa_base:.1%} de la cartera · gris = n < {C.N_MINIMO}.")

# --- Corte propuesto (G7) y publicación a los analistas --------------------------
with st.container(border=True):
    ui.titulo_grafica("Si muevo el corte, ¿cuánta aprobación pierdo y cuánto incumplimiento evito?", "CALCULADO",
                      codigo="G7 · líneas de trade-off")
    curva, n_hold = servicios.curva_politica(usuario.rol, filtros)
    if curva.empty:
        ui.estado_vacio(f"El segmento tiene solo {n_hold} solicitudes en el holdout",
                        f"La curva se calcula con el 25% de la base que el modelo no vio. Con menos de {C.N_MINIMO} "
                        "casos no es confiable. Quita un filtro para ampliar el segmento.",
                        [("Quitar último filtro", _quitar_ultimo)], key="p3_curva")
    else:
        g, m = st.columns([1.6, 1], gap="medium")
        with m:
            clave_slider = "p3_c2_" + "_".join(f"{k}{v}" for k, v in sorted(segmento.items()))
            if clave_slider not in st.session_state:
                st.session_state[clave_slider] = corte_vigente * 100
            corte_pct = st.slider(f"C2 · {C.CONTROLES['C2']['nombre']}", 5.0, 30.0, step=0.5, format="%.1f%%",
                                  key=clave_slider, help=ui.amarre("C2"))
            corte = corte_pct / 100

            def _en(c):
                return curva.iloc[(curva["corte"] - c).abs().argmin()]

            actual, propuesto = _en(corte_vigente), _en(corte)
            igual = abs(corte - corte_vigente) < 0.004
            d_ap = (propuesto["aprobacion"] - actual["aprobacion"]) * 100
            d_def = (propuesto["default_aprobados"] - actual["default_aprobados"]) * 100
            a1, a2 = st.columns(2)
            a1.metric("Aprobación*", pct(propuesto["aprobacion"]),
                      delta="igual" if igual else f"{d_ap:+.1f} pp", delta_color="off" if igual else "normal",
                      delta_arrow="off" if igual else "auto")
            a2.metric("Incumpl. en aprobados*", pct(propuesto["default_aprobados"]),
                      delta="igual" if igual else f"{d_def:+.1f} pp", delta_color="off" if igual else "inverse",
                      delta_arrow="off" if igual else "auto")
            evitados = propuesto["defaults_evitados_1000"] - actual["defaults_evitados_1000"]
            perdidos = propuesto["buenos_rechazados_1000"] - actual["buenos_rechazados_1000"]
            st.caption(f"Por cada 1,000 solicitudes: {evitados:+.0f} incumplimientos evitados y {perdidos:+.0f} "
                       f"buenos clientes rechazados frente al corte vigente ({corte_vigente:.1%}). Holdout n = {n_hold:,}.")

            @st.dialog("Publicar corte a los analistas")
            def publicar() -> None:
                st.markdown(f"**Segmento:** {politica.describir(segmento)}")
                st.markdown(f"**Corte de PD:** {corte_vigente:.1%} → **{corte:.1%}** "
                            f"({'▼ más estricto' if corte < corte_vigente else '▲ más flexible'})")
                st.markdown(f"- Aprobación esperada: {pct(actual['aprobacion'])} → {pct(propuesto['aprobacion'])}\n"
                            f"- Incumplimiento en aprobados: {pct(actual['default_aprobados'])} → "
                            f"{pct(propuesto['default_aprobados'])}")
                st.caption("Al publicar, cada analista recibe un aviso en su bandeja con las solicitudes cuya "
                           "sugerencia cambia (por ejemplo, «aprobar → condicionar»).")
                if st.button("Confirmar y publicar", type="primary", icon=":material/campaign:"):
                    almacen.publicar_politica(segmento, politica.describir(segmento), corte_vigente, corte,
                                              resumen["n"], usuario.nombre_corto)
                    st.session_state["p3_toast"] = f"Corte publicado: {corte_vigente:.1%} → {corte:.1%}."
                    st.rerun()

            if st.button("Publicar este corte a los analistas", type="primary", icon=":material/campaign:",
                         disabled=igual, width="stretch",
                         help="Se valida y confirma antes de registrar; los analistas reciben una notificación."):
                publicar()
            propuesta = pd.DataFrame([{
                "fecha": date.today().isoformat(), "autor": usuario.nombre_corto,
                "segmento": politica.describir(segmento), "n_base": resumen["n"],
                "incumplimiento_observado": round(resumen["tasa"], 4), "n_holdout": n_hold,
                "corte_vigente": round(corte_vigente, 3), "corte_propuesto": round(corte, 3),
                "aprobacion_vigente": round(actual["aprobacion"], 4), "aprobacion_propuesta": round(propuesto["aprobacion"], 4),
                "incumplimiento_aprobados_vigente": round(actual["default_aprobados"], 4),
                "incumplimiento_aprobados_propuesto": round(propuesto["default_aprobados"], 4),
                "grupos_fuera_de_tolerancia": "; ".join(f"{dimension} {r[seg_col]} ({r['tasa']:.1%}, n={r['n']})"
                                                         for _, r in fuera.iterrows()) or "ninguno",
            }])
            st.download_button("Exportar propuesta (solo agregados)", propuesta.to_csv(index=False).encode("utf-8"),
                               file_name=f"propuesta_politica_{date.today():%Y%m%d}.csv", mime="text/csv",
                               icon=":material/download:", width="stretch")
        with g:
            G.mostrar(G.g7_tradeoff(curva, corte_vigente, corte), key="g7")

if mensaje := st.session_state.pop("p3_toast", None):
    st.toast(mensaje, icon=":material/campaign:")

# --- Políticas publicadas -----------------------------------------------------------
if len(activas):
    with st.expander(f"🔔 Cortes publicados vigentes ({len(activas)})", expanded=False):
        for _, pol in activas.iterrows():
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"**{politica.describir(pol['segmento'])}**: {pol['corte_anterior']:.1%} → "
                            f"**{pol['corte_nuevo']:.1%}** · {pol['autor']} · {pol['ts'][:16].replace('T', ' ')}")
                st.space("stretch")
                st.button("Revertir", key=f"rev_{pol['id']}", on_click=almacen.revertir_politica,
                          args=(int(pol["id"]), usuario.nombre_corto))

# --- Cruce de dos dimensiones: opcional, para no recargar la vista principal ------
with st.expander("Cruce avanzado: DTI × otra dimensión (mapa de calor)"):
    cruce = st.segmented_control("Cruzar el DTI con", ["Bancarrota", "Enganche", "Pagos fallidos", "LTV"],
                                 default="Bancarrota", key="p3_cruce", required=True)
    seg_cruce, fid_cruce = DIMENSION[cruce]
    cols_orden = C.SEGMENTOS[seg_cruce]["orden"]
    if fid_cruce and dict(filtros)[fid_cruce] != C.TODOS:
        cols_orden = [dict(filtros)[fid_cruce]]
    filas_dti = C.SEGMENTOS["SEG_DTI"]["orden"] if dict(filtros)["F3"] == C.TODOS else [dict(filtros)["F3"]]
    tabla = servicios.tasa_cruzada(usuario.rol, filtros, "SEG_DTI", seg_cruce)
    G.mostrar(G.g5_mapa_calor(tabla, filas_dti, cols_orden, "SEG_DTI", seg_cruce, C.TOLERANCIA_SEGMENTO), key="g5")
    cortes_dti = servicios.cortes_dti()
    st.caption(f"Filas = terciles de DTI* (cortes {cortes_dti[0]:.1%} y {cortes_dti[1]:.1%}). Borde rojo = supera "
               f"la tolerancia de {C.TOLERANCIA_SEGMENTO:.0%}. Gris = n < {C.N_MINIMO}.")

ui.pie_origen("Conteos y tasas de incumplimiento: datos reales de las 80,000 filas. PD, categorías de riesgo, "
              "segmentos, cortes y curvas: datos propios*.", marcas=("*",))
