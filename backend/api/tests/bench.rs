//! `/bench` and the five `/api/bench/*` routes (Decision D17, M4b).
//!
//! Ruling 6 made `/bench` a 302 because one origin could not answer both UI1's and the
//! Bench's `/api/files`, and because nothing here answered the Bench's other calls. D17
//! closes both halves — the Bench-only questions live under `/api/bench/`, so the names
//! cannot collide — and this file is the proof: the page is served from here, it never
//! says the word this window is forbidden to say (gold §5), and each landed route has one
//! test of its own.

mod support;

/// PASS MARK 4's static half (Task 13, Step 3): the page ships from this origin and the
/// word never appears in it. `grep -ci prolog` over the file is the same check by hand.
#[tokio::test]
async fn bench_serves_the_page_and_never_says_prolog() {
    let res = support::get_raw("/bench").await;
    assert_eq!(res.status, 200, "GET /bench must serve the page, not redirect");
    assert!(
        res.content_type.starts_with("text/html"),
        "expected html, got {}",
        res.content_type
    );
    assert!(res.body.contains("lineageQ"), "that is not the UI2 page");
    assert!(
        !res.body.to_lowercase().contains("prolog"),
        "gold §5: UI2 never names the reference engine — the extracted page still does"
    );
}

/// The page's own file tree. Bench-shaped (`groups[].items[].path`), but keyed by the
/// store's fileids, which is what makes every later call (`file`, `blocks`, `run`,
/// `source`) work with the path it hands back.
#[tokio::test]
async fn bench_files_lists_the_store_as_the_pages_file_tree() {
    let v = support::get("/api/bench/files").await;
    let groups = v["groups"].as_array().expect("groups");
    assert_eq!(groups.len(), 1, "team_finance has one folder: {groups:?}");
    assert_eq!(groups[0]["dir"], "sas/raw");
    let items = groups[0]["items"].as_array().expect("items");
    assert_eq!(items.len(), 25, "the 25 team_finance SAS files");
    assert_eq!(items[0]["path"], "sas/raw/01_seed_customers.sas");
    assert_eq!(items[0]["name"], "01_seed_customers.sas");
    assert_eq!(items[0]["kind"], "sas");
}

/// The folder page: every file with what it holds, and the flow links between them —
/// computed from the same facts as UI1's `blocklinks`, so the two windows agree.
#[tokio::test]
async fn bench_folder_counts_the_files_and_links_them_by_flow() {
    let v = support::get("/api/bench/folder?dir=sas/raw").await;
    assert_eq!(v["dir"], "sas/raw");
    let files = v["files"].as_array().expect("files");
    assert_eq!(files.len(), 25);
    assert!(files.iter().all(|f| f["size"].as_i64().unwrap_or(0) > 0), "every file has bytes");
    assert!(
        files.iter().any(|f| f["name"] == "11_branch_rollup.sas" && f["shapes"].as_i64() == Some(1)),
        "11_branch_rollup.sas has one block"
    );
    let links = v["links"].as_array().expect("links");
    assert!(
        links.iter().any(|l| l["from"] == "01_seed_customers.sas"
            && l["to"] == "04_build_accounts.sas"
            && l["kind"] == "flow"
            && l["via"].as_array().map(|v| v.iter().any(|t| t == "work.customers")) == Some(true)),
        "04_build_accounts reads work.customers from 01_seed_customers: {links:?}"
    );
}

/// D17 says `similar` may answer `[]` **with a note** when the Bench's implementation
/// depends on a Python index this store does not hold. It does, and the note says so —
/// an empty list with no explanation would look like "no similar programs".
#[tokio::test]
async fn bench_similar_is_empty_and_says_why() {
    let v = support::get("/api/bench/similar?stem=11_branch_rollup").await;
    assert_eq!(v["similar"].as_array().map(|a| a.len()), Some(0));
    let note = v["note"].as_str().unwrap_or("");
    assert!(note.contains("signature index"), "the note must name what is missing: {note:?}");
}

/// Same shape of honesty for `listing`: the empty answer the page already renders, plus
/// the reason it is empty.
#[tokio::test]
async fn bench_listing_is_empty_and_says_why() {
    let v = support::get("/api/bench/listing?stem=09_customer_summary").await;
    assert_eq!(v["loaded"], false);
    assert_eq!(v["tables"].as_object().map(|o| o.len()), Some(0));
    assert!(v["note"].as_str().unwrap_or("").contains("Spark CSVs"));
}

/// `save` writes the corpus's `work/` stage and nothing else (D17). The refusals matter
/// more than the write: a save route that could reach `raw/` would let the page overwrite
/// the source it is migrating.
#[tokio::test]
async fn bench_save_refuses_every_path_outside_a_work_stage() {
    for bad in [
        "corpus/team_finance/sas/raw/09_customer_summary.sas",
        "backend/api/src/lib.rs",
        "../outside.py",
        "corpus/team_finance/sas/work/nested/deep.py",
    ] {
        let res = support::post_raw("/api/bench/save", serde_json::json!({"path": bad, "text": "x"})).await;
        assert_eq!(res.status, 400, "should refuse {bad}, got {} {}", res.status, res.body);
    }
}

/// The one path it accepts, round-tripped through the real corpus folder.
#[tokio::test]
async fn bench_save_writes_the_work_stage() {
    let path = "corpus/team_finance/sas/work/__m4b_save_probe.py";
    let text = "# written by tests/bench.rs\n";
    let v = support::post("/api/bench/save", serde_json::json!({"path": path, "text": text})).await;
    assert_eq!(v["saved_as"], path);
    assert_eq!(v["bytes"], text.as_bytes().len());
    let on_disk = std::path::Path::new(concat!(env!("CARGO_MANIFEST_DIR"), "/../.."))
        .join(path);
    assert_eq!(std::fs::read_to_string(&on_disk).expect("the file it says it wrote"), text);
    std::fs::remove_file(&on_disk).expect("clean up the probe");
}
