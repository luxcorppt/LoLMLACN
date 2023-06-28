use std::fmt::Debug;
use std::io::Write;
use tracing::{debug, instrument};
use opensearch::{IndexParts, SearchParts};
use opensearch::http::StatusCode;
use tracing::error;
use serde_json::{json, Value};
use tokio::fs::File;
use tokio::io::AsyncWriteExt;

#[instrument]
async fn database_exists_impl(index: &str, id: &str) -> Result<bool, opensearch::Error> {
    let client = crate::OPEN_SEARCH_CLIENT.get().unwrap();

    debug!("Checking for document");

    let value = match client
        .search(SearchParts::Index(&[index]))
        .size(0)
        .body(json!({
            "query": {
                "match": {
                    "_id": id
                }
            }
        }))
        .send()
        .await
    {
        Ok(v) => {v}
        Err(e) => {
            error!("Errored while accessing the DB {:?}", e);
            return Err(e);
        }
    };

    // let value = value.error_for_status_code()?;
    let value = value.json::<Value>().await?;

    let found = value["hits"]["total"]["value"].as_i64().unwrap() != 0;
    Ok(found)
}

macro_rules! impl_database_exists {
    ($name:ident, $index:expr) => {
        pub async fn $name(id: &str) -> Result<bool, opensearch::Error> {
            database_exists_impl($index, id).await
        }
    }
}

impl_database_exists!(database_exists_summoner, "summoners");
impl_database_exists!(database_exists_match, "matches");
impl_database_exists!(database_exists_summoner_rank, "ranks");


#[instrument]
pub async fn database_push<T>(index: &str, id: String, object: T)
where
    T: serde::Serialize + Debug
{
    let client = crate::OPEN_SEARCH_CLIENT.get().unwrap();

    debug!("Pushing document");

    let response = match client
        .index(IndexParts::IndexId(index, &id))
        .body(&object)
        .send()
        .await
    {
        Ok(r) => {r},
        Err(e) => {
            handle_db_error(index, id, object, Some(e), None, None).await;
            return;
        }
    };

    if !response.status_code().is_success() {
        handle_db_error(index, id, object, None, Some(response.status_code()), Some(response.text().await.unwrap())).await;
    }
}

async fn handle_db_error(index: &str, id: String, object: impl Debug, err: Option<opensearch::Error>, status_code: Option<StatusCode>, response: Option<String>) {
    error!("Got error for database:\nStatus code: {:?}\nError object: {:?}\nindex: {}\nid: {}\nresponse: {:?}\n", status_code, err, index, id, response);
    let mut file = File::create(String::from("store_db_fail_") + &id).await.unwrap();
    let mut buf = Vec::new();
    write!(buf, "{:?}", object).unwrap();
    file.write_all(buf.as_slice()).await.unwrap()
}

#[cfg(test)]
mod tests {
    use std::time::Duration;
    use tokio_task_manager::TaskManager;
    use crate::database::database_exists_impl;
    use crate::OPEN_SEARCH_CLIENT;

    #[tokio::test]
    async fn test_db_connect() {
        setup();
        let res =
            database_exists_impl("summoners", "_2-HQ5Fkd5twVq0iukuyDmRZM69VpQWj0jE8sPPYrUtkLpUsp6djq2SOBEytFcYYtQBY9w36jACkBQ").await;
        println!("test_db_connect {:?}", res);
        assert!(res.is_ok());
        let res = res.unwrap();
        assert!(res)
    }

    fn setup() {
        if OPEN_SEARCH_CLIENT.get().is_none() {
            crate::build_opensearch();
        }
    }
}