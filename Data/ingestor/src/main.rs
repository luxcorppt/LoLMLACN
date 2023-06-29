mod database;

use tracing as log;
use std::future::Future;
use std::sync::{OnceLock};
use std::time::Duration;
use riven::consts::{Division, PlatformRoute, Queue, RegionalRoute, Tier};
use riven::consts::QueueType::RANKED_SOLO_5x5;
use riven::models::match_v5::Match;
use riven::models::summoner_v4::Summoner;
use riven::{RiotApi, RiotApiConfig, RiotApiError};
use log::{error, info, debug};
use opensearch::http::transport::{SingleNodeConnectionPool, TransportBuilder};
use opensearch::http::Url;
use opensearch::{OpenSearch};
use opensearch::auth::Credentials;
use opensearch::cert::CertificateValidation;
use tokio_task_manager::{Task, TaskManager};
use tracing::{instrument, Instrument};
use crate::database::{database_exists_match, database_exists_summoner, database_exists_summoner_rank};
use futures::future::{BoxFuture, FutureExt};
use riven::models::league_v4::LeagueEntry;

#[allow(dead_code)]
// Andres summoner ID = dSAKTozJwUaJUJEC5O6ncHsxZNRTO_S45cCNLidBIsz7hrCB
// Andres account ID = YnZr9alhs_wwnX300g0KLQ7fu4V-a_5qXFnSMBXr1NdYkao

// Some random guy summers ID = vbDiZPUJf8syg4A61OIDsyBz9NHwgy6tRxt2o4V3a_E267zS

// Some random GM guy summers ID = QtbCPy7pdU032MgFPG7tvLhAQgkGdwqQb_KBHUCgfMND0gQmkq2XIs5zaw

const N_MATCHES: i32 = 10;

const ANDRE_UUID: &'static str = "blm3e9N5UTJwmVDQHJ6v47lSeszmCkQwcSoB-9bTBMLaIyttRf_GEyWBJ8bWzF0givq74y9abvjRfg";
const TIAGO_UUID: &'static str = "XBmQ-UPO-v0tAQ49iAWGC99XC-MwYCWdCHqotNatfDWYb0rRZ8IcSz1hQzlZTAicl844rO6pyZwRBw";

#[derive(Debug)]
enum TypesItems {
    Match(Match),
    Summoner(Summoner),
    Matches(Vec<String>),
    Ranks(Vec<LeagueEntry>)
}

impl From<Summoner> for TypesItems {
    fn from(value: Summoner) -> Self {
        TypesItems::Summoner(value)
    }
}

impl From<Match> for TypesItems {
    fn from(value: Match) -> Self {
        TypesItems::Match(value)
    }
}

impl From<Vec<String>> for TypesItems {
    fn from(value: Vec<String>) -> Self { TypesItems::Matches(value) }
}

impl From<Vec<LeagueEntry>> for TypesItems {
    fn from(value: Vec<LeagueEntry>) -> Self { TypesItems::Ranks(value) }
}

static RIOT_API: OnceLock<RiotApi> = OnceLock::new();
static OPENSEARCH_CLIENT: OnceLock<OpenSearch> = OnceLock::new();

fn build_opensearch(url: &str, database_creds_user: String, database_creds_pass: String) {
    let url = Url::parse(url).unwrap();
    let conn_pool = SingleNodeConnectionPool::new(url);
    let transport = TransportBuilder::new(conn_pool)
        .cert_validation(CertificateValidation::None)
        .disable_proxy()
        .auth(
            Credentials::Basic(
                database_creds_user,
                database_creds_pass
            )
        )
        .build().unwrap();
    let client = OpenSearch::new(transport);
    OPENSEARCH_CLIENT.set(client).unwrap();
}

#[tokio::main(flavor="multi_thread", worker_threads=10)]
async fn main() {
    let tm = TaskManager::new(Duration::from_secs(10));
    console_subscriber::init();

    dotenv::dotenv().ok();

    let host = std::env::var("HOST").expect("Host not found");
    let api_key_bdcc = std::env::var("API_KEY_BDCC").expect("API KEY BDCC not found");
    let database_creds_user = std::env::var("DATABASE_CREDS_USER").expect("DATABASE_CREDS_USER not found");
    let database_creds_pass = std::env::var("DATABASE_CREDS_PASSWORD").expect("DATABASE_CREDS_PASSWORD not found");

    build_opensearch(host.as_str(), database_creds_user, database_creds_pass);

    let api_config = RiotApiConfig::with_key(api_key_bdcc).preconfig_throughput();

    let riot_api = RiotApi::new(api_config);

    match RIOT_API.set(riot_api) {
        Ok(_) => {}
        Err(_) => {
            panic!("Error")
        }
    }

    let master_task= tm.task();

    info!("ready to start");

    todo!("Remove this and write the bootstrap for rank pulls");
    tokio::spawn(async {
        bootstrap(master_task).await;
    });

    tokio::time::sleep(Duration::from_secs(2)).await;

    println!("Press Ctrl+C to exit.");
    match tm.shutdown_gracefully_on_ctrl_c().await {
        true => {println!("Shut down gracefully.")}
        false => {println!("Error detected while shutting down, check logs.")}
    }
}

