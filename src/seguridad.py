"""Matrices de acceso y política de columnas (Bloque F).

Este módulo no solo documenta: el código de las pantallas pide aquí qué columnas
puede recibir cada rol. Lo que no está en la matriz se niega por defecto.
"""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

# ---------------------------------------------------------------------------
# Roles
# ---------------------------------------------------------------------------
ROLES = {
    "analista": "Analista de crédito",
    "gerente": "Gerente de riesgo",
    "operacion": "Operación del modelo",
}
PERSONA_DE_ROL = {"analista": "Adrián", "gerente": "Mariana", "operacion": "Luis"}
TODOS_LOS_ROLES = list(ROLES)

# Tabla correo -> rol para el modo demostración. En producción vive en
# .streamlit/secrets.toml ([roles."correo"]) y nunca en el repositorio.
USUARIOS_DEMO = {
    "adrian.perez@autocredit.mx": {"nombre": "Adrián Pérez", "rol": "analista", "analista_id": "A-017"},
    "sofia.reyes@autocredit.mx": {"nombre": "Sofía Reyes", "rol": "analista", "analista_id": "A-022"},
    "mariana.torres@autocredit.mx": {"nombre": "Mariana Torres", "rol": "gerente", "analista_id": None},
    "luis.ramirez@autocredit.mx": {"nombre": "Luis Ramírez", "rol": "operacion", "analista_id": None},
    "invitado@autocredit.mx": {"nombre": "Invitado sin rol", "rol": None, "analista_id": None},
}


@dataclass(frozen=True)
class Usuario:
    email: str
    nombre: str
    rol: str | None
    analista_id: str | None = None

    @property
    def persona(self) -> str:
        return PERSONA_DE_ROL.get(self.rol or "", "Sin rol")

    @property
    def nombre_corto(self) -> str:
        partes = self.nombre.split()
        return f"{partes[0][0]}. {' '.join(partes[1:])}" if len(partes) > 1 else self.nombre


# ---------------------------------------------------------------------------
# Matriz persona × pantalla
# ---------------------------------------------------------------------------
PANTALLAS = {
    "P0": {"titulo": "Inicio de sesión", "roles": TODOS_LOS_ROLES, "alcance": "Todos",
           "decision": "Ninguna de negocio: identifica a la persona y le asigna su rol."},
    "P1": {"titulo": "Bandeja de solicitudes", "roles": ["analista"], "alcance": "Solo sus casos (ANALISTA_ID)",
           "decision": "¿Qué solicitud atiendo primero?"},
    "P2": {"titulo": "Ficha de solicitud", "roles": ["analista"], "alcance": "Solo sus casos (ANALISTA_ID)",
           "decision": "Aprobar, condicionar o rechazar esta solicitud."},
    "P3": {"titulo": "Cartera por segmento", "roles": ["gerente"], "alcance": "Solo agregados (n ≥ 30)",
           "decision": "Endurecer o relajar la política de un segmento (corte, enganche, DTI máx.)."},
    "P4": {"titulo": "Monitor operativo", "roles": ["operacion"], "alcance": "Métricas y distribuciones agregadas",
           "decision": "Escalar una alerta o descartarla con nota."},
    "P5": {"titulo": "Estados y recorridos", "roles": TODOS_LOS_ROLES, "alcance": "Sin datos de clientes",
           "decision": "¿Puedo confiar en lo que veo? Si no, ¿cómo me recupero?"},
    "P6": {"titulo": "Gobierno de datos", "roles": TODOS_LOS_ROLES, "alcance": "Solo metadatos",
           "decision": "Saber quién ve qué dato y con qué tratamiento."},
}


def puede_ver(rol: str | None, pantalla: str) -> bool:
    return bool(rol) and rol in PANTALLAS[pantalla]["roles"]


def matriz_pantallas() -> pd.DataFrame:
    filas = []
    for rol, nombre in ROLES.items():
        fila = {"Persona": f"{PERSONA_DE_ROL[rol]} · {nombre}"}
        for pid, p in PANTALLAS.items():
            if not puede_ver(rol, pid):
                fila[f"{pid} {p['titulo']}"] = "✗ No"
            elif p["alcance"].startswith("Solo sus"):
                fila[f"{pid} {p['titulo']}"] = "✓ Sus casos"
            else:
                fila[f"{pid} {p['titulo']}"] = "✓ Sí"
        filas.append(fila)
    return pd.DataFrame(filas)


