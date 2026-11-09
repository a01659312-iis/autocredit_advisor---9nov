"""P4 · Monitor operativo · Luis (operación). Se vigila, no se consulta.
Decisión: escalar una alerta o descartarla con nota."""
from datetime import timedelta

import numpy as np
import pandas as pd
import streamlit as st

from src import almacen, auth, config as C, graficas as G, servicios, simulacion as S, ui
from src.modelo import calibracion, peso_variables, psi
from src.seguridad import enmascarar
from src.ui import pct

usuario = auth.exigir_acceso("P4")
ui.cabecera("P4", usuario, extra="Solo métricas y distribuciones agregadas")
modelo = servicios.modelo()

ORDEN_SEVERIDAD = {"frescura": 0, "psi": 1, "aprobacion": 2, "incompletos": 3, "pd": 4, "acuerdo": 5}
ACCIONES = {m["metrica"]: m["accion"] for m in C.METRICAS_MONITOR}


@st.dialog("Escalar alerta")
def dialogo_escalar(alerta: dict) -> None:
    st.markdown(f"**{alerta['texto']}**")
    st.caption(f"Acción sugerida por la tabla de vigilancia: {alerta['accion']}")
    tipo = st.radio("Tipo de escalamiento", ["Revisión 100% manual", "Incidente de datos (TI)",
                                             "Revisar corte con la gerente"])
    nota = st.text_area("Nota para el responsable y el siguiente turno", max_chars=400)
    if st.button("Confirmar escalamiento", type="primary"):
        if not nota.strip():
            st.error("Escribe una nota: quien recibe el escalamiento necesita saber qué viste.")
        else:
            almacen.guardar_alerta(alerta["fecha"], alerta["clave"], alerta["metrica"], alerta["valor"],
                                   "Escalada", tipo, nota.strip(), usuario.nombre_corto)
            st.rerun()


@st.dialog("Descartar con nota")
def dialogo_descartar(alerta: dict) -> None:
    st.markdown(f"**{alerta['texto']}**")
    razon = st.selectbox("¿Por qué no es un problema?", ["Efecto estacional (fin de mes, quincena)",
                                                         "Ya se atiende por otro canal",
                                                         "Falso positivo de la métrica", "Otro"])
    nota = st.text_area("Nota (queda visible para el siguiente turno)", max_chars=400)
    if st.button("Descartar alerta", type="primary"):
        if not nota.strip():
            st.error("Descartar sin nota no está permitido: el siguiente turno vería la alerta cerrada sin saber por qué.")
        else:
            almacen.guardar_alerta(alerta["fecha"], alerta["clave"], alerta["metrica"], alerta["valor"],
                                   "Descartada", razon, nota.strip(), usuario.nombre_corto)
            st.rerun()


def tabla_acuerdo(f: pd.DataFrame, reales: pd.DataFrame, hoy) -> pd.DataFrame:
    conteo = f.groupby(["dia", "categoria"]).size().unstack(fill_value=0)
    for cat in G.CATEGORIAS_ACUERDO:
        if cat not in conteo:
            conteo[cat] = 0
    if len(reales):
        r = reales[reales["categoria"].isin(G.CATEGORIAS_ACUERDO)]["categoria"].value_counts()
        for cat, n in r.items():
            conteo.loc[hoy, cat] = conteo.loc[hoy, cat] + n if hoy in conteo.index else n
    conteo = conteo.fillna(0)
    proporciones = conteo[G.CATEGORIAS_ACUERDO].div(conteo[G.CATEGORIAS_ACUERDO].sum(axis=1), axis=0)
    dias_es = ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"]
    proporciones["dia_txt"] = ["Hoy" if d == hoy else f"{dias_es[d.weekday()]} {d.day}/{d.month}" for d in proporciones.index]
    proporciones["n"] = conteo[G.CATEGORIAS_ACUERDO].sum(axis=1).astype(int)
    return proporciones.reset_index()


