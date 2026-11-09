"""P2 · Ficha de solicitud · Adrián (analista).
Decisión: aprobar, condicionar o rechazar esta solicitud en menos de 5 minutos.

Flujo (recomendación 4): 1 validar datos → 2 revisar riesgo contra el corte y la media
→ 3 decidir → 4 validar la decisión y, solo después de confirmarla, registrarla."""
import math
import time

import pandas as pd
import streamlit as st

from src import almacen, auth, config as C, datos, graficas as G, servicios, ui
from src.modelo import evaluar, pd_con_enganche, peso_variables
from src.seguridad import MATRIZ_DATOS, OCULTO, aplicar_politica_fila
from src.simulacion import texto_hace
from src.ui import pct

usuario = auth.exigir_acceso("P2")
modelo = servicios.modelo()
cola, originales = servicios.cola_analista(usuario)
ui.cabecera("P2", usuario)


def _ir_bandeja():
    st.session_state.pop("folio_actual", None)


# --- Recorrido de error 1: llegar sin solicitud elegida -------------------------
folio = st.session_state.get("folio_actual")
if not folio:
    ui.estado_vacio("Elige una solicitud en tu bandeja",
                    "La ficha muestra una solicitud a la vez. Ábrela desde P1, donde están ordenadas por PD.",
                    key="p2_sin_folio")
    st.page_link("vistas/p1_bandeja.py", label="Ir a la bandeja", icon=":material/inbox:")
    st.stop()

# --- Recorrido de error 2: folio que no es suyo (autorización por ANALISTA_ID) --
if folio not in set(cola["FOLIO"]):
    st.error(f"La solicitud {folio} no está asignada a tu ANALISTA_ID ({usuario.analista_id}). "
             "No se muestra ningún dato.", icon=":material/lock:")
    st.page_link("vistas/p1_bandeja.py", label="Volver a mi bandeja", icon=":material/inbox:")
    st.stop()

registro = cola[cola["FOLIO"] == folio].iloc[0]
corte = float(registro["CORTE"])
fila = aplicar_politica_fila(usuario.rol, registro.to_dict())  # solo columnas permitidas al analista
ev = evaluar(modelo, fila, corte=corte)
estado = registro["ESTADO_SOLICITUD"]
st.session_state.setdefault(f"inicio_{folio}", time.time())
demo = not auth.modo_oidc()
clave = folio
k_dec, k_eng, k_mot, k_txt = (f"dec_{clave}", f"eng_{clave}", f"mot_{clave}", f"txt_{clave}")

# --- Encabezado ---------------------------------------------------------------------
with st.container(horizontal=True, vertical_alignment="center"):
    if st.button("Bandeja", icon=":material/arrow_back:", on_click=_ir_bandeja, type="tertiary"):
        st.switch_page("vistas/p1_bandeja.py")
    st.markdown(f"### Solicitud {folio}")
    st.badge(f"recibida {texto_hace(registro['RECIBIDA_MIN'])}**", color="gray")
    st.badge(f"{C.ICONO_ESTADO[estado]} {estado}**",
             color={"Pendiente": "blue", "En espera de documento": "orange"}.get(estado, "green"))
    if ev.nivel:
        st.badge(f"{C.ICONO_NIVEL[ev.nivel]} riesgo {ev.nivel.lower()}*",
                 color={"Alto": "red", "Medio": "orange", "Bajo": "green"}[ev.nivel])

if st.session_state.pop("aviso_regreso", False):
    st.info("Regresaste a la solicitud que tenías abierta cuando expiró la sesión; lo que habías capturado "
            "está abajo.", icon=":material/history:")

# Aviso de cambio de política para ESTA solicitud.
if registro["SUGERENCIA_GENERAL"] != registro["SUGERENCIA"] or abs(corte - C.CORTE_PD) > 1e-9:
    antes, ahora = registro["SUGERENCIA_GENERAL"], registro["SUGERENCIA"]
    cambio = (f"la sugerencia del modelo pasó de {C.ICONO_SUGERENCIA[antes]} {antes.lower()} a "
              f"**{C.ICONO_SUGERENCIA[ahora]} {ahora.lower()}**" if antes != ahora
              else f"la sugerencia no cambia ({C.ICONO_SUGERENCIA[ahora]} {ahora.lower()})")
    st.warning(f"**La gerencia publicó un corte para el segmento de esta solicitud:** {C.CORTE_PD:.1%} → "
               f"**{corte:.1%}**; {cambio}.", icon=":material/campaign:")