macro_rules! return_or_await {
    ($task:expr, $future:expr) => {
        tokio::select! {
            _ = $task.wait() => return,
            i = $future => i
        }
    }
}

macro_rules! go_process {
    ($task:expr, $b:expr) => {
        tokio::spawn(processing_loop($b, $task))
    }
}

macro_rules! get_api_result {
    ($b:expr) => {
        $b.await.map(|v| v.map(Into::into))
    }
}

macro_rules! process_api_result {
    ($task:expr, $b:expr) => {
        debug!("process_api_result checkpoint");
        let f = async move { get_api_result!($b) };
        go_process!($task, f.instrument(tracing::debug_span!("api_result_call")).boxed())
    }
}

fn escape_processing_loop<T>(fut: BoxFuture<'static, Option<Result<T,RiotApiError>>>, _task: Task)
    where
        T: Into<TypesItems> + 'static
{
    debug!("process_api_result checkpoint");
    let f = async move { get_api_result!(fut) };
    tokio::spawn(processing_loop(f.instrument(tracing::debug_span!("api_result_call")).boxed(), _task));
}


macro_rules! go_database {
    ($task:expr, $index:expr, $id:expr, $obj:expr) => {
        tokio::spawn(database::database_loop($index, $id, $obj, $task.clone()))
    }
}

#[instrument(skip(item, _task))]
fn processing_loop(item: BoxFuture<'static,Option<Result<TypesItems, RiotApiError>>>, mut _task: Task) -> BoxFuture<'static, ()> {
    async move {
        debug!("processing_loop checkpoint");
        let item = return_or_await!(_task, item);
        let item = match item {
            None => { return; }
            Some(i) => { i }
        };
        match item {
            Err(e) => {
                error!("Fail to fetch {}", e)
            }
            Ok(TypesItems::Match(m)) => {
                go_database!(
                _task.clone(),
                "matches",
                m.metadata.match_id.clone(),
                m.clone()
            );
                for puuid in m.metadata.participants {
                    escape_processing_loop(
                        async move {
                            Some(
                                RIOT_API.get().unwrap().summoner_v4().get_by_puuid(
                                    PlatformRoute::EUW1,
                                    &puuid).await
                            )
                        }.boxed(),
                        _task.clone()
                    )
                }
            }
            Ok(TypesItems::Summoner(summoner)) => {
                match database_exists_summoner(&summoner.puuid, _task.clone()).await { // If not in the database
                    Ok(exists) => {
                        if exists {
                            // match database_exists_summoner_rank() { }
                            escape_processing_loop(
                                async move {
                                    Some(RIOT_API.get().unwrap().league_v4().get_league_entries_for_summoner(
                                        PlatformRoute::EUW1,
                                        &summoner.id
                                    ).await
                                    )
                                }.boxed(),
                                _task.clone()
                            );
                            return;
                        }
                    }
                    Err(e) => {
                        error!("Failed to check database {}", e);
                        return;
                    }
                }
                go_database!(
                _task.clone(),
                "summoners",
                summoner.puuid.clone(),
                summoner.clone()
            );
                escape_processing_loop(
                    async move {
                        Some(RIOT_API.get().unwrap().match_v5().get_match_ids_by_puuid(
                            RegionalRoute::EUROPE,
                            &summoner.puuid,
                            Some(N_MATCHES),
                            None,
                            Some(Queue::SUMMONERS_RIFT_5V5_RANKED_SOLO),
                            None,
                            Some(0),
                            None
                        ).await
                        )
                    }.boxed(),
                    _task.clone()
                )
            }
            Ok(TypesItems::Matches(matches)) => {
                for m in matches {
                    match database_exists_match(&m, _task.clone()).await {
                        Ok(exists) => {
                            if exists {
                                continue;
                            }
                        }
                        Err(e) => {
                            error!("Failed to check database {}", e);
                            continue;
                        }
                    }
                    escape_processing_loop(
                        async move {
                            RIOT_API.get().unwrap().match_v5().get_match(
                                RegionalRoute::EUROPE,
                                &m
                            ).await.transpose()
                        }.boxed(),
                        _task.clone()
                    )
                }
            }
            Ok(TypesItems::Ranks(ranks)) => {
                for rank in ranks {
                    match database_exists_summoner_rank(&rank.summoner_id, _task.clone()).await { // If not in the database
                        Ok(exists) => {
                            if exists {
                                return;
                            }
                        }
                        Err(e) => {
                            error!("Failed to check database {}", e);
                            return;
                        }
                    }
                    go_database!(
                _task.clone(),
                "rank",
                rank.summoner_id.clone(),
                rank.clone()
            );
                }
            }
        }
    }.boxed()
}

#[instrument(skip(_task))]
async fn bootstrap(_task: Task) {
    let id = RIOT_API.get().unwrap().league_v4().get_league_entries(
        PlatformRoute::EUW1,
        RANKED_SOLO_5x5,
        Tier::GOLD,
        Division::IV,
        None
    ).await.expect("Fail to fetch players list for bootstrap")
        .first().expect("Fail to get first player for bootstrap")
        .summoner_id.to_owned();

    info!("Got starter node: {}", id);

    process_api_result!(
        _task.clone(),
        async { Some(RIOT_API.get().unwrap().summoner_v4().get_by_summoner_id(PlatformRoute::EUW1, id.as_str()).await) }
    );
}

/*
fn test() {
    let rt = tokio::runtime::Runtime::new().unwrap();
    rt.block_on(async {
        let riot_api = RiotApi::new(API_KEY);

        // let andre = riot_api.account_v1()
        //     .get_by_riot_id(RegionalRoute::EUROPE,"El Profeta André", "1229").await.unwrap().unwrap();

        let andre = riot_api.account_v1()
            .get_by_puuid(RegionalRoute::EUROPE, ANDRE_UUID).await.unwrap();

        println!("PUUID do Andre: {}", &andre.puuid);

        let matches = riot_api.match_v5()
            .get_match_ids_by_puuid(RegionalRoute::EUROPE,
                                    &*andre.puuid, Some(N_MATCHES), None, None, None, Some(0), None).await.unwrap();

        println!("Matches: {:?}", matches);

        let match_ = &matches[0];
        let match_ = riot_api.match_v5().get_match(RegionalRoute::EUROPE, match_).await.unwrap().unwrap();


        // 1- Go to Summers V4 get the summersID from the puuid
        // 2-

        // println!("First Match:\n{:?}", match_);

        let json = serde_json::to_string(&match_);
        //println!("First Match:\n{:?}", json.unwrap());

        // time::sleep(Duration::from_secs(20)).await;

        for (i, p) in match_.metadata.participants.iter().enumerate() {
            match riot_api.account_v1().get_by_puuid(RegionalRoute::EUROPE, p).await {
                Err(e) => {
                    println!("Player {}: Error # ({:?}) | {}", i, e.status_code(), p)
                }
                Ok(player) => {
                    println!("{}", serde_json::to_string(&player).unwrap());
                    //println!("Player {}: {} # {} | {}",
                    //         i, player.game_name.unwrap_or("<none>".parse().unwrap()), player.tag_line.unwrap_or("<none>".parse().unwrap()), p);
                }
            }
            // time::sleep(Duration::from_secs(20)).await;
        }
    })
}


// async fn todo_processor(request_tx: UnboundedSender<TypesItems>, request_rx: UnboundedReceiver<TypesItems>,
//                         process_tx: UnboundedSender<TypesItems>, process_rx: UnboundedReceiver<TypesItems>,
//                         store_tx: UnboundedSender<TypesItems>, store_rx: UnboundedReceiver<TypesItems>) {
//
//     let api_config =
//         RiotApiConfig::with_key(API_KEY_BDCC).preconfig_throughput();
//
//     let riot_api = RiotApi::new(api_config);
//
//     let mut queue: Vec<TypesItems> = Vec::new();
//
//     info!("Bootstraping...");
//     bootstrap(&mut queue, &riot_api).await;
//
//     request_tx.send(TypesItems::Empty);
//
//     info!("Starting crawling...");
//     while !queue.is_empty() {
//         match queue.pop().unwrap() {
//             TypesItems::Match(match_) => {
//                 debug!("Added new Match {:?}", match_);
//
//                 TODO: match_ -> To db
//
// for i in match_.metadata.participants{
//     queue.push(TypesItems::Summoner(
//         riot_api.summoner_v4().get_by_puuid(PlatformRoute::EUW1, &*i).await.unwrap()
//     ))
// }
// }
// TypesItems::Summoner(summoner) => {
//     debug!("Added new Summoner {:?}", summoner);
//
//TODO: summoners -> To db

// let a = riot_api.match_v5().get_match_ids_by_puuid(
//     RegionalRoute::EUROPE,
//     summoner.puuid.as_str(),
//     Some(10),
//     None,
//     Some(Queue::SUMMONERS_RIFT_5V5_RANKED_SOLO),
//     None,
//     None,
//     None
// ).await.unwrap();
//
// for i in a {
//     let match_ = riot_api.match_v5().get_match(RegionalRoute::EUROPE, &*i).await.unwrap().unwrap();

//
//
// queue.push(TypesItems::Match(match_));
// }
// }
// _ => {}
// }
// }
// }
*/