@st.fragment(run_every=timedelta(minutes=C.REFRESCO_MIN))
def monitor() -> None:
    escenario = st.session_state.get("escenario", "drift")
    reloj, nota_reloj = S.reloj_operativo()
    reloj = reloj.replace(second=0, microsecond=0)
    carga = S.ultima_carga(reloj, escenario)
    min_sin_carga = (reloj - carga).total_seconds() / 60
    viejo = min_sin_carga > C.FRESCURA_ROJO_MIN
    hoy = reloj.date()

    # --- Frescura siempre visible ---------------------------------------------
    color = "green" if min_sin_carga <= C.FRESCURA_AMBAR_MIN else ("orange" if not viejo else "red")
    icono = "🟢" if color == "green" else ("🟡" if color == "orange" else "🔴")
    c_ven, c_fre = st.columns([1, 1.4], vertical_alignment="bottom")
    with c_ven:
        ventana = ui.filtro("F7", "p4_f7", widget="segmented", required=True)
    with c_fre, st.container(horizontal=True, vertical_alignment="center", horizontal_alignment="right"):
        st.badge(f"{icono} Última carga {carga:%H:%M}** (hace {int(min_sin_carga)} min)", color=color,
                 icon=":material/schedule:")
        st.badge(f"Refresco cada {C.REFRESCO_MIN} min", color="gray")
    ui.amarre_corto("F7")
    if nota_reloj:
        st.caption(nota_reloj)
    f = servicios.flujo_monitor(usuario.rol, escenario, reloj.isoformat())
    ven = S.recortar_ventana(f, ventana, reloj)
    prev = S.ventana_anterior(f, ventana, reloj)
    diario = f if ventana == "7 días" else f[f["dia"] == hoy]
    reales = almacen.decisiones(fecha=hoy.isoformat())

    if ven.empty:
        ui.estado_vacio("No hay solicitudes en esta ventana",
                        "La ventana elegida no tiene cargas todavía (p. ej., la primera hora del día). "
                        "Usa «Hoy» o «7 días».", [("Ver hoy", lambda: st.session_state.update(p4_f7="Hoy"))],
                        key="p4_vacio")
        return

    # --- Métricas --------------------------------------------------------------
    aprob = ven["analista_aprueba"].mean()
    aprob_prev = prev["analista_aprueba"].mean() if len(prev) else np.nan
    pd_prom = ven["PD"].mean()
    pd_prev = prev["PD"].mean() if len(prev) else np.nan
    acuerdo_tab = tabla_acuerdo(diario, reales, hoy)
    fila_hoy = acuerdo_tab[acuerdo_tab["dia"] == hoy] if ventana != "7 días" else acuerdo_tab
    if ventana == "7 días":
        pesos = acuerdo_tab["n"]
        acuerdo = float((acuerdo_tab[G.CATEGORIAS_ACUERDO[0]] * pesos).sum() / pesos.sum())
    else:
        acuerdo = float(fila_hoy[G.CATEGORIAS_ACUERDO[0]].iloc[0]) if len(fila_hoy) else np.nan
    psis = {v: psi(servicios.distribucion_entrenamiento(usuario.rol, v), diario[v].to_numpy()) for v in C.VARIABLES_DRIFT}
    var_peor = max(psis, key=lambda v: -1 if np.isnan(psis[v]) else psis[v])
    incompletos = ven["incompleto"].mean()

    def estado(valor, lo=None, hi=None, margen=0.0):
        """Verde dentro de la banda; amarillo a menos de `margen` del borde; rojo fuera."""
        if viejo:
            return "sin_datos"
        if (lo is not None and valor < lo) or (hi is not None and valor > hi):
            return "alerta"
        if (lo is not None and valor < lo + margen) or (hi is not None and valor > hi - margen):
            return "vigilar"
        return "ok"

    est_aprob = estado(aprob, *C.BANDA_APROBACION, margen=0.02)
    est_pd = estado(pd_prom, *C.BANDA_PD_PROMEDIO, margen=0.01)
    est_acuerdo = estado(acuerdo, lo=C.META_ACUERDO, margen=0.03)
    est_psi = "sin_datos" if viejo else ("alerta" if psis[var_peor] > C.UMBRAL_PSI_ALERTA else
                                         "vigilar" if psis[var_peor] > C.UMBRAL_PSI_VIGILAR else "ok")
    est_inc = estado(incompletos, hi=C.UMBRAL_INCOMPLETOS, margen=0.01)

    # --- Alertas arriba, ordenadas por gravedad ---------------------------------
    alertas = []
    fecha = hoy.isoformat()
    if est_psi == "alerta":
        alertas.append({"clave": f"psi_{var_peor}", "tipo": "psi", "metrica": "Drift (PSI)",
                        "texto": f"Drift de {C.ETIQUETAS[var_peor]}: PSI {psis[var_peor]:.2f} (> {C.UMBRAL_PSI_ALERTA})",
                        "valor": f"{psis[var_peor]:.2f}", "accion": ACCIONES["Drift (PSI) de DTI, LTV y PTI"]})
    if est_aprob == "alerta":
        alertas.append({"clave": "aprobacion", "tipo": "aprobacion", "metrica": "Tasa de aprobación",
                        "texto": f"Aprobación {pct(aprob)} fuera de la banda {C.BANDA_APROBACION[0]:.0%}–{C.BANDA_APROBACION[1]:.0%} ({ventana.lower()})",
                        "valor": pct(aprob), "accion": ACCIONES["Tasa de aprobación"]})
    if est_inc == "alerta":
        alertas.append({"clave": "incompletos", "tipo": "incompletos", "metrica": "Datos incompletos",
                        "texto": f"{pct(incompletos)} de solicitudes con datos clave incompletos (> {C.UMBRAL_INCOMPLETOS:.0%})",
                        "valor": pct(incompletos), "accion": ACCIONES["Solicitudes con datos clave incompletos"]})
    if est_pd == "alerta":
        alertas.append({"clave": "pd", "tipo": "pd", "metrica": "PD promedio",
                        "texto": f"PD promedio {pct(pd_prom)} fuera de 13.5% ± 3 pp",
                        "valor": pct(pd_prom), "accion": ACCIONES["PD promedio de las solicitudes"]})
    if est_acuerdo == "alerta":
        alertas.append({"clave": "acuerdo", "tipo": "acuerdo", "metrica": "Acuerdo modelo–analista",
                        "texto": f"Acuerdo modelo–analista {pct(acuerdo)} (meta ≥ {C.META_ACUERDO:.0%})",
                        "valor": pct(acuerdo), "accion": ACCIONES["Acuerdo modelo–analista"]})
    alertas.sort(key=lambda a: ORDEN_SEVERIDAD[a["tipo"]])
    atendidas = almacen.alertas_atendidas(fecha)

    # --- Semáforos ---------------------------------------------------------------
    sufijo = f" · dato de las {carga:%H:%M}" if viejo else ""
    s1, s2, s3, s4, s5 = st.columns(5)
    with s1:
        delta = f"{(aprob - aprob_prev) * 100:+.1f} pp vs. {'hora previa' if ventana == 'Última hora' else 'ayer'}" \
            if ventana != "7 días" and not np.isnan(aprob_prev) else None
        ui.semaforo("Tasa de aprobación", pct(aprob), est_aprob,
                    f"Banda {C.BANDA_APROBACION[0]:.0%}–{C.BANDA_APROBACION[1]:.0%} · cada hora{sufijo}", delta,
                    delta_color="off")
    with s2:
        ui.semaforo("PD promedio", pct(pd_prom), est_pd, f"Base 13.5% ± 3 pp · cada hora{sufijo}",
                    delta=f"{(pd_prom - pd_prev) * 100:+.1f} pp vs. {'hora previa' if ventana == 'Última hora' else 'ayer'}"
                    if ventana != "7 días" and not np.isnan(pd_prev) else None, delta_color="inverse")
    with s3:
        ui.semaforo("Acuerdo con el modelo", pct(acuerdo), est_acuerdo,
                    f"Meta ≥ {C.META_ACUERDO:.0%} · diario · incluye {len(reales)} decisiones reales de hoy{sufijo}")
    with s4:
        ui.semaforo(f"Drift de {C.ETIQUETAS[var_peor].split(' (')[-1].rstrip(')')} (PSI)", f"{psis[var_peor]:.2f}", est_psi,
                    "Mayor de: " + " · ".join(f"{C.ETIQUETAS[v].split('(')[-1].rstrip(')')} {psis[v]:.2f}" for v in C.VARIABLES_DRIFT)
                    + f" · umbral {C.UMBRAL_PSI_ALERTA}{sufijo}", origen_tag="CALCULADO")
    with s5:
        ui.semaforo("Datos incompletos", pct(incompletos), est_inc,
                    f"Base real 0% · alerta > {C.UMBRAL_INCOMPLETOS:.0%} · cada carga{sufijo}")

    if viejo:
        with st.container(border=True):
            st.error(f"**Sin carga nueva desde las {carga:%H:%M}** (hace {int(min_sin_carga)} min; tolerancia "
                     f"{C.FRESCURA_ROJO_MIN} min). Lo que ves **no** es el estado actual: los semáforos pasan a gris "
                     "y las alertas automáticas se suspenden para no disparar falsas alarmas.",
                     icon=":material/cloud_off:")
            with st.container(horizontal=True):
                if st.button("Reintentar carga", type="primary", icon=":material/refresh:"):
                    st.cache_data.clear()
                    if escenario == "atrasada":
                        st.toast("El reintento no trajo datos nuevos: la fuente sigue sin responder.", icon=":material/error:")
                ya_avisado = (atendidas["clave"] == "frescura").any() if len(atendidas) else False
                if st.button("Avisar a TI", icon=":material/support_agent:", disabled=ya_avisado):
                    almacen.guardar_alerta(fecha, "frescura", "Frescura de datos", f"{int(min_sin_carga)} min",
                                           "Escalada", "Incidente de datos (TI)",
                                           f"Última carga {carga:%H:%M}; sin datos nuevos.", usuario.nombre_corto)
                    st.rerun()
                if ya_avisado:
                    st.caption("TI ya fue avisado; queda registrado en la bitácora del turno.")
    elif alertas:
        for a in alertas:
            a["fecha"] = fecha
            previa = atendidas[atendidas["clave"] == a["clave"]] if len(atendidas) else pd.DataFrame()
            with st.container(border=True, horizontal=True, vertical_alignment="center"):
                if len(previa):
                    p = previa.iloc[0]
                    st.badge(p["accion"], color="gray", icon=":material/task_alt:")
                    st.markdown(f"~~{a['texto']}~~ · {p['tipo']} por {p['usuario']} a las {p['ts'][11:16]}: _{p['nota']}_")
                else:
                    st.badge("Alerta", color="red", icon=":material/warning:")
                    st.markdown(f"**{a['texto']}** · {a['accion']}")
                    st.space("stretch")
                    if st.button("Escalar", key=f"esc_{a['clave']}", type="primary"):
                        dialogo_escalar(a)
                    if st.button("Descartar con nota", key=f"desc_{a['clave']}"):
                        dialogo_descartar(a)
    else:
        st.success("Todas las métricas en banda. Sin alertas activas.", icon=":material/check_circle:")

    # --- Gráficas -----------------------------------------------------------------
    g1, g2, g3 = st.columns(3, gap="medium")
    with g1, st.container(border=True):
        ui.titulo_grafica("¿La aprobación sigue dentro de la banda?", "SIMULADO", codigo="G8 · línea con banda")
        serie = S.serie_aprobacion(f, hoy)
        G.mostrar(G.g8_linea_banda(serie, C.BANDA_APROBACION, hoy, gris=viejo), key="g8")
        st.caption("Aprobación de la última hora móvil, un punto cada 15 min. Franja verde = banda esperada; "
                   "puntos rojos = fuera de banda.")
    with g2, st.container(border=True):
        ui.titulo_grafica(f"¿Cambió la población que llega? ({C.ETIQUETAS[var_peor].split('(')[-1].rstrip(')')})",
                          "REAL", "SIMULADO", codigo="G9 · histogramas")
        G.mostrar(G.g9_histogramas(servicios.distribucion_entrenamiento(usuario.rol, var_peor),
                                   diario[var_peor].to_numpy(), var_peor, psis[var_peor], gris=viejo), key="g9")
        st.caption(f"Se muestra la variable con mayor PSI* ({psis[var_peor]:.2f}). Base: entrenamiento (real); "
                   "ventana actual: simulada**.")
    with g3, st.container(border=True):
        ui.titulo_grafica("¿Analistas y modelo se están separando?", "SIMULADO", "REAL en bitácora",
                          codigo="G10 · barras 100% apiladas")
        G.mostrar(G.g10_apiladas(tabla_acuerdo(f, reales, hoy)), key="g10")
        st.caption("Rojo = el analista aprueba lo que el modelo rechaza (riesgo); azul = rechaza lo que aprueba "
                   "(negocio perdido). «Hoy» suma las decisiones reales guardadas en P2.")


