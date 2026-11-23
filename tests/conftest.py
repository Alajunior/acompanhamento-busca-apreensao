"""Fixtures compartilhadas: a simulação, a linha do tempo e o payload saem uma vez por sessão de testes."""
import pytest

from dados.gerar import simular
from src.montar_painel import montar_payload
from src.padroes import cargas as _cargas
from src.publicacao import linha_do_tempo


@pytest.fixture(scope="session")
def sim():
    return simular(42)


@pytest.fixture(scope="session")
def linha(sim):
    return linha_do_tempo(sim)


@pytest.fixture(scope="session")
def cargas(sim):
    return _cargas(sim)


@pytest.fixture(scope="session")
def payload(linha, cargas):
    return montar_payload(linha, cargas)


@pytest.fixture(scope="session")
def ba_fontes(sim):
    from dados.ba import fontes_ba
    return fontes_ba(sim)


@pytest.fixture(scope="session")
def ba_json(sim, tmp_path_factory):
    from src.montar_ba import montar_ba
    return montar_ba(sim, tmp_path_factory.mktemp("ba") / "ba.json")
