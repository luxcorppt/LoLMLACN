# Data

-------------------
## [Aggregator](aggregator)
Helper program for us not to change the database configurations.

-------------------
## [Graph](grapher)
Used for making the graphs for NS from the data we collected previously. 

-------------------

## [Ingest](ingestor)
First version, takes infinite data from the RIOT API and stores it into the OpenSearch database.

Here we found a bug that generates an infinite loop in the Rust compiler.

-------------------
## [IngestV2](ingestorv2)
Second version, takes data from both the RIOT API and the database, queries the data and the api and stores the results into the OpenSearch database.

-------------------
