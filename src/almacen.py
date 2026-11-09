"""Bitácora persistente (SQLite) de decisiones, borradores, estados y alertas.

Es lo que conecta pantallas de distintas personas: la decisión que Adrián guarda en
P2 alimenta el acuerdo modelo–analista que Luis vigila en P4. Solo se guardan folio,
decisión, motivo, PD y tiempos: nunca las variables del expediente.
"""
from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

import pandas as pd

from src import config as C

_ESQUEMA = """
CREATE TABLE IF NOT EXISTS decisiones (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, fecha TEXT, folio TEXT, analista_id TEXT, decision TEXT,
    enganche_condicion REAL, motivo TEXT, motivo_texto TEXT, pd REAL,
    sugerencia TEXT, contradice INTEGER, categoria TEXT, duracion_seg REAL, corte REAL
);
CREATE TABLE IF NOT EXISTS estados (
    folio TEXT PRIMARY KEY, analista_id TEXT, estado TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS documentos (
    folio TEXT PRIMARY KEY, ts TEXT
);
CREATE TABLE IF NOT EXISTS borradores (
    email TEXT, folio TEXT, payload TEXT, ts TEXT, PRIMARY KEY (email, folio)
);
CREATE TABLE IF NOT EXISTS regreso (
    email TEXT PRIMARY KEY, pagina TEXT, folio TEXT, ts TEXT
);
CREATE TABLE IF NOT EXISTS politicas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT, autor TEXT, segmento TEXT, descripcion TEXT,
    corte_anterior REAL, corte_nuevo REAL, n_segmento INTEGER, activa INTEGER DEFAULT 1
);
CREATE TABLE IF NOT EXISTS avisos_vistos (
    email TEXT, politica_id INTEGER, ts TEXT, PRIMARY KEY (email, politica_id)
);
CREATE TABLE IF NOT EXISTS alertas (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fecha TEXT, clave TEXT, metrica TEXT, valor TEXT, accion TEXT, tipo TEXT,
    nota TEXT, usuario TEXT, ts TEXT
);
"""


@contextmanager
def _conexion(ruta: Path | None = None):
    ruta = Path(ruta or C.RUTA_BD)
    ruta.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(ruta, check_same_thread=False)
    try:
        con.executescript(_ESQUEMA)
        # Migración: bitácoras creadas con la versión anterior no tienen la columna «corte».
        columnas = {c[1] for c in con.execute("PRAGMA table_info(decisiones)")}
        if "corte" not in columnas:
            con.execute("ALTER TABLE decisiones ADD COLUMN corte REAL")
        yield con
        con.commit()
    finally:
        con.close()


def _ahora(ahora: datetime | None) -> datetime:
    return ahora or datetime.now()


