//! `files` — `GET /api/files`.
//!
//! **Why this exists.** The explorer's ALL FILES layer, and `search()`'s file-kind hits,
//! both start from the same list: every indexed file as `{id, label, folder}`. `:8000`
//! (`service.py::list_files`) reads two extra columns (`sasfilename`, `folder_path`) that
//! its own ingest computed once; this store keeps only `fileid`, so `label`/`folder` are
//! derived here, the same way `:8000`'s ingest derived them in the first place
//! (`sas_lineage.exporter.make_fileid`: `fileid = "<folder>/<name>"`) — split on the last
//! `/`, basename is the label, the rest is the folder (empty folder for a bare filename).
//!
//! **Inputs → outputs.** the store's `files` table, ordered by fileid → `{"files": [...]}`.

use crate::types::{AppState, FileRow};
use axum::extract::State;
use axum::http::StatusCode;
use axum::response::Json;
use serde_json::{json, Value};

pub async fn files(State(state): State<AppState>) -> Result<Json<Value>, (StatusCode, String)> {
    let conn = state.db.lock().map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let mut st = conn
        .prepare("SELECT fileid FROM files ORDER BY fileid")
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    let rows: Vec<FileRow> = st
        .query_map([], |r| Ok(split_fileid(r.get::<_, String>(0)?)))
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?
        .collect::<Result<_, _>>()
        .map_err(|e| (StatusCode::INTERNAL_SERVER_ERROR, e.to_string()))?;
    Ok(Json(json!({ "files": rows })))
}

/// `"ankitha_1/06_seed_fx_rates.sas"` -> `id` unchanged, `label` `"06_seed_fx_rates.sas"`,
/// `folder` `"ankitha_1"`. A fileid with no `/` (no subfolder) gets an empty folder.
fn split_fileid(fileid: String) -> FileRow {
    match fileid.rfind('/') {
        Some(i) => FileRow {
            label: fileid[i + 1..].to_string(),
            folder: fileid[..i].to_string(),
            id: fileid,
        },
        None => FileRow { label: fileid.clone(), folder: String::new(), id: fileid },
    }
}

#[cfg(test)]
mod tests {
    use super::split_fileid;

    #[test]
    fn splits_folder_and_label() {
        let r = split_fileid("ankitha_1/06_seed_fx_rates.sas".to_string());
        assert_eq!(r.id, "ankitha_1/06_seed_fx_rates.sas");
        assert_eq!(r.folder, "ankitha_1");
        assert_eq!(r.label, "06_seed_fx_rates.sas");
    }

    #[test]
    fn no_slash_is_an_empty_folder() {
        let r = split_fileid("big_1000.sas".to_string());
        assert_eq!(r.folder, "");
        assert_eq!(r.label, "big_1000.sas");
    }
}
