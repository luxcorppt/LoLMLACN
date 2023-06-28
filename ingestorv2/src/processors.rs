use async_channel::Sender;
use opensearch::SearchParts;
use riven::consts::{PlatformRoute, QueueType, RegionalRoute};
use riven::models::match_v5::Match;
use serde_json::{json, Value};
use tracing::{debug, error, info, instrument, warn};
use crate::database::{database_exists_match, database_exists_summoner_rank, database_push};
use crate::{OPEN_SEARCH_CLIENT, RIOT_API, WANTED_MATCH_COUNT};
use thiserror::Error;

pub type SummonerId = String;
pub type MatchId = String;

#[derive(Debug)]
pub enum TypesItems {
    Match(Box<Match>),
    Matches(Vec<MatchId>),
    SummonerId(SummonerId),
}

impl TypesItems {
    #[instrument]
    pub async fn process(&self, queue: &Sender<TypesItems>) -> Result<(), anyhow::Error> {
        match self {
            TypesItems::Match(m) => {
                database_push("matches", m.metadata.match_id.clone(), m).await;

                // NOOOOOOPE. NO MORE RANK PULLS
                // for part in &m.info.participants {
                //     queue.send(
                //         TypesItems::SummonerId(
                //             part.summoner_id.clone()
                //         )
                //     ).await?
                // }
                Ok(())
            }
            TypesItems::Matches(matches) => {
                for m in matches {
                    if database_exists_match(m).await? {
                        warn!("The match already existed, this player will have less matches than expected.");
                        return Ok(())
                    }
                    debug!("Getting item from Riot API.");
                    queue.send(
                        TypesItems::Match(
                            RIOT_API.get().unwrap().match_v5().get_match(
                                RegionalRoute::EUROPE,
                                m
                            ).await?.unwrap().into()
                        )
                    ).await?;
                }
                Ok(())
            }
            TypesItems::SummonerId(summoner_id) => {
                //Self::processor_get_rank(summoner_id).await
                Self::processor_summoner_get_matches(summoner_id, queue).await
            }
        }
    }

    async fn processor_get_rank(summoner_id: &SummonerId) -> Result<(), anyhow::Error> {
        if database_exists_summoner_rank(summoner_id).await? {
            return Ok(())
        }
        debug!("Getting item from Riot API.");
        let val = RIOT_API.get().unwrap()
            .league_v4()
            .get_league_entries_for_summoner(PlatformRoute::EUW1, summoner_id)
            .await?;

        // Only save 5x5 Ranked Solo
        match val.iter().find(|x| x.queue_type == QueueType::RANKED_SOLO_5x5) {
            None => {
                info!("Got nothing from Riot, continuing...")
            }
            Some(rank) => {
                database_push("ranks", summoner_id.into(), rank).await;
            }
        }

        Ok(())
    }

    async fn processor_summoner_get_matches(summoner_id: &SummonerId, queue: &Sender<TypesItems>) -> Result<(),anyhow::Error> {
        let client = OPEN_SEARCH_CLIENT.get().unwrap();

        let response = client.search(SearchParts::Index(&["matches"]))
            .size(1)
            ._source_includes(&["info.participants.puuid", "info.participants.summonerId"])
            .track_total_hits(true)
            .body(json!({
                "query": {
                    "nested": {
                        "path": "info.participants",
                        "query": {
                            "match": {
                                "info.participants.summonerId.keyword": summoner_id
                            }
                        }
                    }
                }
            }))
            .send().await?;
        let response = response.error_for_status_code()?;
        let response = response.json::<Value>().await?;
        let took = response["took"].as_i64().unwrap();
        debug!("Request took {} ms", took);

        let total = &response["hits"]["total"];
        let total_rel = total["relation"].as_str().unwrap();
        // optionally a debug_assert, but it should always hold when track_total_hits is set to true
        assert_eq!(total_rel, "eq");
        let total_value = total["value"].as_i64().unwrap();
        if total_value >= WANTED_MATCH_COUNT {
            info!("Got enough matches on this summonerId, continuing...");
            return Ok(())
        }

        let needed = WANTED_MATCH_COUNT - total_value;

        let hits = response["hits"]["hits"].as_array().unwrap();
        if hits.is_empty() {
            error!("Unexpected situation: This summonerId has no matches. How tf did it end up in the db then?");
            return Err(InvariantBroken::NoMatches.into())
        }
        let hit = &hits[0];
        let participants = hit["_source"]["info"]["participants"].as_array().unwrap();
        let puuid = participants.iter()
            .find(|v| v["summonerId"].as_str().unwrap() == summoner_id)
            .unwrap()
            ["puuid"].as_str()
            .unwrap();

        let matches = RIOT_API.get().unwrap().match_v5().get_match_ids_by_puuid(
            RegionalRoute::EUROPE,
            puuid,
            Some(needed as i32),
            None,
            Some(riven::consts::Queue::SUMMONERS_RIFT_5V5_RANKED_SOLO),
            None,
            Some(0),
            None
        ).await?;

        queue.send(TypesItems::Matches(matches)).await?;

        Ok(())
    }
}

#[derive(Error, Debug)]
enum InvariantBroken {
    #[error("There should exist matches at this point.")]
    NoMatches,
}

impl From<Match> for TypesItems {
    fn from(value: Match) -> Self {
        TypesItems::Match(value.into())
    }
}

impl From<Vec<String>> for TypesItems {
    fn from(value: Vec<String>) -> Self { TypesItems::Matches(value) }
}

impl From<SummonerId> for TypesItems {
    fn from(value: SummonerId) -> Self {
        TypesItems::SummonerId(value)
    }
}