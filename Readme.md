# Understanding League of Legends through Machine Learning and Analysis of Complex Networks

-------------------

## Informations:
- Course: Big Data Cloud Computing at FCUP
- [Report](report/bdcc_report.pdf)
### By:
- André Silva - 201906559 - [andresilva@fc.up.pt](mailto:andresilva@fc.up.pt) / [asilva@luxcorp.pt](mailto:asilva@luxcorp.pt)
- João Afecto - 201904774 - [joao.afecto@fc.up.pt](mailto:joao.afecto@fc.up.pt) / [afecto@luxcorp.pt](mailto:afecto@luxcorp.pt)
- João Antunes - 202203846 - [joao.antunes@fc.up.pt](mailto:joao.antunes@fc.up.pt)
- Pedro Vieira - 201905272 - [pedrocvieira@fc.up.pt](mailto:pedrocvieira@fc.up.pt) / [pvieira@luxcorp.pt](mailto:pvieira@luxcorp.pt)

-------------------

## [Data](Data/Readme.md) - Section III
After requesting a developer key at Riot, we built a query-and-store system for the data we needed for the assignment.

We used Rust to make the system that takes data from RIOT and stores it in a way that can be posteriorly used by the OpenSearch engine, commonly used at an industrial level.

From the data obtained, there were two distinct preprocessing steps:
- construction of a network to be analyzed;
- creation of a tabular structure that will be something from EAD and Machine Learning algorithms.

We use "state-of-the-art" software for the analysis, and all the code, in theory, was built so that scaling the amount of data does not raise too many problems.
In addition to the traditional data analysis and machine learning packages, we use the RAPIDS suite for the GPU, especially Cugraph, Cufilter, and Cudf packages for large-scale network analysis (Networkit, Graph-tool) and large-scale data visualization software such as Holoviews, Datashader, and Bokeh, as well as other associated packages.

As for hardware, we use part of the college's data center infrastructure. The infrastructure was built by us under the supervision of the Department of Computer Science, Faculty of Sciences of the University of Porto.

-------------------
## [Network Science](NetworkScience/Readme.md) - Section IV
In the network analysis, we performed various tests not only to understand the topology of the network but also to understand the mechanism that generates it.

We tested dynamic processes such as the Bianconi-Barabási model and models of resilience and information diffusion in the network with parallels to real problems, for example, dissemination of scam attempts.
To visualize the network, we use rasterization techniques with software such as Holoviews and Datashader.

-------------------
## [Machine Learning](MachineLearning/Readme.md) - Section V

Applying ML to tabular data and EDA to them has its results arranged in a dashboard created using Pyplot.
The main objective of the ML algorithms was to try to understand how well I could distinguish the ranks of the players based on the data obtained.
Furthermore, we compared the type of time spent and the result of the metrics between the algorithms running on CPU versus GPU. We also discovered a bug in RAPIDS.

-------------------
