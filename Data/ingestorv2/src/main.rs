mod processors;
mod database;
#[cfg(nightly)]
mod traits;

use std::future::Future;
use std::string::ToString;
use std::sync::OnceLock;
use std::time::Duration;
use anyhow::Error;
use async_channel::{Receiver, Sender};
use clap::Parser;
use opensearch::http::transport::{SingleNodeConnectionPool, TransportBuilder};
use opensearch::http::Url;
use opensearch::{OpenSearch, SearchParts};
use opensearch::auth::Credentials;
use opensearch::cert::CertificateValidation;
use opensearch::http::response::Response;
use riven::{RiotApi, RiotApiConfig};
use serde_json::{json, Value};
use tokio_task_manager::{Task, TaskManager};
use tracing::{debug, error, info, instrument};
use crate::processors::TypesItems;

const DATABASE_CREDS_USER: &'static str = "ingestor";
const DATABASE_CREDS_PASSWORD: &'static str = "!@#qweASDzxc456RTY";

const API_KEY_BDCC: &'static str = "RGAPI-d52eb947-b78b-4354-9423-77bb12a31130";

static RIOT_API: OnceLock<RiotApi> = OnceLock::new();
static OPEN_SEARCH_CLIENT: OnceLock<OpenSearch> = OnceLock::new();

const QUERY_BATCH_SIZE: i64 = 100;
const WANTED_MATCH_COUNT: i64 = 10;

fn build_opensearch() {
    let url = Url::parse("https://khabide.alunos.dcc.fc.up.pt:9200").unwrap();
    let conn_pool = SingleNodeConnectionPool::new(url);
    let transport = TransportBuilder::new(conn_pool)
        .cert_validation(CertificateValidation::None)
        .disable_proxy()
        .auth(
            Credentials::Basic(
                DATABASE_CREDS_USER.to_string(),
                DATABASE_CREDS_PASSWORD.to_string()
            )
        )
        .build().unwrap();
    let client = OpenSearch::new(transport);
    OPEN_SEARCH_CLIENT.set(client).unwrap();
}

fn build_riot_api() {
    let api_config = RiotApiConfig::with_key(API_KEY_BDCC).preconfig_throughput();

    let riot_api = RiotApi::new(api_config);

    match RIOT_API.set(riot_api) {
        Ok(_) => {}
        Err(_) => {
            panic!("Error")
        }
    }
}

#[derive(Parser, Debug)]
struct ProgramArgs {
    #[arg(long, default_value_t = false)]
    no_console: bool,
    #[arg(short, long, default_value_t = 4)]
    processor_threads: u8
}

#[tokio::main]
async fn main() {
    let tm = TaskManager::new(Duration::from_secs(60));
    let args = ProgramArgs::parse();
    if args.no_console {
        tracing_subscriber::fmt().init();
    } else {
        console_subscriber::init();
    }

    build_opensearch();
    build_riot_api();

    let (queue_manager, (feed_sender, _),(_, process_recv),(return_sender, _)) = create_queues();

    //spawn processor "threads"
    for _ in 0..args.processor_threads {
        let task = tm.task();
        tokio::spawn(processing_loop(process_recv.clone(), return_sender.clone(), task));
    }

    // spawn queue fillers
    for _ in 0..1 {
        let task = tm.task();
        let queue_sender = feed_sender.clone();
        tokio::spawn(async move { database_pull_loop(queue_sender, task).await.unwrap(); });
    }

    // spawn the queue manager
    tokio::spawn(queue_manager);

    tokio::time::sleep(Duration::from_secs(2)).await;

    println!("Press Ctrl+C to exit.");
    match tm.shutdown_gracefully_on_ctrl_c().await {
        true => {println!("Shut down gracefully.")}
        false => {println!("Error detected while shutting down, check logs.")}
    }
}

