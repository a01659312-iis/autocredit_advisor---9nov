"""Constantes de negocio, umbrales y registros del tablero.

Todo número de política vive aquí para que el equipo lo calibre en un solo lugar.
Los registros (FILTROS, METRICAS_MONITOR, PANTALLAS) son la fuente única que usan
las pantallas, la página de gobierno y las pruebas.
"""
from __future__ import annotations

from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
RUTA_DATOS = RAIZ / "data" / "Base_SAS_Equipo3.csv"
RUTA_BD = RAIZ / "data" / "autocredit.db"
ZONA_HORARIA = "America/Mexico_City"

APP_NOMBRE = "AutoCredit Advisor"
VERSION_MODELO = "PD-logit v1.0"
SEMILLA = 42

# ---------------------------------------------------------------------------
# Datos y modelo
# ---------------------------------------------------------------------------
OBJETIVO = "DEFAULT"
COLUMNAS_ESPERADAS = [
    "REVOLVING_UTILIZATION", "DEBT_TO_INCOME", "MISSED_PAYMENTS_12M",
    "SAVINGS_BALANCE", "DOWN_PAYMENT_PCT", "FINANCIAL_LITERACY_SCORE",
    "LOAN_TO_VALUE", "DELINQ_90", "YEARS_CREDIT_HISTORY", "PAYMENT_TO_INCOME",
    "BANKRUPTCY_FLAG", "DEFAULT",
]

# FINANCIAL_LITERACY_SCORE se excluye a propósito (ver EXCLUIDAS_DEL_MODELO).
VARIABLES_MODELO = [
    "REVOLVING_UTILIZATION", "DEBT_TO_INCOME", "PAYMENT_TO_INCOME",
    "LOAN_TO_VALUE", "DOWN_PAYMENT_PCT", "SAVINGS_BALANCE",
    "MISSED_PAYMENTS_12M", "DELINQ_90", "YEARS_CREDIT_HISTORY", "BANKRUPTCY_FLAG",
]
EXCLUIDAS_DEL_MODELO = {
    "FINANCIAL_LITERACY_SCORE": (
        "Puede funcionar como proxy de escolaridad o nivel socioeconómico, el "
        "solicitante no puede comprobarla con un documento y aporta muy poco al "
        "poder predictivo (ver diferencia de AUC en la ficha del modelo)."
    ),
}

# Etiquetas legibles y formato de cada variable.
ETIQUETAS = {
    "REVOLVING_UTILIZATION": "Uso de crédito revolvente",
    "DEBT_TO_INCOME": "Deuda / ingreso (DTI)",
    "PAYMENT_TO_INCOME": "Pago / ingreso (PTI)",
    "LOAN_TO_VALUE": "Préstamo / valor (LTV)",
    "DOWN_PAYMENT_PCT": "Enganche",
    "SAVINGS_BALANCE": "Saldo de ahorro",
    "MISSED_PAYMENTS_12M": "Pagos fallidos (12 m)",
    "DELINQ_90": "Atrasos de 90+ días",
    "YEARS_CREDIT_HISTORY": "Años de historial crediticio",
    "BANKRUPTCY_FLAG": "Antecedente de bancarrota",
    "FINANCIAL_LITERACY_SCORE": "Score de educación financiera",
    "DEFAULT": "Incumplimiento (DEFAULT)",
}
FORMATO = {  # pct | int | dinero | bandera | num
    "REVOLVING_UTILIZATION": "pct", "DEBT_TO_INCOME": "pct",
    "PAYMENT_TO_INCOME": "pct", "LOAN_TO_VALUE": "pct", "DOWN_PAYMENT_PCT": "pct",
    "SAVINGS_BALANCE": "dinero", "MISSED_PAYMENTS_12M": "int", "DELINQ_90": "int",
    "YEARS_CREDIT_HISTORY": "int", "BANKRUPTCY_FLAG": "bandera",
    "FINANCIAL_LITERACY_SCORE": "num",
}
# Variables cuyo faltante bloquea "Aprobar" (sin ellas la PD no es confiable).
VARIABLES_CLAVE = ["DEBT_TO_INCOME", "PAYMENT_TO_INCOME", "LOAN_TO_VALUE",
                   "SAVINGS_BALANCE", "MISSED_PAYMENTS_12M"]
