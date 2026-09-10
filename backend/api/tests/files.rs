mod support;
use support::get;

#[tokio::test]
async fn returns_all_25_team_finance_files_with_exactly_id_label_folder() {
    let res = get("/api/files").await;
    let files = res["files"].as_array().expect("files array");
    assert_eq!(files.len(), 25);
    for row in files {
        let obj = row.as_object().expect("file row is an object");
        let mut keys: Vec<&String> = obj.keys().collect();
        keys.sort();
        assert_eq!(keys, vec!["folder", "id", "label"]);
    }
}

#[tokio::test]
async fn one_row_is_shaped_right() {
    let res = get("/api/files").await;
    let files = res["files"].as_array().expect("files array");
    let hit = files
        .iter()
        .find(|f| f["id"] == "sas/raw/06_seed_fx_rates.sas")
        .expect("06_seed_fx_rates.sas is in the team_finance corpus");
    assert_eq!(hit["label"], "06_seed_fx_rates.sas");
    assert_eq!(hit["folder"], "sas/raw");
}

#[tokio::test]
async fn sorted_by_fileid() {
    let res = get("/api/files").await;
    let files = res["files"].as_array().expect("files array");
    let ids: Vec<&str> = files.iter().map(|f| f["id"].as_str().unwrap()).collect();
    let mut sorted = ids.clone();
    sorted.sort();
    assert_eq!(ids, sorted);
}
