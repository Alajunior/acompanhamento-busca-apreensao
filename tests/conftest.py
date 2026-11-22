"""Fixtures compartilhadas: a simulação, a linha do tempo e o payload saem uma vez por sessão de testes."""
import pytest

from dados.gerar import simular
from src.montar_painel import montar_payload
from src.publicacao import linha_do_tempo


@pytest.fixture(scope="session")
def sim():
    return simular(42)


@pytest.fixture(scope="session")
def linha(sim):
    return linha_do_tempo(sim)


@pytest.fixture(scope="session")
def payload(linha):
    return montar_payload(linha)