def _pedir_documento():
    almacen.poner_estado(folio, usuario.analista_id, "En espera de documento")
    st.toast(f"{folio} pasó a «En espera de documento».", icon=":material/mail:")


def _llego_documento():
    almacen.registrar_documento(folio)
    almacen.poner_estado(folio, usuario.analista_id, "Pendiente")
    st.toast("Llegó el documento: la PD se recalculó con el dato real.", icon=":material/task_alt:")


# --- Pasos del proceso en cajas -------------------------------------------------------
datos_ok = not (ev.invalidos or ev.imputados or ev.fuera_rango)
decision_actual = st.session_state.get(k_dec)
pasos = [
    ("1 · Validar datos", "✅ completos" if datos_ok else ("⛔ " + ev.calidad.lower()), "green" if datos_ok else "red"),
    ("2 · Revisar riesgo", f"PD {pct(ev.pd)} vs corte {corte:.1%}" if ev.pd is not None else "sin PD",
     "green" if ev.pd is not None else "gray"),
    ("3 · Decidir", (f"{decision_actual}" + (" · contradice al modelo" if decision_actual != ev.sugerencia else ""))
     if decision_actual else "pendiente",
     ("green" if decision_actual == ev.sugerencia else "orange") if decision_actual else "gray"),
    ("4 · Validar y registrar", "✅ registrada" if estado == "Resuelta hoy" else "pendiente",
     "green" if estado == "Resuelta hoy" else "gray"),
]
for col, (titulo, texto, color) in zip(st.columns(4, gap="small"), pasos):
    with col, st.container(border=True):
        st.markdown(f"**{titulo}**  \n:{color}[{texto}]")

# --- Paso 1: estados de excepción (se valida antes de evaluar) ------------------------
if ev.invalidos:
    st.error(f"Dato imposible en {', '.join(C.ETIQUETAS[v] for v in ev.invalidos)}: está fuera de los límites "
             "válidos, así que **no se calcula PD**. Pide el documento o rechaza con motivo.",
             icon=":material/error:")
if ev.imputados:
    with st.container(border=True):
        st.warning(
            f"**Esta solicitud llegó sin {', '.join(C.ETIQUETAS[v] for v in ev.imputados)}.** Se imputó la mediana "
            "de entrenamiento y la PD puede estar sesgada. «Aprobar» y «Condicionar» quedan deshabilitados "
            "mientras un dato clave siga imputado.", icon=":material/report:")
        with st.container(horizontal=True):
            st.button("Pedir documento (pasa a En espera)", on_click=_pedir_documento, type="primary",
                      disabled=estado == "En espera de documento", icon=":material/mail:")
            if demo:
                st.button("Simular que llegó el documento", on_click=_llego_documento, icon=":material/science:")
if ev.fuera_rango:
    with st.container(border=True):
        rangos = "; ".join(f"{C.ETIQUETAS[v]} = {datos.formatear(v, fila[v])} (entrenado entre "
                           f"{datos.formatear(v, modelo.rango[v][0])} y {datos.formatear(v, modelo.rango[v][1])})"
                           for v in ev.fuera_rango)
        st.warning(f"**Dato fuera del rango con el que se entrenó el modelo:** {rangos}. La PD es una "
                   "extrapolación, por eso el modelo **no emite recomendación**: decide con revisión manual "
                   "y registra el motivo.", icon=":material/warning:")
        with st.container(horizontal=True):
            st.button("Pedir avalúo / documento", on_click=_pedir_documento, type="primary",
                      disabled=estado == "En espera de documento", icon=":material/mail:")
            if demo:
                st.button("Simular documento corregido", on_click=_llego_documento, icon=":material/science:")
if estado == "En espera de documento":
    st.info("Esta solicitud espera un documento. Cuando llegue, la PD se recalcula y se habilita la decisión.",
            icon=":material/hourglass_top:")
if ev.pd is None:
    st.stop()

valores = {v: (float(fila[v]) if pd.notna(fila[v]) else modelo.medianas[v]) for v in modelo.variables}

# --- Fila principal: riesgo + benchmark (izq) · decisión (der) -----------------------
izq, der = st.columns([1.55, 1], gap="medium")

