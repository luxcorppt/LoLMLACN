# Big Data Cloud Computing - Project

-------------------

- [BDCC Report](report/bdcc_report.pdf)

-------------------

## [Data](Data/Readme.md) - Section III
Depois de requesitar-mos uma chave de desenvolvedor há Riot, construimos um sistema de query-and-store aos dados que precisavamos para o trabalho.
Esse sistema é escrito em Rust e guarda os dados de forma que seja possivél este serem usados pela OpenSearch engine, que é bastante usada a nível industrial.
Dos dados obtidos, houve 2 passos de preprocessamento distintios: (1) construção de uma network para ser analísada; (2) criação de estrutura tabular que irá ser
algo de EAD e de algoritmos de Machine Learning.

Usamos software "state-of-the-art" para a análise e todos o código em teoria foi construido para que o escalar da quantidade de dados não levante muitos problemas.
Para além dos tradicionais packages de analise de dados e machine learning usamos o RAPIDS suite para GPU, especialmente cugraph, cufilter e cudf, packages para
large-scale network análises (networkit, graph-tool) e software para visualização de grande volume de dados como o Holoviews, Datashader e Bokeh, bem como outros packages associados.

Quanto a hardware, com autorização, usamos parte da infrastrutura do datacenter da faculdade. Hardware este que muito dele foi preparado por nós.

-------------------
## [Network Science](NetworkScience/Readme.md) - Section IV
Na análise da network fizemos testes para perceber a topologia da network bem como perceber o mecanismo que a gera. Fizemos testes quanto a processos dinamicos como
o modelo Bianconi-Barabási e testamos modelos de resiliência e difusão de informação na network com parelelos a probelmas reais e.g. difusão de tentativas de scam.
Para visualizar a network usamos técnicas de rasterização com software como Holoviews e Datashader.

-------------------
## [Machine Learning](MachineLearning/Readme.md) - Section V

A aplicação de ML a dados tabulares e a EAD aos mesmos tem os seus resultados dispostos em uma dashboard criada usando pyplot.
O principal objetivo dos algortimos de ML foi tentar perceber o quão bem se consegui distinguir os ranks dos players com base nos dados obtidos.
Para além disso, fizemos a comparação entre tipo tempo gasto e resultado das métricas entre os algoritmos a correr em CPU contra GPU (aqui descobrimos um bug no RAPIDS :] ).

-------------------

## By:
- André Silva - 201906559 - [andresilva@fc.up.pt](mailto:andresilva@fc.up.pt) / [asilva@luxcorp.pt](mailto:asilva@luxcorp.pt)
- João Afecto - 201904774 - [joao.afecto@fc.up.pt](mailto:joao.afecto@fc.up.pt) / [afecto@luxcorp.pt](mailto:afecto@luxcorp.pt)
- João Antunes - 202203846 - [joao.antunes@fc.up.pt](mailto:joao.antunes@fc.up.pt)
- Pedro Vieira - 201905272 - [pedrocvieira@fc.up.pt](mailto:pedrocvieira@fc.up.pt) / [pvieira@luxcorp.pt](mailto:pvieira@luxcorp.pt)