# Límites de validez: fuera de aquí el dato es imposible y no se puntúa.
LIMITES_VALIDOS = {
    "REVOLVING_UTILIZATION": (0.0, 1.5), "DEBT_TO_INCOME": (0.0, 2.0),
    "PAYMENT_TO_INCOME": (0.0, 2.0), "LOAN_TO_VALUE": (0.0, 2.0),
    "DOWN_PAYMENT_PCT": (0.0, 1.0), "SAVINGS_BALANCE": (0.0, 10_000_000),
    "MISSED_PAYMENTS_12M": (0, 12), "DELINQ_90": (0, 12),
    "YEARS_CREDIT_HISTORY": (0, 80), "BANKRUPTCY_FLAG": (0, 1),
}

# ---------------------------------------------------------------------------
# Política de crédito (propuesta por el equipo; se calibra con datos reales)
# ---------------------------------------------------------------------------
CORTE_PD = 0.15            # PD >= corte -> el modelo sugiere no aprobar
LIMITE_RIESGO_BAJO = 0.08  # Bajo < 8% <= Medio < 15% <= Alto
TOLERANCIA_SEGMENTO = 0.20 # Mariana: segmento con default > 20% exige acción
N_MINIMO = 30              # celda/barra con n < 30 no muestra tasa
N_MINIMO_AUDITORIA = 100   # auditoría de sesgo agregada (Luis)
ESCALA_PD_MAX = 0.40
ENGANCHE_MAX_CONDICION = 0.31  # máximo enganche observado en la base (p100)
SESION_TIMEOUT_MIN = 30
META_MINUTOS_DECISION = 5

# Semáforo de incumplimiento por segmento (verde / amarillo / rojo)
AMARILLO_SEGMENTO = 0.15   # 15%–20% advertencia; > 20% fuera de tolerancia

# Sentido del riesgo: +1 = un valor más alto es peor; -1 = un valor más alto es mejor.
SENTIDO_RIESGO = {
    "REVOLVING_UTILIZATION": 1, "DEBT_TO_INCOME": 1, "PAYMENT_TO_INCOME": 1, "LOAN_TO_VALUE": 1,
    "DOWN_PAYMENT_PCT": -1, "SAVINGS_BALANCE": -1, "MISSED_PAYMENTS_12M": 1, "DELINQ_90": 1,
    "YEARS_CREDIT_HISTORY": -1, "BANKRUPTCY_FLAG": 1,
}
# Variables que se comparan contra la media de la cartera en la ficha (benchmark).
VARIABLES_BENCHMARK = ["DEBT_TO_INCOME", "PAYMENT_TO_INCOME", "LOAN_TO_VALUE", "DOWN_PAYMENT_PCT",
                       "REVOLVING_UTILIZATION"]

# ---------------------------------------------------------------------------
# Íconos de estado y semáforo (siempre con texto, nunca solo color)
# ---------------------------------------------------------------------------
ICONO_NIVEL = {"Alto": "🔴", "Medio": "🟡", "Bajo": "🟢"}
ICONO_ESTADO = {"Pendiente": "⏳", "En espera de documento": "📄", "Resuelta hoy": "✅"}
ICONO_CALIDAD = {"Completo": "✔️", "Incompleto": "⚠️", "Fuera de rango": "⛔", "Dato inválido": "⛔"}
ICONO_SUGERENCIA = {"Aprobar": "✅", "Condicionar": "🟠", "Rechazar": "❌", "Revisión manual": "🔍",
                    "Sin calcular": "—"}

# ---------------------------------------------------------------------------
# Segmentos (CALCULADOS sobre columnas REAL). Los cortes de DTI son terciles.
# ---------------------------------------------------------------------------
SEGMENTOS = {
    "SEG_DTI": {
        "etiqueta": "Endeudamiento (DTI)", "columna": "DEBT_TO_INCOME",
        "tipo": "terciles", "orden": ["Bajo", "Medio", "Alto"],
    },
    "SEG_ENGANCHE": {
        "etiqueta": "Enganche", "columna": "DOWN_PAYMENT_PCT", "tipo": "bins",
        "bins": [-0.001, 0.04, 0.08, 0.12, 1.01],
        "orden": ["< 4%", "4–8%", "8–12%", "≥ 12%"],
    },
    "SEG_PAGOS": {
        "etiqueta": "Pagos fallidos (12 m)", "columna": "MISSED_PAYMENTS_12M",
        "tipo": "bins", "bins": [-1, 0, 1, 2, 99], "orden": ["0", "1", "2", "3 o más"],
    },
    "SEG_BANCARROTA": {
        "etiqueta": "Bancarrota", "columna": "BANKRUPTCY_FLAG", "tipo": "mapa",
        "mapa": {0: "Sin bancarrota", 1: "Con bancarrota"},
        "orden": ["Sin bancarrota", "Con bancarrota"],
    },
    "SEG_LTV": {
        "etiqueta": "Préstamo / valor (LTV)", "columna": "LOAN_TO_VALUE", "tipo": "bins",
        "bins": [-0.001, 0.80, 0.90, 0.95, 2.0],
        "orden": ["< 80%", "80–90%", "90–95%", "≥ 95%"],
    },
}