# ---------------------------------------------------------------------------
# Matriz persona × dato (completa: toda columna de la base, derivada,
# propuesta y protegida). Niveles de acceso:
# ---------------------------------------------------------------------------
INDIVIDUAL = "Individual"          # el valor de una solicitud concreta
AGREGADO = "Agregado n≥30"          # tasas, medianas, distribuciones
AUDITORIA = "Auditoría n≥100"       # solo agregados grandes para sesgo
ENMASCARADO = "Enmascarado"         # ****1234
VISIBLE = "Visible"                 # metadato del sistema, no es dato personal
OCULTO = "Oculto"                   # la columna no sale de la base

_M = []


def _dato(dato, grupo, origen, sensibilidad, analista, gerente, operacion, nota=""):
    _M.append({"dato": dato, "grupo": grupo, "origen": origen, "sensibilidad": sensibilidad,
               "analista": analista, "gerente": gerente, "operacion": operacion, "nota": nota})


# 1) Las 12 columnas de Base_SAS_Equipo3.csv (REAL)
_G1 = "Columna de la base"
_dato("REVOLVING_UTILIZATION", _G1, "REAL", "Crediticio", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("DEBT_TO_INCOME", _G1, "REAL", "Financiero", INDIVIDUAL, AGREGADO, AGREGADO, "Drift diario (PSI)")
_dato("PAYMENT_TO_INCOME", _G1, "REAL", "Financiero", INDIVIDUAL, AGREGADO, AGREGADO, "Drift diario (PSI)")
_dato("LOAN_TO_VALUE", _G1, "REAL", "Financiero", INDIVIDUAL, AGREGADO, AGREGADO, "Drift diario (PSI)")
_dato("DOWN_PAYMENT_PCT", _G1, "REAL", "Financiero", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("SAVINGS_BALANCE", _G1, "REAL", "Financiero (saldo bancario)", INDIVIDUAL, AGREGADO, AGREGADO,
      "Mariana ve medianas por segmento; Luis, distribución")
_dato("MISSED_PAYMENTS_12M", _G1, "REAL", "Crediticio", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("DELINQ_90", _G1, "REAL", "Crediticio", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("YEARS_CREDIT_HISTORY", _G1, "REAL", "Crediticio", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("BANKRUPTCY_FLAG", _G1, "REAL", "Crediticio (legal)", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("FINANCIAL_LITERACY_SCORE", _G1, "REAL", "Posible proxy socioeconómico", OCULTO, OCULTO, AUDITORIA,
      "Fuera del modelo; solo auditoría de sesgo")
_dato("DEFAULT", _G1, "REAL", "Resultado histórico", OCULTO, AGREGADO, AGREGADO,
      "Una solicitud nueva aún no tiene resultado: mostrarlo al analista filtraría la respuesta")

# 2) Datos CALCULADOS
_G2 = "Calculado"
_dato("PD_MODELO", _G2, "CALCULADO", "Score de riesgo", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("CONTRIBUCIONES_LOCALES", _G2, "CALCULADO", "Explicación del caso", INDIVIDUAL, OCULTO, OCULTO,
      "Solo explican un caso; Luis ve coeficientes globales")
_dato("SEGMENTOS (DTI, enganche, pagos, LTV)", _G2, "CALCULADO", "Agrupación", OCULTO, AGREGADO, AGREGADO)
_dato("PSI y calibración", _G2, "CALCULADO", "Métrica del sistema", OCULTO, OCULTO, AGREGADO)
_dato("CORTE_POR_SEGMENTO (política publicada)", _G2, "CALCULADO", "Política de crédito", INDIVIDUAL, INDIVIDUAL,
      AGREGADO, "Mariana la publica; Adrián ve el corte que aplica a su solicitud y recibe aviso del cambio")

# 3) Columnas operativas PROPUESTAS (hoy SIMULADO)
_G3 = "Propuesta operativa"
_dato("LOAN_ID / FOLIO", _G3, "SIMULADO", "Identificador", INDIVIDUAL, OCULTO, ENMASCARADO,
      "Adrián: completo, solo sus casos")
_dato("ANALISTA_ID", _G3, "SIMULADO", "Identificador interno", INDIVIDUAL, AGREGADO, OCULTO,
      "Filtro en servidor: cada analista recibe solo lo suyo")
_dato("FECHA_SOLICITUD", _G3, "SIMULADO", "Operativo", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("ESTADO_SOLICITUD", _G3, "SIMULADO", "Operativo", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("DECISION_ANALISTA", _G3, "REAL en bitácora", "Decisión", INDIVIDUAL, AGREGADO, ENMASCARADO,
      "Luis ve la bitácora con folio enmascarado y sin analista")
_dato("MOTIVO_OVERRIDE (catálogo)", _G3, "REAL en bitácora", "Decisión", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("MOTIVO_OVERRIDE (texto libre)", _G3, "REAL en bitácora", "Puede contener datos personales",
      INDIVIDUAL, OCULTO, OCULTO)
_dato("FECHA_CARGA", _G3, "SIMULADO", "Metadato del sistema", VISIBLE, VISIBLE, VISIBLE)

# 4) Columnas del dataset completo que NO vienen en esta base (protegidas)
_G4 = "Protegida · no viene en esta base"
_dato("RACE_ETH", _G4, "NO PRESENTE", "Protegido", OCULTO, OCULTO, AUDITORIA)
_dato("GENDER", _G4, "NO PRESENTE", "Protegido", OCULTO, OCULTO, AUDITORIA)
_dato("PRIMARY_LANGUAGE", _G4, "NO PRESENTE", "Protegido", OCULTO, OCULTO, AUDITORIA)
_dato("AGE / AGE_BAND", _G4, "NO PRESENTE", "Protegido", OCULTO, OCULTO, AUDITORIA)
_dato("MEDICAL_DEBT_FLAG", _G4, "NO PRESENTE", "Salud", OCULTO, OCULTO, OCULTO)
_dato("STATE", _G4, "NO PRESENTE", "Ubicación (posible proxy de raza)", INDIVIDUAL, AGREGADO, OCULTO,
      "Mariana solo STATE_TIER")
_dato("HOUSEHOLD_INCOME", _G4, "NO PRESENTE", "Financiero", INDIVIDUAL, AGREGADO, AGREGADO)
_dato("Nombre, teléfono, RFC/CURP", _G4, "NO PRESENTE", "Identificación directa", OCULTO, OCULTO, OCULTO,
      "No cambia la decisión; vive en el sistema de originación")

MATRIZ_DATOS: list[dict] = _M


def tratamiento(fila: dict) -> str:
    niveles = {fila["analista"], fila["gerente"], fila["operacion"]}
    if ENMASCARADO in niveles:
        return "ENMASCARAR"
    if niveles <= {OCULTO, AUDITORIA}:
        return "OCULTAR"
    if niveles == {VISIBLE}:
        return "VISIBLE"
    if fila["dato"] == "ANALISTA_ID":
        return "AUTORIZAR"
    if AGREGADO not in niveles and INDIVIDUAL in niveles:
        return "RESTRINGIR"   # solo quien decide el caso lo ve; nadie más, ni agregado
    return "AGREGAR"


def nivel_acceso(rol: str, dato: str) -> str:
    """Nivel de acceso de un rol a un dato. Lo desconocido se niega (OCULTO)."""
    for fila in MATRIZ_DATOS:
        if fila["dato"] == dato:
            return fila[rol]
    return OCULTO


def columnas_individuales(rol: str, columnas) -> list[str]:
    """Columnas que el rol puede ver a nivel de una solicitud concreta."""
    return [c for c in columnas if nivel_acceso(rol, c) == INDIVIDUAL]


def aplicar_politica_fila(rol: str, fila: dict) -> dict:
    """Quita de una fila todo lo que el rol no puede ver de forma individual."""
    return {k: v for k, v in fila.items() if nivel_acceso(rol, k) == INDIVIDUAL}


def puede_agregado(rol: str, dato: str) -> bool:
    return nivel_acceso(rol, dato) in (INDIVIDUAL, AGREGADO, AUDITORIA)


def tabla_matriz_datos() -> pd.DataFrame:
    filas = []
    for f in MATRIZ_DATOS:
        filas.append({
            "Dato": f["dato"], "Grupo": f["grupo"], "Origen": f["origen"],
            "Sensibilidad": f["sensibilidad"],
            "Adrián (analista)": f["analista"], "Mariana (gerente)": f["gerente"],
            "Luis (operación)": f["operacion"], "Tratamiento": tratamiento(f), "Nota": f["nota"],
        })
    return pd.DataFrame(filas)


def enmascarar(folio: str) -> str:
    folio = str(folio)
    return "****" + folio[-4:]