with izq, st.container(border=True):
    ui.titulo_grafica("Paso 2 · ¿Está arriba o abajo del corte y de la media?", "CALCULADO",
                      codigo="G1 · barra con corte y media de la cartera")
    veredicto = {
        "Aprobar": ("El modelo sugiere aprobar", "green", ":material/check:"),
        "Condicionar": (f"El modelo sugiere condicionar: enganche ≥ {ev.enganche_requerido:.1%}"
                        if ev.enganche_requerido else "", "orange", ":material/tune:"),
        "Rechazar": ("El modelo sugiere rechazar: ni con 31% de enganche baja del corte", "red", ":material/close:"),
        "Revisión manual": ("Sin recomendación: dato fuera de rango", "gray", ":material/help:"),
    }[ev.sugerencia]
    with st.container(horizontal=True, vertical_alignment="center"):
        st.markdown(f"## PD {ev.pd:.1%}\\*")
        st.badge(veredicto[0], color=veredicto[1], icon=veredicto[2])
    G.mostrar(G.g1_barra_corte(ev.pd, corte, modelo.tasa_base), key="g1")

    # Benchmark: la solicitud contra la media de la cartera (no solo el número absoluto).
    # Benchmark: la solicitud contra la media de la cartera (no solo el número absoluto).
    st.markdown("**Esta solicitud frente a la media de la cartera** (80,000 créditos)")
    filas_bm = [("Prob. de incumplimiento (PD)*", ev.pd, modelo.tasa_base, 1)]
    filas_bm += [(C.ETIQUETAS[v], valores[v], modelo.media_cartera[v], C.SENTIDO_RIESGO[v])
                 for v in C.VARIABLES_BENCHMARK]
    bm = pd.DataFrame([{
        "Indicador": nombre, "Solicitud": pct(val), "Media de la cartera": pct(media),
        "Vs. media": (f"{'🔴' if (val - media) * sentido > 0 else '🟢'} {'▲' if val > media else '▼'} "
                      f"{(val - media) * 100:+.1f} pp"),
    } for nombre, val, media, sentido in filas_bm])
    st.dataframe(bm, hide_index=True, column_config={
        "Vs. media": st.column_config.TextColumn("Vs. media", help="🔴 más riesgo que la media · 🟢 menos riesgo.")})
    st.caption("▲/▼ = por encima o por debajo de la media. 🔴 = esa diferencia sube el riesgo; 🟢 = lo baja "
               "(más enganche baja el riesgo; más deuda lo sube).")

# --- Decisión ------------------------------------------------------------------
# Restaurar borrador (p. ej., tras una sesión expirada).
if k_dec not in st.session_state:
    borrador = almacen.leer_borrador(usuario.email, folio)
    if borrador:
        for k, v in zip((k_dec, k_eng, k_mot, k_txt), ("decision", "enganche", "motivo", "texto")):
            if borrador.get(v) is not None:
                st.session_state[k] = borrador[v]
        st.toast("Recuperamos lo que habías capturado en esta solicitud.", icon=":material/history:")


def _guardar_borrador():
    almacen.guardar_borrador(usuario.email, folio, {
        "decision": st.session_state.get(k_dec), "enganche": st.session_state.get(k_eng),
        "motivo": st.session_state.get(k_mot), "texto": st.session_state.get(k_txt)})


def _siguiente_pendiente():
    resto = cola[(cola["ESTADO_SOLICITUD"] == "Pendiente") & (cola["FOLIO"] != folio)]
    resto = resto.sort_values(["PD", "RECIBIDA_MIN"], ascending=[False, False])
    return resto["FOLIO"].iloc[0] if len(resto) else None


