mod indexer;

use std::borrow::Cow;
use std::collections::BTreeSet;
use std::fs::File;
use std::sync::OnceLock;
use opensearch::auth::Credentials;
use opensearch::cert::CertificateValidation;
use opensearch::http::transport::{SingleNodeConnectionPool, TransportBuilder};
use opensearch::http::Url;
use opensearch::{OpenSearch, SearchParts};
use opensearch::http::response::Response;
use serde_json::{json, Value};
use tracing::{info};
use crate::indexer::Indexer;

static OPENSEARCH_CLIENT: OnceLock<OpenSearch> = OnceLock::new();

const TARGET_MATCH_COUNT: i32 = 50_000;
const QUERY_BATCH_SIZE: i64 = 1000;

fn build_opensearch() {
    let url = Url::parse("https://khabide.alunos.dcc.fc.up.pt:9200").unwrap();
    let conn_pool = SingleNodeConnectionPool::new(url);
    let transport = TransportBuilder::new(conn_pool)
        .cert_validation(CertificateValidation::None)
        .disable_proxy()
        .auth(
            Credentials::Basic(
                String::from("ingestor"),
                String::from("!@#qweASDzxc456RTY")
            )
        )
        .build().unwrap();
    let client = OpenSearch::new(transport);
    OPENSEARCH_CLIENT.set(client).unwrap();
}

#[tokio::main(flavor = "multi_thread")]
async fn main() -> Result<(), anyhow::Error> {
    tracing_subscriber::fmt::init();

    build_opensearch();

    let client = OPENSEARCH_CLIENT.get().unwrap();
    let initial_response = client
        .search(SearchParts::Index(&["matches"]))
        .size(QUERY_BATCH_SIZE)
        .sort(&["_id"])
        ._source_includes(&["metadata.participants"])
        .body(json!({
            "query": {
                "match_all": {}
            }
        }))
        .send()
        .await?;

    let mut edges: BTreeSet<(i32, i32)> = BTreeSet::new();
    let mut indexer = Indexer::new();
    let mut response_bodies = Vec::new();

    let initial_response = initial_response.error_for_status_code()?;
    // end start

    let response = initial_response;
    let mut current_count = 0;
    let response_body = response.json::<Value>().await?;
    response_bodies.push(response_body);
    loop {
        let response_body = response_bodies.last().unwrap();

        let (count, next) = process_result(&mut edges, &mut indexer, &response_body);
        current_count += count;

        if current_count >= TARGET_MATCH_COUNT as usize {
            break;
        }

        if let Some(next) = next {
            let response = get_response_next(client, next).await?;
            response_bodies.push(response.json::<Value>().await?);
        } else {
            break;
        }
    }

    info!("Finalizing with {} matches processed", current_count);

    // Finalizer
    let mut writer = csv::Writer::from_writer(File::create("output_graph.csv")?);

    for edge in edges.iter() {
        writer.serialize(edge)?;
    }
    writer.flush()?;

    info!("Finalizing map with {} nodes.", indexer.node_count());

    let mut writer = csv::Writer::from_writer(File::create("output_map.csv")?);
    for (a,b) in indexer.into_map() {
        writer.serialize((b,a))?;
    }
    writer.flush()?;

    Ok(())
}

async fn get_response_next(client: &OpenSearch, next: &Value) -> Result<Response, anyhow::Error> {
    let response = client
        .search(SearchParts::Index(&["matches"]))
        .size(QUERY_BATCH_SIZE)
        .sort(&["_id"])
        ._source_includes(&["metadata.participants"])
        .body(json!({
            "query": {
                "match_all": {}
            },
            "search_after": next
        }))
        .send()
        .await?;

    Ok(response)
}

fn process_result<'a>(edges: &mut BTreeSet<(i32, i32)>, indexer: &mut Indexer, response_body: &'a Value) -> (usize, Option<&'a Value>) {
    let took = response_body["took"].as_i64().unwrap();
    info!("Request took {} ms.", took);

    let hits = response_body["hits"]["hits"].as_array().unwrap();
    info!("Got {} items.", hits.len());
    if hits.len() == 0 {
        info!("Request returned 0 items.");
        return (0, None)
    }
    for hit in hits {
        let participants = hit["_source"]["metadata"]["participants"].as_array().unwrap();
        let participants: Vec<_> = participants.iter()
            .map(|v| Cow::from(v.as_str().unwrap()))
            .map(|v| indexer.insert_get(v.into_owned()))
            .collect();
        let iter = participants.iter();
        let iter2 = iter.clone();
        let iter_merge = iter.flat_map(|v| {
            let v2 = v.clone();
            iter2.clone().filter(move |n| **n != v2).map(move |n| (v.clone(), *n))
        });
        edges.extend(iter_merge);
    }

    (hits.len(), Some(&hits.last().unwrap()["sort"]))
}