# ---------------------------------------------------------------------------
# Registro de filtros. Regla (Bloque E): ningún filtro sin persona y decisión.
# La prueba tests/test_registros.py falla si alguno queda sin amarrar.
# ---------------------------------------------------------------------------
TODOS = "Todos"
FILTROS = {
    "F1": {
        "nombre": "Estado de solicitud", "pantalla": "P1", "persona": "Adrián (analista)",
        "decision": "Qué atiendo ahora: pendientes nuevas o las que esperan un documento.",
        "opciones": ["Pendiente", "En espera de documento", "Resuelta hoy"],
        "defecto": "Pendiente", "origen": "SIMULADO", "columna": "ESTADO_SOLICITUD",
    },
    "F2": {
        "nombre": "Nivel de riesgo (PD)", "pantalla": "P1", "persona": "Adrián (analista)",
        "decision": "Empezar por los casos en o sobre el corte (Alto) y los cercanos (Medio).",
        "opciones": ["Alto", "Medio", "Bajo"],
        "defecto": ["Alto", "Medio", "Bajo"], "origen": "CALCULADO", "columna": "NIVEL",
    },
    "F3": {
        "nombre": "Endeudamiento (DTI)", "pantalla": "P3", "persona": "Mariana (gerente)",
        "decision": "Fijar el DTI máximo o un corte de PD más estricto para DTI Alto.",
        "opciones": [TODOS, "Bajo", "Medio", "Alto"], "defecto": TODOS,
        "origen": "CALCULADO", "columna": "SEG_DTI",
    },
    "F4": {
        "nombre": "Enganche", "pantalla": "P3", "persona": "Mariana (gerente)",
        "decision": "Fijar el enganche mínimo: a partir de qué banda el default baja de la tolerancia.",
        "opciones": [TODOS, "< 4%", "4–8%", "8–12%", "≥ 12%"], "defecto": TODOS,
        "origen": "CALCULADO", "columna": "SEG_ENGANCHE",
    },
    "F5": {
        "nombre": "Pagos fallidos (12 m)", "pantalla": "P3", "persona": "Mariana (gerente)",
        "decision": "Condicionar (más enganche o garantía) a quien tuvo pagos fallidos recientes.",
        "opciones": [TODOS, "0", "1", "2", "3 o más"], "defecto": TODOS,
        "origen": "CALCULADO", "columna": "SEG_PAGOS",
    },
    "F6": {
        "nombre": "Antecedente de bancarrota", "pantalla": "P3", "persona": "Mariana (gerente)",
        "decision": "Mandar a revisión manual o excluir solicitudes con antecedente de bancarrota.",
        "opciones": [TODOS, "Sin bancarrota", "Con bancarrota"], "defecto": TODOS,
        "origen": "REAL", "columna": "SEG_BANCARROTA",
    },
    "F7": {
        "nombre": "Ventana de tiempo", "pantalla": "P4", "persona": "Luis (operación)",
        "decision": "Distinguir un pico de la última hora de una tendencia de varios días antes de escalar.",
        "opciones": ["Última hora", "Hoy", "7 días"], "defecto": "Hoy",
        "origen": "SIMULADO", "columna": "FECHA_SOLICITUD",
    },
}
# Controles que no filtran pero cambian lo que se ve: también se amarran a una decisión.
CONTROLES = {
    "C1": {
        "nombre": "Ver el incumplimiento por…", "pantalla": "P3", "persona": "Mariana (gerente)",
        "decision": "Elegir qué regla de política revisa: DTI máximo, enganche mínimo, pagos fallidos, bancarrota o LTV máximo (una dimensión a la vez).",
        "opciones": ["DTI", "Enganche", "Pagos fallidos", "Bancarrota", "LTV"], "defecto": "DTI",
        "origen": "CALCULADO",
    },
    "C2": {
        "nombre": "Corte de PD propuesto", "pantalla": "P3", "persona": "Mariana (gerente)",
        "decision": "Endurecer o relajar el corte de PD del segmento filtrado midiendo la aprobación que se pierde, y publicarlo a los analistas.",
        "opciones": "5% a 30% en pasos de 0.5 pp", "defecto": CORTE_PD, "origen": "CALCULADO",
    },
    "C3": {
        "nombre": "Enganche exigido al condicionar", "pantalla": "P2", "persona": "Adrián (analista)",
        "decision": "Fijar el enganche que se le pide al cliente para aprobar condicionado.",
        "opciones": "Desde el enganche actual hasta 31%", "defecto": "Enganche mínimo que deja la PD bajo el corte",
        "origen": "CALCULADO",
    },
}

