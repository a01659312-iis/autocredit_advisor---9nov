"""Bloque E: ningún filtro ni control sin persona y decisión."""
from src import config as C
from src.seguridad import PANTALLAS, PERSONA_DE_ROL


def _rol_de(persona: str) -> str:
    return {v: k for k, v in PERSONA_DE_ROL.items()}[persona.split(" (")[0]]


def test_cada_filtro_tiene_persona_decision_y_defecto():
    for fid, f in {**C.FILTROS, **C.CONTROLES}.items():
        assert f["persona"].strip(), fid
        assert len(f["decision"].strip()) > 20, f"{fid} necesita una decisión explícita"
        assert f["pantalla"] in PANTALLAS, fid
        assert "defecto" in f, fid
        assert f["origen"] in {"REAL", "CALCULADO", "SIMULADO"}, fid


def test_la_persona_del_filtro_puede_ver_su_pantalla():
    for fid, f in {**C.FILTROS, **C.CONTROLES}.items():
        assert _rol_de(f["persona"]) in PANTALLAS[f["pantalla"]]["roles"], fid


def test_defecto_es_una_opcion_valida():
    for fid, f in C.FILTROS.items():
        defecto = f["defecto"] if isinstance(f["defecto"], list) else [f["defecto"]]
        assert set(defecto) <= set(f["opciones"]), fid


def test_cada_pantalla_principal_tiene_persona():
    for pid in ("P1", "P2", "P3", "P4"):
        assert PANTALLAS[pid]["roles"], pid


def test_tabla_de_vigilancia_completa():
    for m in C.METRICAS_MONITOR:
        assert m["banda"] and m["frecuencia"] and m["accion"], m["metrica"]


def test_variable_excluida_no_entra_al_modelo():
    for v in C.EXCLUIDAS_DEL_MODELO:
        assert v not in C.VARIABLES_MODELO