type Queue<T> = (Sender<T>, Receiver<T>);
fn create_queues<T>() -> (impl Future<Output=()> + Sized, Queue<T>, Queue<T>, Queue<T>) {
    let feed_queue = async_channel::bounded::<T>(100);
    let process_queue = async_channel::bounded::<T>(200);
    let return_queue = async_channel::unbounded::<T>();

    async fn queue_manager<T>(feed_queue: Queue<T>, process_queue: Queue<T>, return_queue: Queue<T>) {
        loop {
            //stop check
            if feed_queue.0.is_closed() &&  process_queue.0.is_empty() && return_queue.0.is_empty() {
                info!("Reached possible stop condition. Waiting 300 secs.");
                tokio::time::sleep(Duration::from_secs(300)).await;
                if return_queue.0.is_empty() {
                    process_queue.0.close();
                    return_queue.0.close();
                    info!("Timed out. Terminating");
                    break;
                }
            }

            /* TODO: this can be written better with tokio::select, but we also need to change queue types to do that, which requires
                nightly features at Rust 1.70 (return position impl trait in trait), or it's waaaay too complicated
             */
            let value = if let Ok(v) = return_queue.1.try_recv() {
                Some(v)
            } else if process_queue.0.len() <= 100 {
                feed_queue.1.try_recv().ok()
            } else {
                None
            };

            let value = if let Some(v) = value {
                v
            } else {
                let wait_p = if process_queue.0.len() >= 75 {
                    30000
                } else {
                    100
                };
                info!("Queues exhausted, waiting {} ms.", wait_p);
                tokio::time::sleep(Duration::from_millis(wait_p)).await;
                continue;
            };

            // if process_queue is ever closed outside of here, something bad happened.
            process_queue.0.send(value).await.unwrap();
        }
    }

    let f = queue_manager(feed_queue.clone(), process_queue.clone(), return_queue.clone());

    (f, feed_queue, process_queue, return_queue)
}

#[instrument(skip(_task))]
async fn processing_loop(recv_queue: Receiver<TypesItems>, return_queue: Sender<TypesItems>, _task: Task) {
    loop {
        let result = recv_queue.recv().await;
        match result {
            Err(_) => {
                info!("Closed queue is now empty. Stopped.");
                break;
            }
            Ok(v) => {
                match v.process(&return_queue).await {
                    Ok(_) => {}
                    Err(e) => {
                        error!("Processing {:?}\nGot error: {:?}", v, e);
                    }
                }
            }
        }
    }
}

#[instrument(skip(_task))]
async fn database_pull_loop(queue: Sender<TypesItems>, mut _task: Task) -> Result<(), Error> {
    let client = OPEN_SEARCH_CLIENT.get().unwrap();
    let mut response = tokio::select! {
        _ = _task.wait() => {
            queue.close();
            return Ok(())
        }
        i = get_response_next(client, None) => i?
    };
    loop {
        response = response.error_for_status_code()?;
        let response_body = response.json::<Value>().await?;

        let took = response_body["took"].as_i64().unwrap();
        debug!("Request took {} ms.", took);

        let hits = response_body["hits"]["hits"].as_array().unwrap();
        info!("Got {} items.", hits.len());
        if hits.is_empty() {
            info!("Request returned 0 items.");
            queue.close();
            return Ok(());
        }

        let next = &hits.last().unwrap()["sort"];

        for hit in hits {
            let id = hit["_id"].as_str().unwrap();
            queue.send(TypesItems::SummonerId(id.into())).await?
        }

        response = tokio::select! {
            _ = _task.wait() => {
                queue.close();
                return Ok(())
            }
            i = get_response_next(client, Some(next)) => i?
        }
    }
}

async fn get_response_next(client: &OpenSearch, next: Option<&Value>) -> Result<Response, Error> {
    let response = client
        .search(SearchParts::Index(&["ranks"]))
        .size(QUERY_BATCH_SIZE)
        .sort(&["_id"])
        ._source(&["false"]);
    let response = match next {
        None => {
            response.body(json!({
                "query": {
                    "match_all": {}
                },
            }))
        }
        Some(next) => {
            response.body(json!({
                "query": {
                    "match_all": {}
                },
                "search_after": next
            }))
        }
    };

    response.send().await.map_err(Into::into)
}