tab_monitor, tab_salud, tab_bitacora, tab_vigilo = st.tabs(
    ["Monitor", "Salud del modelo (mensual)", "Bitácora del turno", "¿Qué vigilo y cada cuánto?"])


with tab_monitor:
    monitor()

with tab_salud:
    m = modelo.metricas
    ui.titulo_grafica("¿El modelo sigue separando buenos de malos pagadores?", "CALCULADO", "REAL")
    estado_auc = "ok" if m["auc"] >= C.AUC_MINIMO else "alerta"
    c1, c2, c3, c4 = st.columns(4)
    with c1:
        ui.semaforo("ROC-AUC (holdout)", f"{m['auc']:.3f}", estado_auc, f"Mínimo {C.AUC_MINIMO} · mensual",
                    origen_tag="CALCULADO")
    c2.metric("KS*", f"{m['ks']:.3f}", border=True, help="Máxima separación entre buenos y malos.")
    c3.metric(f"Recall de incumplimiento al corte {C.CORTE_PD:.0%}*", pct(m["recall_default"]), border=True,
              help="De los créditos que sí cayeron en incumplimiento, cuántos habría rechazado el modelo.")
    c4.metric("Aprobación / incumplimiento en aprobados*", f"{pct(m['aprobacion'])} / {pct(m['default_aprobados'])}",
              border=True)
    a, b = st.columns([1.2, 1], gap="medium")
    with a, st.container(border=True):
        ui.titulo_grafica("Incumplimiento esperado vs. observado por decil", "CALCULADO", "REAL", codigo="Calibración")
        cal = calibracion(modelo.holdout["PD"].to_numpy(), modelo.holdout[C.OBJETIVO].to_numpy())
        G.mostrar(G.calibracion(cal), key="g_cal")
        st.caption(f"Holdout de {m['n']:,} créditos (25% de la base) que el modelo no vio. Si las barras se "
                   "separan mes a mes, el modelo necesita recalibración.")
    with b, st.container(border=True):
        ui.titulo_grafica("¿Qué variables pesan más en el modelo?", "CALCULADO")
        pesos = peso_variables(modelo)
        coef = modelo.coeficientes.assign(
            **{"Peso": lambda d: d["variable"].map(pesos),
               "Efecto de +1 desv. estándar": lambda d: d["odds_ratio_1sd"].map(lambda x: f"×{x:.2f} en momios"),
               "Dirección": lambda d: np.where(d["coef_std"] > 0, "▲ sube el riesgo", "▼ baja el riesgo"),
               "Significancia (z)": lambda d: d["z"].map(lambda z: f"{abs(z):.1f} ✓" if abs(z) > 1.96 else f"{abs(z):.1f}")})
        st.dataframe(coef[["etiqueta", "Peso", "Dirección", "Efecto de +1 desv. estándar", "Significancia (z)"]]
                     .rename(columns={"etiqueta": "Variable"}), hide_index=True)
        st.caption("★★★ = variables más significativas: uso de crédito revolvente, endeudamiento (DTI), enganche y "
                   "pagos fallidos. ✓ = significativa al 95% (|z| > 1.96).")
        auc_con = servicios.auc_con_variable_excluida()
        st.caption(f"Excluida por equidad: FINANCIAL_LITERACY_SCORE. AUC con ella {auc_con:.4f} vs. sin ella "
                   f"{m['auc']:.4f} (diferencia {(auc_con - m['auc']):+.4f}). {C.EXCLUIDAS_DEL_MODELO['FINANCIAL_LITERACY_SCORE']}")

