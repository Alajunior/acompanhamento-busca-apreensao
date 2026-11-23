"""Calendário de dias úteis e arredondamentos do Excel da aba Busca e Apreensão.

As metas da planilha do jurídico contam dias úteis (seg–sex menos feriados) e arredondam como o Excel: ARRED com o meio
afastando do zero e ARRED.CIMA sempre afastando do zero, sobre o número com 15 algarismos significativos.
"""
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, ROUND_UP, Decimal

FERIADOS_2026 = (
    date(2026, 1, 1), date(2026, 2, 16), date(2026, 2, 17), date(2026, 4, 3), date(2026, 4, 21), date(2026, 5, 1),
    date(2026, 6, 4), date(2026, 9, 7), date(2026, 10, 12), date(2026, 11, 2), date(2026, 11, 15), date(2026, 11, 20),
    date(2026, 12, 25),
    date(2026, 8, 14),   # feriado local fictício
)
HORA_CORTE = 19          # registro a partir das 19h conta no dia útil seguinte


def eh_util(d: date, feriados=FERIADOS_2026) -> bool:
    return d.weekday() < 5 and d not in feriados


def _mes(mes: str) -> tuple[int, int]:
    m, a = mes.split("/")
    return int(a), int(m)


def dias_uteis(mes: str, feriados=FERIADOS_2026) -> list[date]:
    a, m = _mes(mes)
    d, out = date(a, m, 1), []
    while d.month == m:
        if eh_util(d, feriados):
            out.append(d)
        d += timedelta(days=1)
    return out


def du_indice(d: date, feriados=FERIADOS_2026) -> int:
    """Nº do dia útil no mês até o dia (fim de semana/feriado herda o anterior; antes do 1º útil = 0)."""
    return sum(1 for x in dias_uteis(mes_txt(d), feriados) if x <= d)


def dia_util_registro(ts: datetime, feriados=FERIADOS_2026) -> date:
    d = ts.date() + timedelta(days=1 if ts.hour >= HORA_CORTE else 0)
    while not eh_util(d, feriados):
        d += timedelta(days=1)
    return d


def quebra(d: date) -> str:
    return "ATÉ DIA 10" if d.day <= 10 else ("DO DIA 11 AO DIA 20" if d.day <= 20 else "DO DIA 21 AO DIA 31")


def mes_txt(d: date) -> str:
    return f"{d.month}/{d.year}"


def _excel(x: float, casas: int, modo) -> float:
    q = Decimal(1).scaleb(-casas)
    return float(Decimal(repr(float(f"{x:.15g}"))).quantize(q, rounding=modo))


def arred(x: float, casas: int = 0) -> float:
    return _excel(x, casas, ROUND_HALF_UP)


def arred_cima(x: float, casas: int = 0) -> float:
    return _excel(x, casas, ROUND_UP)
