use std::collections::BTreeMap;
use std::fs::File;
use anyhow::Error;
use opensearch::http::response::Response;
use opensearch::{OpenSearch, SearchParts};
use opensearch::auth::Credentials;
use opensearch::cert::CertificateValidation;
use opensearch::http::transport::{SingleNodeConnectionPool, TransportBuilder};
use opensearch::http::Url;
use serde_json::{json, Value};
use tracing::info;

const QUERY_BATCH_SIZE: i64 = 500;

#[tokio::main]
async fn main() -> Result<(), Error> {
    let mut buckets_map: BTreeMap<String, u64> = BTreeMap::new();
    let client = build_opensearch();
    let mut response = get_response_next(&client, None).await?;

    loop {
        response = response.error_for_status_code()?;
        let response_body = response.json::<Value>().await?;


        let took = response_body["took"].as_i64().unwrap();
        info!("Request took {} ms.", took);

        let hits = response_body["hits"]["hits"].as_array().unwrap();
        info!("Got {} items.", hits.len());
        if hits.len() == 0 {
            info!("Request returned 0 items.");
            break;
        }

        let next = &hits.last().unwrap()["sort"];

        for hit in hits {
            let participants = hit["_source"]["info"]["participants"].as_array().unwrap();
            for part in participants {
                let id = part["summonerId"].as_str().unwrap();
                *buckets_map.entry(id.into()).or_insert(0) += 1;
            }
        }

        response = get_response_next(&client, Some(next)).await?;
    }

    // Finalizer
    let mut writer = csv::Writer::from_writer(File::create("output_buckets.csv")?);

    for v in buckets_map.iter() {
        writer.serialize(v)?;
    }
    writer.flush()?;

    Ok(())
}

async fn get_response_next(client: &OpenSearch, next: Option<&Value>) -> Result<Response, Error> {
    let response = client
        .search(SearchParts::Index(&["matches"]))
        .size(QUERY_BATCH_SIZE)
        .sort(&["_id"])
        ._source_includes(&["info.participants.summonerId"]);
    let response = match next {
        None => {
            response.body(json!({
                "query": {
                    "match": {
                        "info.queueId": 420
                    }
                },
            }))
        }
        Some(next) => {
            response.body(json!({
                "query": {
                    "match": {
                        "info.queueId": 420
                    }
                },
                "search_after": next
            }))
        }
    };

    response.send().await.map_err(Into::into)
}

fn build_opensearch() -> OpenSearch {
    let url = Url::parse("https://192.168.0.239:9200").unwrap();
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
    client
}