# --- Decisiones -------------------------------------------------------------
def guardar_decision(registro: dict, ahora: datetime | None = None) -> None:
    t = _ahora(ahora)
    with _conexion() as con:
        con.execute(
            """INSERT INTO decisiones (ts, fecha, folio, analista_id, decision, enganche_condicion,
               motivo, motivo_texto, pd, sugerencia, contradice, categoria, duracion_seg, corte)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (t.isoformat(timespec="seconds"), t.date().isoformat(), registro["folio"],
             registro["analista_id"], registro["decision"], registro.get("enganche_condicion"),
             registro.get("motivo"), registro.get("motivo_texto"), registro.get("pd"),
             registro.get("sugerencia"), int(bool(registro.get("contradice"))),
             registro.get("categoria"), registro.get("duracion_seg"), registro.get("corte")),
        )
        con.execute("INSERT OR REPLACE INTO estados VALUES (?,?,?,?)",
                    (registro["folio"], registro["analista_id"], "Resuelta hoy", t.isoformat()))
        con.execute("DELETE FROM borradores WHERE folio = ?", (registro["folio"],))


def decisiones(fecha: str | None = None, analista_id: str | None = None) -> pd.DataFrame:
    sql, args = "SELECT * FROM decisiones WHERE 1=1", []
    if fecha:
        sql += " AND fecha = ?"
        args.append(fecha)
    if analista_id:
        sql += " AND analista_id = ?"
        args.append(analista_id)
    with _conexion() as con:
        return pd.read_sql_query(sql + " ORDER BY ts DESC", con, params=args)


# --- Estados de solicitud ---------------------------------------------------
def poner_estado(folio: str, analista_id: str, estado: str, ahora: datetime | None = None) -> None:
    with _conexion() as con:
        con.execute("INSERT OR REPLACE INTO estados VALUES (?,?,?,?)",
                    (folio, analista_id, estado, _ahora(ahora).isoformat()))


def estados(analista_id: str) -> dict[str, str]:
    with _conexion() as con:
        filas = con.execute("SELECT folio, estado FROM estados WHERE analista_id = ?", (analista_id,)).fetchall()
    return dict(filas)


def registrar_documento(folio: str) -> None:
    with _conexion() as con:
        con.execute("INSERT OR REPLACE INTO documentos VALUES (?,?)", (folio, datetime.now().isoformat()))


def documentos_recibidos() -> set[str]:
    with _conexion() as con:
        return {f for (f,) in con.execute("SELECT folio FROM documentos").fetchall()}


# --- Borradores y regreso tras sesión expirada -------------------------------
def guardar_borrador(email: str, folio: str, payload: dict) -> None:
    with _conexion() as con:
        con.execute("INSERT OR REPLACE INTO borradores VALUES (?,?,?,?)",
                    (email, folio, json.dumps(payload), datetime.now().isoformat()))


def leer_borrador(email: str, folio: str) -> dict | None:
    with _conexion() as con:
        fila = con.execute("SELECT payload FROM borradores WHERE email = ? AND folio = ?",
                           (email, folio)).fetchone()
    return json.loads(fila[0]) if fila else None


def guardar_regreso(email: str, pagina: str, folio: str | None) -> None:
    with _conexion() as con:
        con.execute("INSERT OR REPLACE INTO regreso VALUES (?,?,?,?)",
                    (email, pagina, folio, datetime.now().isoformat()))


def tomar_regreso(email: str) -> dict | None:
    with _conexion() as con:
        fila = con.execute("SELECT pagina, folio FROM regreso WHERE email = ?", (email,)).fetchone()
        con.execute("DELETE FROM regreso WHERE email = ?", (email,))
    return {"pagina": fila[0], "folio": fila[1]} if fila else None


# --- Alertas del monitor -----------------------------------------------------
def guardar_alerta(fecha: str, clave: str, metrica: str, valor: str, accion: str,
                   tipo: str, nota: str, usuario: str) -> None:
    with _conexion() as con:
        con.execute(
            """INSERT INTO alertas (fecha, clave, metrica, valor, accion, tipo, nota, usuario, ts)
               VALUES (?,?,?,?,?,?,?,?,?)""",
            (fecha, clave, metrica, valor, accion, tipo, nota, usuario,
             datetime.now().isoformat(timespec="seconds")),
        )


def alertas_atendidas(fecha: str) -> pd.DataFrame:
    with _conexion() as con:
        return pd.read_sql_query("SELECT * FROM alertas WHERE fecha = ? ORDER BY ts DESC", con, params=[fecha])


def bitacora_alertas(limite: int = 20) -> pd.DataFrame:
    with _conexion() as con:
        return pd.read_sql_query("SELECT * FROM alertas ORDER BY ts DESC LIMIT ?", con, params=[limite])


# --- Políticas por segmento (Mariana publica, Adrián recibe aviso) -----------
def publicar_politica(segmento: dict, descripcion: str, corte_anterior: float, corte_nuevo: float,
                      n_segmento: int, autor: str, ahora: datetime | None = None) -> int:
    """Registra un corte de PD para un segmento. Una política nueva sobre el mismo
    segmento reemplaza a la anterior (la anterior queda inactiva, con su historial)."""
    clave = json.dumps(segmento, sort_keys=True, ensure_ascii=False)
    with _conexion() as con:
        con.execute("UPDATE politicas SET activa = 0 WHERE segmento = ? AND activa = 1", (clave,))
        cur = con.execute(
            """INSERT INTO politicas (ts, autor, segmento, descripcion, corte_anterior, corte_nuevo, n_segmento, activa)
               VALUES (?,?,?,?,?,?,?,1)""",
            (_ahora(ahora).isoformat(timespec="seconds"), autor, clave, descripcion,
             corte_anterior, corte_nuevo, n_segmento))
        return int(cur.lastrowid)


def revertir_politica(politica_id: int, autor: str) -> None:
    """Revertir también avisa a los analistas: se registra como un cambio más (nuevo → anterior)."""
    with _conexion() as con:
        fila = con.execute("SELECT segmento, descripcion, corte_anterior, corte_nuevo, n_segmento FROM politicas "
                           "WHERE id = ?", (politica_id,)).fetchone()
        if not fila:
            return
        con.execute("UPDATE politicas SET activa = 0 WHERE id = ?", (politica_id,))
        con.execute(
            """INSERT INTO politicas (ts, autor, segmento, descripcion, corte_anterior, corte_nuevo, n_segmento, activa)
               VALUES (?,?,?,?,?,?,?,0)""",
            (datetime.now().isoformat(timespec="seconds"), autor, fila[0], fila[1] + " (revertido)",
             fila[3], fila[2], fila[4]))


def politicas(solo_activas: bool = True) -> pd.DataFrame:
    sql = "SELECT * FROM politicas" + (" WHERE activa = 1" if solo_activas else "") + " ORDER BY id DESC"
    with _conexion() as con:
        df = pd.read_sql_query(sql, con)
    if len(df):
        df["segmento"] = df["segmento"].map(json.loads)
    return df


def marcar_avisos_vistos(email: str, ids: list[int]) -> None:
    with _conexion() as con:
        con.executemany("INSERT OR REPLACE INTO avisos_vistos VALUES (?,?,?)",
                        [(email, int(i), datetime.now().isoformat()) for i in ids])


def avisos_vistos(email: str) -> set[int]:
    with _conexion() as con:
        return {i for (i,) in con.execute("SELECT politica_id FROM avisos_vistos WHERE email = ?", (email,))}


def reiniciar_demo() -> None:
    with _conexion() as con:
        for tabla in ("decisiones", "estados", "documentos", "borradores", "regreso", "alertas", "politicas",
                      "avisos_vistos"):
            con.execute(f"DELETE FROM {tabla}")