# Versión corta de la decisión, para el renglón compacto bajo cada grupo de filtros.
DECISION_CORTA = {
    "F1": "qué atiendo ahora", "F2": "empezar por el riesgo más alto",
    "F3": "DTI máximo o corte más estricto", "F4": "enganche mínimo",
    "F5": "condicionar por pagos fallidos", "F6": "revisión manual por bancarrota",
    "F7": "pico de la hora o tendencia, antes de escalar",
    "C1": "qué regla de política reviso", "C2": "corte de PD del segmento",
    "C3": "enganche que pido al condicionar",
}

FILTROS_DESCARTADOS = [
    ("GENDER, RACE_ETH, AGE_BAND, PRIMARY_LANGUAGE",
     "Ninguna decisión de crédito legítima depende de ellos y filtrar por ellos facilita discriminar. Además no vienen en esta base."),
    ("STATE", "Ninguna persona decide por estado y la ubicación puede ser proxy de raza."),
    ("FINANCIAL_LITERACY_SCORE", "Excluida del modelo; filtrar por ella crearía una política sobre un posible proxy socioeconómico."),
    ("YEARS_CREDIT_HISTORY", "Ya entra al modelo; como filtro no cambia ninguna regla de política que Mariana pueda mover."),
]

# ---------------------------------------------------------------------------
# Monitor operativo (Luis). Igual a la tabla del Bloque A, ahora ejecutable.
# ---------------------------------------------------------------------------
BANDA_APROBACION = (0.55, 0.75)
BANDA_PD_PROMEDIO = (0.105, 0.165)  # 13.5% ± 3 pp
META_ACUERDO = 0.85
UMBRAL_PSI_VIGILAR = 0.10
UMBRAL_PSI_ALERTA = 0.25
UMBRAL_INCOMPLETOS = 0.02           # base REAL: 0% de nulos en las 80,000 filas
FRESCURA_AMBAR_MIN = 60
FRESCURA_ROJO_MIN = 120
REFRESCO_MIN = 15
VARIABLES_DRIFT = ["DEBT_TO_INCOME", "LOAN_TO_VALUE", "PAYMENT_TO_INCOME"]

METRICAS_MONITOR = [
    {"metrica": "Tasa de aprobación", "banda": "55% – 75%", "frecuencia": "Cada hora",
     "accion": "Revisar corte y drift", "origen": "SIMULADO"},
    {"metrica": "PD promedio de las solicitudes", "banda": "13.5% ± 3 pp (base de entrenamiento)",
     "frecuencia": "Cada hora", "accion": "Abrir detalle de drift", "origen": "SIMULADO"},
    {"metrica": "Acuerdo modelo–analista", "banda": "≥ 85% de coincidencia", "frecuencia": "Diario",
     "accion": "Revisar motivos con la gerente", "origen": "SIMULADO + REAL de la bitácora"},
    {"metrica": "Drift (PSI) de DTI, LTV y PTI", "banda": "Vigilar > 0.10 · Alerta > 0.25",
     "frecuencia": "Diario", "accion": "Escalar: revisión 100% manual", "origen": "CALCULADO"},
    {"metrica": "Solicitudes con datos clave incompletos", "banda": "> 2% (base REAL: 0%)",
     "frecuencia": "Cada carga", "accion": "Abrir incidente de datos", "origen": "SIMULADO"},
    {"metrica": "Frescura de los datos", "banda": "Ámbar > 60 min · Rojo > 120 min sin carga",
     "frecuencia": "Continuo", "accion": "Avisar a TI; KPIs en gris", "origen": "SIMULADO"},
    {"metrica": "AUC y recall del modelo (default observado vs esperado)", "banda": "AUC ≥ 0.75",
     "frecuencia": "Mensual (los créditos tardan en madurar)", "accion": "Recalibrar o reentrenar",
     "origen": "CALCULADO"},
]
AUC_MINIMO = 0.75

# ---------------------------------------------------------------------------
# Decisiones del analista
# ---------------------------------------------------------------------------
DECISIONES = ["Aprobar", "Condicionar", "Rechazar"]
MOTIVOS_OVERRIDE = [
    "Ingreso adicional comprobado no capturado",
    "Garantía o aval adicional",
    "Cliente con historial positivo en la institución",
    "Error o inconsistencia en el dato de entrada",
    "Riesgo no capturado por el modelo (fraude, documentación)",
    "Política comercial vigente / campaña",
    "Otro (detallar)",
]
MOTIVO_OTRO = "Otro (detallar)"
