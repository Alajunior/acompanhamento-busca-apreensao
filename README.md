# Acompanhamento de Busca e Apreensão: réplica de um painel jurídico, com dados sintéticos

[![CI](https://github.com/Alajunior/acompanhamento-busca-apreensao/actions/workflows/ci.yml/badge.svg)](https://github.com/Alajunior/acompanhamento-busca-apreensao/actions/workflows/ci.yml) ![Python 3.12](https://img.shields.io/badge/python-3.12-3776AB?logo=python&logoColor=white) [![Painel ao vivo](https://img.shields.io/badge/painel-ao%20vivo-2ea44f)](https://alajunior.github.io/acompanhamento-busca-apreensao/) ![Dados 100% sintéticos](https://img.shields.io/badge/dados-100%25%20sint%C3%A9ticos-6e7781)

> **Em 30 segundos**
>
> - **Problema:** o jurídico precisa saber o que vence hoje, onde cada processo trava, quanto vale e onde está o veículo.
> - **Como:** regra de etapas, travas de publicação, conciliação com a tabela oficial e padrões de circulação das placas por câmeras, calculados em Python e filtrados no navegador.
> - **Resultado:** 226 testes, com paridade JS × Python em todas as contagens do painel. Os trajetos foram calibrados pelo painel real: 37% das pastas com captura têm algum trajeto, contra 38% no real.

**Painel ao vivo:** https://alajunior.github.io/acompanhamento-busca-apreensao/ · dados 100% sintéticos · projeto de portfólio

Quando o cliente para de pagar o financiamento do veículo e nem a cobrança nem a entrega amigável resolvem, o caso vai para o jurídico: ação de **busca e apreensão**. O processo anda por etapas (emenda da inicial, aguardando liminar, liminar deferida, mandados) e cada etapa vira uma tarefa com prazo no sistema do escritório.

Este painel responde às perguntas do jurídico:
- **O que fazer hoje:** o que vence, onde está cada processo, quem está sobrecarregado.
- **Onde trava e quanto vale:** quanto risco há em cada etapa e quanto do valor o veículo cobre.
- **Onde está o veículo:** quais placas as câmeras de leitura viram, onde e em que etapa está o processo, e que padrão de circulação se repete.

É a réplica de um painel que construí e mantenho em produção, com o código escrito do zero. A mesma base do meu painel de Monitoramento (fotos do dia, travas de publicação, evolução) aplicada à área jurídica.

> **Todos os dados são sintéticos**, gerados por [`dados/gerar.py`](dados/gerar.py): processos, advogados (`ADV-01`…`ADV-24`), clientes (`CLIENTE 000123`), placas (começam por `ZZ`) e CPFs (mascarados). As comarcas são municípios reais, o que é geografia pública. Nenhum dado de cliente ou de empresa.

![Painel, aba Operação](docs/painel_operacao.png)

## Como usar (2 minutos)

1. **"Agora (simulado)", no topo.** O painel real atualiza a cada 30 minutos; aqui você escolhe o horário do dia simulado (26/11/2026). Dois horários mostram as travas em ação:
   - **11:05:** a leitura veio incompleta, a guarda de volume rejeita a rodada e o painel continua com a publicação anterior;
   - **13:05:** a via ao vivo cai e o painel publica a tabela oficial (o selo muda para "tabela oficial");
   - **15:05:** a leitura das capturas de placa falha, e o card Veículo localizado mantém a carga das 13:05, com aviso.
2. **Filtros** (valem para todas as abas e para a exportação): UF, carteira, data do agendamento (com os atalhos Vencidos, Hoje, Próximos 7 dias e Mês), advogado, etapa e produto do veículo.
3. **Aba Operação:**
   - KPIs com variação contra o início do dia e contra o dia anterior;
   - **Veículo localizado:** pastas vistas por câmera em 24 horas, 7 e 30 dias, por etapa com a sugestão do que fazer, as capturas mais recentes ("há 13 min") e as cidades;
   - escada de mandados e prazos por etapa;
   - carteira por advogado, com os sinais "carga alta" e "vencidos alto";
   - **mapa clicável**, por processos ou por veículos localizados: escolha um ou mais estados e o **Detalhe da região** compara cada UF com o Brasil (1 UF, 2 a 4 lado a lado, ou 5+ em tabela);
   - as tabelas dinâmicas Produtivos, Follow e Em diligência;
   - movimentação do dia.
4. **Aba Gestão:** destaques escritos por regra, risco × valor do bem, cobertura, carteira × etapa, comarcas, perfil do veículo e a evolução diária por etapa.
5. **Aba Padrões de placa (BETA):** o que se repetiu nas capturas dos últimos 60 dias, por pasta:
   - seis estados (padrão observado, em formação, aprendendo, sem captura recente, sem captura, sem placa);
   - lista com busca por pasta ou placa (com as passagens nos 60 dias) e o detalhe da pasta: ponto principal, ordem habitual pelo horário (A → B → C), **trajetos observados** (capturas seguidas em pontos diferentes, com até 3 h entre elas, e quantos se repetiram em dias diferentes), área, dias da semana, horário e endereço do banco ("perto de casa");
   - mapa de ruas (OpenStreetMap) com os pontos e os trajetos em curvas com seta, na cor do período da saída (manhã, tarde, noite) e mais grossas quanto mais dias se repetiram; clicar num trajeto da lista destaca ele no mapa. Tela cheia e CSV da aba. Link direto: [`?aba=padroes&pasta=7012366`](https://alajunior.github.io/acompanhamento-busca-apreensao/?aba=padroes&pasta=7012366);
   - card **Apreendidos com captura antes**: apreensões da aba Busca e Apreensão com a placa vista nos 60 dias antes, e o padrão de circulação que ela tinha na data da apreensão.
6. **Aba Busca e Apreensão:** a planilha do jurídico refeita como painel, para as pastas com localização do veículo ou apreensão desde janeiro:
   - segmentações como no Excel (analista, fase, UF, mês, etapa e localizador), cada uma valendo nas seções em que vale na planilha original;
   - índice lateral e as 12 seções: LOCALIZADOS, VISÃO LOCALIZADOS, MANDADOS, APREENDIDOS, VISÃO APREENDIDOS, COMP. ANALISTA, META BANCO, META RELÓGIO, META ANALISTA, META RELÓGIO ANALISTA, LOCALIZADOR e LINHA DO TEMPO;
   - tabelas com o visual do Excel: ordenação por coluna, subtotais, TOTAL fixo, busca, páginas de 40 linhas e CSV;
   - metas com % atingido, falta por dia útil e projeção, e o "relógio" por dia útil com as metas de 100%, 120% e 130%;
   - linha do tempo de cada pasta no calendário ("parado há N dias") e, ao clicar numa linha, o detalhe da pasta com os localizadores que receberam a ficha.
7. **Exportar Excel:** um `.xlsx` com os filtros ativos (BD com as 62 colunas, Resumo, Prazos, Advogados, Movimentação, Localizados, Padroes, Filtros e, com UF escolhida, Regiões). Cada card também tem seu **CSV**.

Os cards de análise têm um botão **ⓘ** com o "como ler". São três temas (Midnight, Dark e Light), e o painel funciona no celular.

![Painel, aba Gestão](docs/painel_gestao.png)

## O que tem por trás

| Parte | Como funciona | Onde |
|---|---|---|
| **Simulação** | Cerca de 17 mil processos ao longo de ~1.000 dias. Cada um nasce no contencioso, é ajuizado e anda pelas etapas até a apreensão ou a saída por acordo. Cada etapa é uma tarefa aberta com prazo, reagendada a cada 25 a 60 dias quando a etapa demora. Os tempos são calibrados pelo funil real (tabela abaixo) | [`dados/gerar.py`](dados/gerar.py) |
| **A regra** | Agenda de tarefas abertas → **uma linha por pasta** (62 colunas). Ficam só os 21 tipos válidos; uma tarefa BAIXADO tira a pasta inteira. Vence o dia de agendamento mais recente; no mesmo dia, **LIMINAR DEFERIDA > EMENDAR INICIAL > AGUARDANDO LIMINAR** (só quando todas as tarefas do dia estão nesse trio); depois decidem a hora e o maior ID | [`src/regra.py`](src/regra.py) |
| **Travas de publicação** | Toda publicação vira foto. Rodada com menos de **85%** das linhas da anterior é rejeitada (aceita se a seguinte confirmar a queda, com até 2% de diferença). Se a via ao vivo falha, entra a tabela oficial | [`src/publicacao.py`](src/publicacao.py) |
| **Conciliação** | A "tabela oficial" simulada reproduz a procedure real, que escolhe **ao acaso** entre tarefas do mesmo dia. A conciliação compara por tipo (fora as pastas com empate), por carteira e por pasta, com tolerância de max(5, 2%) | [`src/conciliacao.py`](src/conciliacao.py) |
| **Capturas de placa** | Cerca de 24 mil capturas sintéticas. Cada veículo visto tem uma rotina de 1 a 3 pontos fixos (casa, trabalho, outro) perto de uma cidade real, com hora típica e dias sorteados, mais capturas esparsas; alguns são vistos em outra UF. Parte dos veículos faz o caminho no mesmo dia (casa → câmeras de passagem fixas → trabalho e, às vezes, a volta), calibrado pelo real: 38% das placas com trajeto e 10% com trajeto repetido. Vêm com os defeitos da fonte real: placa com traço e minúscula, coordenada vazia ou (0,0), texto "undefined", duplicatas, acento na cidade | [`dados/capturas.py`](dados/capturas.py) |
| **Padrões** | Para cada carga de capturas (os horários do "agora"): células de ~330 m, ponto principal (mais dias distintos), estado pelos dias (≥ 6, 4–5, 1–3), faixa de 2 h circular (23h–1h vale), sequência com letras (só pontos de 2 dias ou mais), trajetos (capturas seguidas, células diferentes, até 3 h, agrupados por origem → destino, repetidos = 2 dias ou mais), área por envoltória convexa e distância haversine, e o "perto de casa" pelo prefixo do CEP. Para as apreensões, o mesmo cálculo com as capturas até o fim do dia da apreensão | [`src/padroes.py`](src/padroes.py) |
| **Aba Busca e Apreensão** | Da mesma simulação saem as tarefas que a aba lê: localização do veículo, apreensão, fichas enviadas a localizadores, formulário da apreensão, ações dos advogados, metas e feriados. As regras do painel real dão uma linha por pasta em cada horário: a **etapa** (Apreendido > Mandado expedido > Localizado > Encerrada), as **duas datas da apreensão** (a do registro, que conta no dia útil seguinte se for depois das 19h, e a do fato), a fase da carteira na data do evento, o valor de performance estimado e o **localizador padronizado** (texto livre agrupado pelo telefone, xarás separados por "(FINAL dddd)"). As metas seguem os arredondamentos do Excel (ARRED e ARRED.CIMA) | [`dados/ba.py`](dados/ba.py), [`src/ba_regras.py`](src/ba_regras.py) |
| **Payload** | 44 fotos (39 dias de histórico, sem domingo, mais as 5 de hoje). A primeira vai inteira; as demais, só como **delta** do que mudou. As 6 cargas de capturas seguem o mesmo esquema. O painel cabe em um HTML de ~1 MB; o detalhe das placas (~2,4 MB) fica em `placas.json` e a aba Busca e Apreensão (~1,4 MB) em `ba.json`, carregados só ao abrir a aba | [`src/montar_painel.py`](src/montar_painel.py) |
| **Agregações** | Os filtros rodam no navegador ([`src/agregar.js`](src/agregar.js)). Uma referência independente em Python ([`src/referencia.py`](src/referencia.py)) calcula os mesmos números, e o **teste de paridade** roda o JS no Node e compara tudo em 52 combinações de filtros, mais a lista da aba Padrões e as bordas das janelas de 24 h, 7 e 30 dias. A aba Busca e Apreensão tem o mesmo par ([`src/ba.js`](src/ba.js) × [`src/referencia_ba.py`](src/referencia_ba.py)), comparado seção a seção em 46 combinações de segmentação e 12 de linha do tempo | [`tests/test_paridade.py`](tests/test_paridade.py), [`tests/test_paridade_ba.py`](tests/test_paridade_ba.py) |
| **Painel** | HTML, CSS e JS puro, Chart.js, um mapa do Brasil em SVG próprio e Leaflet com OpenStreetMap na aba Padrões. Animações respeitam `prefers-reduced-motion`. A exportação `.xlsx` é feita no navegador (SheetJS) | [`src/painel.html`](src/painel.html), [`src/exportar.js`](src/exportar.js) |

**Funil simulado contra o real** (mediana de dias antes da apreensão, só dos processos apreendidos):

| Marco | Real | Simulado |
|---|---|---|
| Entrada no contencioso | 170 | 176 |
| Ajuizamento | 71 | 76 |
| Liminar deferida | 34 | 35 |
| 1º mandado | 18 | 18 |
| Apreendidos no 1º mandado | 74% | 73,5% |

No dia simulado são **4.617 processos**, 27% com agendamento vencido e 42 pastas com empate de tarefas no mesmo dia. Nos empates entre AGUARDANDO LIMINAR e EMENDAR INICIAL, a etapa real é EMENDAR em cerca de 87%, a proporção medida no histórico do sistema real: é por isso que a precedência do fluxo põe EMENDAR na frente. A conciliação com a tabela oficial fecha nas três recargas.

Nas placas, às 17:05: 1.557 pastas tiveram o veículo visto em 30 dias (34% das que têm placa), 252 nas últimas 24 horas e 65 fora da UF do processo. Pelos padrões, 647 pastas estão em padrão observado, 366 em formação e 612 aprendendo. Na carga inteira de capturas (não só nas pastas da publicação), das 1.928 pastas com captura nos 60 dias, 717 (37%) têm algum trajeto e 251 (13%) um trajeto que se repetiu em dias diferentes (no painel real, 38% e 10%). Das 1.212 apreensões do ano, 68 tiveram a placa vista nos 60 dias antes, com mediana de 5 dias entre a última captura e a apreensão.

Na aba Busca e Apreensão, às 17:05: 1.664 pastas com localização ou apreensão em 2026, sendo 1.212 apreendidas, 193 com mandado expedido aguardando o oficial, 95 localizadas e 164 com a localização encerrada sem apreensão. Foram 118 apreensões em novembro (meta de 117) e 1.227 no ano. As fichas de localizador somam 8.486 passagens em 5.744 pastas; 16,0% delas terminaram em localização (fora as fichas que chegaram com o carro já achado), com mediana de 24,7 dias do envio da ficha.

## Decisões

- **Site estático, não servidor.** O painel real é um app Flask com atualizador. Aqui o Python faz o trabalho pesado (simulação, regra, travas, fotos) e o navegador só filtra e agrega. Assim o link abre na hora, inclusive no celular. O preço é ter as agregações em JavaScript, e é para isso que existe o teste de paridade com o Python.
- **A regra é a parte que mais importa.** Um painel jurídico vale o quanto bate com a fonte oficial. Cada defeito real que a regra precisa tratar aparece de propósito nos dados, cada um com um teste:
  - chave com espaço ou NBSP;
  - tipo de tarefa com caixa trocada;
  - BAIXADO junto de tarefas abertas;
  - empates no mesmo dia;
  - veículo com cor nula.
- **Empate não é erro da regra.** A procedure oficial escolhe ao acaso entre duas tarefas do mesmo dia. Por isso a conciliação deixa essas pastas fora da comparação por tipo, e o painel aplica a precedência do fluxo nelas.
- **Uma etapa extinta, como na vida real.** EMENDA REALIZADA deixa de existir em 03/11: as tarefas abertas migram para AGUARDANDO LIMINAR. A evolução conta os dias antigos à parte, com aviso, em vez de sumir com eles.
- **Os estados de falha são encenados.** No painel real, a guarda de volume e a queda para a tabela oficial só aparecem quando acontecem. Aqui eles ficam em horários fixos do "agora", para quem avalia ver as travas funcionando.
- **Padrões calculados no Python, não no navegador.** Os padrões dependem de geometria (células, envoltória convexa, haversine) e mudam pouco ao longo do dia. O Python calcula cada carga uma vez, e só as pastas cujas capturas mudaram são recalculadas e gravadas. O navegador só conta por filtro, e essas contagens também estão na paridade, inclusive as do card de apreendidos.
- **Detalhe sob demanda.** O resumo das placas vai no HTML, porque o card, o mapa e a lista precisam dele já na abertura. O detalhe de cada pasta fica no `placas.json` e só carrega quando a aba abre. Aberto como arquivo local, o painel avisa e o resto continua funcionando.
- **Limite conhecido da simulação:** os pontos das rotinas são sorteados num raio de 6 km do centro da cidade, sem máscara de terra, e os bairros são nomes genéricos sorteados por ponto. Em cidades litorâneas, alguns pontos caem no mar. Para o que o projeto mostra (a regra dos padrões e a tela), isso não muda nada; para um estudo geográfico, seria o primeiro ajuste.
- **Descreve, não prevê.** A aba Padrões diz onde o veículo costuma passar, em que horário e que caminhos entre câmeras se repetem, como no painel real. A linha do trajeto liga as câmeras, não segue as ruas (sem serviço de rotas). Não estima probabilidade de apreensão.
- **A planilha continua sendo a planilha.** A aba Busca e Apreensão reproduz a planilha manual do jurídico (as mesmas seções, colunas e fórmulas), porque é com ela que a equipe confere o trabalho. O painel só tira a digitação: lê do sistema e aplica as regras que a planilha aplicava à mão. Um teste fecha cada fórmula de meta com números calculados à mão.
- **Nenhum nome de pessoa.** Advogados são códigos (um nome inventado pode coincidir com o de uma pessoa real) e os destaques nunca citam advogado.

![Aba Padrões de placa: detalhe de uma pasta com os trajetos observados e as curvas no mapa](docs/painel_placas.png)

![Aba Busca e Apreensão: segmentações, índice e a seção LOCALIZADOS](docs/painel_planilha.png)

## Como rodar

```bash
pip install -r requirements.txt
python -m dados.gerar --verificar      # simulação + conferência do funil (~15 s)
python -m src.montar_painel            # docs/index.html, docs/bd.json, docs/placas.json e docs/ba.json
python -m pytest                       # 226 testes (a paridade e a exportação precisam do Node)
```

Abra `docs/index.html` no navegador. Para o detalhe da aba Padrões, para a aba Busca e Apreensão e para as abas BD, Localizados e Padroes do `.xlsx`, sirva a pasta (`python -m http.server --directory docs`), porque o navegador não carrega `bd.json`, `placas.json` nem `ba.json` de um arquivo local.

## Estrutura

```
dados/gerar.py               simulação dos processos e fontes (agenda, estoque, garantia, cor, distribuição)
dados/capturas.py            capturas de placa por câmera e endereços do banco
dados/ba.py                  fontes da aba Busca e Apreensão (localizações, apreensões, fichas, metas)
src/regra.py                 agenda → uma linha por pasta (21 tipos, precedência, empates, 62 colunas)
src/publicacao.py            fotos, guarda de 85%, queda para a tabela oficial, roteiro do dia simulado
src/conciliacao.py           nossa regra × tabela oficial
src/padroes.py               capturas → resumo do localizado e padrões de circulação, por carga
src/ba_calendario.py         dias úteis e arredondamentos do Excel
src/ba_regras.py             tarefas → uma linha por pasta da aba Busca e Apreensão, localizador padronizado, passagens
src/montar_ba.py             docs/ba.json (cargas do dia em delta)
src/montar_painel.py         payload em delta + build de docs/index.html, docs/bd.json, docs/placas.json e docs/ba.json
src/agregar.js               agregações do painel (navegador e Node)
src/referencia.py            as mesmas agregações em Python, para a paridade
src/ba.js                    as 12 seções e a linha do tempo da aba Busca e Apreensão (navegador e Node)
src/referencia_ba.py         as mesmas seções em Python, para a paridade
src/exportar.js              CSV por card e abas do .xlsx
src/painel.html              o painel (HTML, CSS e JS puro)
tests/                       226 testes: simulação, capturas, padrões, regra, travas, conciliação, payload, referência, paridade, exportação, guarda de publicação
docs/                        o painel publicado, a base da exportação e as imagens deste README
```

Bibliotecas e mapa de terceiros: ver [`LICENCAS.md`](LICENCAS.md).
