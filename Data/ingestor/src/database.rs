use std::fmt::Debug;
use std::io::Write;
use tracing::{debug, instrument};
use opensearch::{GetParts, IndexParts};
use riven::reqwest::StatusCode;
use tracing::error;
use serde_json::Value;
use tokio::fs::File;
use tokio::io::AsyncWriteExt;
use tokio_task_manager::Task;

macro_rules! panic_or_await {
    ($task:expr, $future:expr) => {
        tokio::select! {
            _ = $task.wait() => panic!("Terminating..."),
            i = $future => i
        }
    }
}

#[instrument(skip(_task))]
async fn database_exists_impl(index: &str, id: &str, mut _task: Task) -> Result<bool, opensearch::Error> {
    let client = crate::OPENSEARCH_CLIENT.get().unwrap();

    let value = match panic_or_await!(_task, client
    .get(GetParts::IndexId(index, id))
    ._source(&["false"])
    .send())
    {
        Ok(v) => {v}
        Err(e) => {
            error!("Errored while accessing the DB {:?}", e);
            return Err(e);
        }
    };

    // let value = value.error_for_status_code()?;
    let value = panic_or_await!(_task, value.json::<Value>())?;

    let found = value["found"].as_bool().unwrap();
    Ok(found)
}

macro_rules! impl_database_exists {
    ($name:ident, $index:expr) => {
        pub async fn $name(id: &str, _task: Task) -> Result<bool, opensearch::Error> {
            database_exists_impl($index, id, _task).await
        }
    }
}

impl_database_exists!(database_exists_summoner, "summoners");
impl_database_exists!(database_exists_match, "matches");
impl_database_exists!(database_exists_summoner_rank, "ranks");


#[instrument(skip(_task))]
pub async fn database_loop<T>(index: &str, id: String, object: T, mut _task: Task)
where
    T: serde::Serialize + Debug
{
    let client = crate::OPENSEARCH_CLIENT.get().unwrap();

    debug!("Pushing document id {} into index {}", id, index);

    let response = match panic_or_await!(_task, client
        .index(IndexParts::IndexId(index, &id))
        .body(&object)
        .send()
    )
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
    use crate::OPENSEARCH_CLIENT;

    #[tokio::test]
    async fn test_db_connect() {
        setup();
        let tm = TaskManager::new(Duration::from_secs(999999999));
        let res =
            database_exists_impl("summoners", "_2-HQ5Fkd5twVq0iukuyDmRZM69VpQWj0jE8sPPYrUtkLpUsp6djq2SOBEytFcYYtQBY9w36jACkBQ", tm.task()).await;
        println!("test_db_connect {:?}", res);
        assert!(res.is_ok());
        let res = res.unwrap();
        assert!(res)
    }

    fn setup() {
        if OPENSEARCH_CLIENT.get().is_none() {
            crate::build_opensearch();
        }
    }
}