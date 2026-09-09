//! `oracle` — the scaffold, not the destination.
//!
//! **Why this exists.** A question is answered from the store only once its route has
//! landed. Until then this forwards it to the Python implementation being replaced and
//! translates the reply into canonical shape. The same translation is what
//! `tools/diff_route.py` compares against, so it is written once, here, and each arm is
//! deleted as its route lands. When this file is empty the slice is done.

pub async fn forward(base: &str, path_and_query: &str) -> anyhow::Result<serde_json::Value> {
    Ok(reqwest::get(format!("{base}{path_and_query}")).await?.json().await?)
}