@st.dialog("Confirmar y registrar la decisión")
def confirmar(resumen: dict) -> None:
    """Paso 4: la decisión ya pasó la validación; solo se registra al confirmar."""
    st.markdown(f"**Solicitud {resumen['folio']}**")
    st.markdown(
        f"- Decisión: **{C.ICONO_SUGERENCIA[resumen['decision']]} {resumen['decision']}**"
        + (f" con enganche de {resumen['enganche_condicion']:.1%}" if resumen.get("enganche_condicion") else "")
        + f"\n- Sugerencia del modelo: {C.ICONO_SUGERENCIA[resumen['sugerencia']]} {resumen['sugerencia']} "
        f"(PD {resumen['pd']:.1%} · corte {resumen['corte']:.1%})"
        + f"\n- {'⚠️ Contradice al modelo' if resumen['contradice'] else '✅ Coincide con el modelo'}"
        + (f"\n- Motivo: {resumen['motivo']}" if resumen.get("motivo") else "")
        + (f" — {resumen['motivo_texto']}" if resumen.get("motivo_texto") else ""))
    st.caption("Al confirmar se registra en la bitácora (alimenta el acuerdo modelo–analista que vigila Luis) y "
               "se abre la siguiente solicitud pendiente de mayor PD.")
    c1, c2 = st.columns(2)
    if c1.button("Confirmar y registrar", type="primary", icon=":material/save:", width="stretch"):
        almacen.guardar_decision(resumen | {
            "duracion_seg": time.time() - st.session_state.get(f"inicio_{folio}", time.time())})
        siguiente = _siguiente_pendiente()
        st.session_state["toast_registro"] = f"{folio}: {resumen['decision']} registrada."
        if siguiente:
            st.session_state["folio_actual"] = siguiente
        else:
            st.session_state.pop("folio_actual", None)
        st.rerun()
    if c2.button("Volver a editar", width="stretch"):
        st.rerun()


if mensaje := st.session_state.pop("toast_registro", None):
    st.toast(mensaje, icon=":material/task_alt:")

with der, st.container(border=True):
    st.markdown("**Pasos 3 y 4 · Tu decisión**")
    if estado == "Resuelta hoy":
        hecho = almacen.decisiones(analista_id=usuario.analista_id)
        hecho = hecho[hecho["folio"] == folio].head(1)
        if len(hecho):
            h = hecho.iloc[0]
            st.success(f"Ya resolviste esta solicitud: **{h['decision']}** a las {h['ts'][11:16]}"
                       + (f" · motivo: {h['motivo']}" if h["motivo"] else ""), icon=":material/task_alt:")
        st.page_link("vistas/p1_bandeja.py", label="Volver a la bandeja", icon=":material/inbox:")
    else:
        bloqueado = ev.bloquea_aprobar or estado == "En espera de documento"
        opciones = ["Rechazar"] if bloqueado else C.DECISIONES
        if bloqueado:
            st.caption("Solo «Rechazar» está disponible mientras falte un dato clave o la solicitud espere documento.")
        if st.session_state.get(k_dec) not in opciones:
            st.session_state.pop(k_dec, None)
        decision = st.segmented_control("Decisión", opciones, key=k_dec, on_change=_guardar_borrador,
                                        format_func=lambda d: f"{C.ICONO_SUGERENCIA[d]} {d}",
                                        label_visibility="collapsed")
        pd_final = ev.pd
        enganche = None
        if decision == "Condicionar":
            actual = float(valores["DOWN_PAYMENT_PCT"])
            sugerido = ev.enganche_requerido or min(actual + 0.05, C.ENGANCHE_MAX_CONDICION)
            if k_eng not in st.session_state:
                st.session_state[k_eng] = min(math.ceil(sugerido * 1000) / 10, C.ENGANCHE_MAX_CONDICION * 100)
            enganche_pct = st.slider(f"C3 · {C.CONTROLES['C3']['nombre']}", min_value=round(actual * 100, 1),
                                     max_value=C.ENGANCHE_MAX_CONDICION * 100, step=0.5, format="%.1f%%",
                                     key=k_eng, on_change=_guardar_borrador, help=ui.amarre("C3"))
            enganche = enganche_pct / 100
            pd_final = pd_con_enganche(modelo, fila | valores, enganche)
            bajo = pd_final < corte
            st.markdown(f"Con enganche de **{enganche:.1%}** (hoy {actual:.1%}) la PD queda en **{pd_final:.1%}\\*** "
                        + ("🟢 bajo el corte" if bajo else "🔴 sigue sobre el corte") + ".")

        contradice = False
        if decision:
            sin_recomendacion = ev.sugerencia == "Revisión manual"
            contradice = sin_recomendacion or (decision == "Aprobar" and ev.pd >= corte) or \
                (decision == "Rechazar" and ev.pd < corte) or (decision == "Condicionar" and pd_final >= corte)
        motivo = st.selectbox("Motivo" + (" (obligatorio: contradices al modelo)" if contradice else " (opcional)"),
                              C.MOTIVOS_OVERRIDE, index=None, placeholder="Elige un motivo…",
                              key=k_mot, on_change=_guardar_borrador)
        texto = st.text_input("Detalle del motivo" + (" (obligatorio)" if motivo == C.MOTIVO_OTRO else ""),
                              key=k_txt, on_change=_guardar_borrador, max_chars=280,
                              placeholder="Sin datos personales: no escribas nombres ni teléfonos.")

        if st.button("Validar decisión", type="primary", icon=":material/fact_check:", width="stretch"):
            # Paso 4a: primero se valida; el registro ocurre solo al confirmar en el diálogo.
            problemas = []
            if not decision:
                problemas.append("Elige aprobar, condicionar o rechazar.")
            if contradice and not motivo:
                problemas.append("Tu decisión contradice al modelo (o no hay recomendación): elige un motivo para "
                                 "que Luis pueda medir el acuerdo modelo–analista.")
            if motivo == C.MOTIVO_OTRO and not (texto or "").strip():
                problemas.append("Con «Otro» escribe el detalle del motivo.")
            if problemas:
                st.error("No se registró:\n\n- " + "\n- ".join(problemas), icon=":material/error:")
            else:
                aprueba = decision in ("Aprobar", "Condicionar")
                categoria = "Coincide con el modelo" if not contradice else (
                    "Aprueba lo que el modelo rechaza" if aprueba else "Rechaza lo que el modelo aprueba")
                if ev.sugerencia == "Revisión manual":
                    categoria = "Sin recomendación del modelo"
                confirmar({"folio": folio, "analista_id": usuario.analista_id, "decision": decision,
                           "enganche_condicion": enganche, "motivo": motivo, "motivo_texto": texto or None,
                           "pd": ev.pd, "sugerencia": ev.sugerencia, "contradice": contradice,
                           "categoria": categoria, "corte": corte})
        st.caption("Primero se valida (decisión, motivo, consistencia con el modelo) y después confirmas el "
                   "registro.")