with tab_bitacora:
    st.markdown("**Alertas atendidas** · las notas quedan visibles para el siguiente turno")
    bit = almacen.bitacora_alertas()
    if bit.empty:
        st.caption("Aún no hay alertas escaladas o descartadas.")
    else:
        st.dataframe(bit[["ts", "metrica", "valor", "accion", "tipo", "nota", "usuario"]].rename(
            columns={"ts": "Hora", "metrica": "Métrica", "valor": "Valor", "accion": "Acción", "tipo": "Tipo",
                     "nota": "Nota", "usuario": "Responsable"}), hide_index=True)
    st.markdown("**Decisiones de analistas** · folio enmascarado, sin analista ni texto libre (matriz F)")
    dec = almacen.decisiones()
    if dec.empty:
        st.caption("Aún no hay decisiones registradas. Se llenan cuando un analista guarda en P2.")
    else:
        st.dataframe(pd.DataFrame({
            "Hora": dec["ts"], "Folio": dec["folio"].map(enmascarar), "Decisión": dec["decision"],
            "Sugerencia del modelo": dec["sugerencia"], "Categoría": dec["categoria"],
            "Motivo (catálogo)": dec["motivo"].fillna("—"), "PD": dec["pd"].map(pct),
        }), hide_index=True)

with tab_vigilo:
    st.markdown("Adrián y Mariana abren el tablero con una pregunta y lo cierran al tener la respuesta. Luis no trae "
                "pregunta: deja el monitor abierto y la pantalla le dice qué cambió.")
    st.dataframe(pd.DataFrame(C.METRICAS_MONITOR).rename(columns={
        "metrica": "Qué vigila", "banda": "Umbral / banda", "frecuencia": "Frecuencia", "accion": "Si se sale",
        "origen": "Origen"}).assign(Origen=lambda d: d["Origen"].map(lambda o: ui.NOMBRE_ORIGEN.get(o, o))),
        hide_index=True)
    st.caption("Ritmo: la pantalla se refresca sola cada 15 min, Luis la revisa activamente cada hora y cierra el día "
               "a las 18:00. Umbrales propuestos por el equipo; se calibran con datos reales.")

ui.pie_origen("Los indicadores operativos son simulados** hasta que existan fecha de solicitud, decisión del "
              "analista y fecha de carga; se construyen con filas reales del holdout y la PD propia* del modelo.")