# --- Fila de detalle: por qué (G2) y contra quién (G3) ------------------------------
pesos = peso_variables(modelo)
c3, c4 = st.columns(2, gap="medium")
with c3, st.container(border=True):
    ui.titulo_grafica("¿Qué sube o baja el riesgo de este caso?", "CALCULADO", codigo="G2 · barras divergentes")
    G.mostrar(G.g2_contribuciones(ev.contribuciones, datos.formatear), key="g2")
    st.caption("Puntos de PD que cambiarían si esa variable tomara el valor típico de la cartera. Rojo sube el "
               "riesgo; azul lo baja.")

with c4, st.container(border=True):
    ui.titulo_grafica("¿En qué se aleja de la media y del buen pagador?", "CALCULADO", codigo="G3 · barras pareadas")
    G.mostrar(G.g3_pareadas(C.VARIABLES_BENCHMARK, [valores[v] for v in C.VARIABLES_BENCHMARK],
                            [modelo.media_cartera[v] for v in C.VARIABLES_BENCHMARK],
                            [modelo.mediana_buenos[v] for v in C.VARIABLES_BENCHMARK]), key="g3")
    with st.expander("Expediente completo (10 variables del modelo)"):
        exp = pd.DataFrame({
            "Variable": [C.ETIQUETAS[v] for v in modelo.variables],
            "Peso en el modelo*": [pesos[v] for v in modelo.variables],
            "Valor": [datos.formatear(v, fila[v]) + (" · imputado" if v in ev.imputados else "")
                      + (" · fuera de rango" if v in ev.fuera_rango else "") for v in modelo.variables],
            "Media de la cartera": [datos.formatear(v, modelo.media_cartera[v]) if C.FORMATO[v] != "bandera"
                                    else f"{modelo.media_cartera[v]:.1%} con antecedente" for v in modelo.variables],
            "Vs. media": [("🔴 ▲" if C.SENTIDO_RIESGO[v] > 0 else "🟢 ▲") if valores[v] > modelo.media_cartera[v]
                          else ("🟢 ▼" if C.SENTIDO_RIESGO[v] > 0 else "🔴 ▼") for v in modelo.variables],
        }).sort_values("Peso en el modelo*", ascending=False)
        st.dataframe(exp, hide_index=True)
        ocultos = [f["dato"] for f in MATRIZ_DATOS if f["analista"] == OCULTO and f["grupo"] != "Calculado"]
        st.caption("★★★ = variables más significativas del modelo (mayor efecto en la PD). Ocultos por política: "
                   + ", ".join(ocultos) + ".")

ui.pie_origen("Los valores de esta solicitud son una fila real del holdout; la PD, las contribuciones y el corte "
              "vigente son datos propios*; folio, hora y estado son simulados**.")
