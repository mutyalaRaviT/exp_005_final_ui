//! `routes` — one file per question the API answers (plan §6), landed one at a time.
//! All twelve are here: `health` plus `files`, `search`, `neighborhood`, `convert`,
//! `blocklinks`, `edges`, `source`, `file`, `blocks`, `tablegraph`, `story` and `run`.
//! `convert` (Task 6b, M4a) was the last to land; Task 14 (M4b) then deleted `forward`,
//! the `/api/*` fallback that answered the rest while they were still Python's job.
//! `bench` is the odd one out: it serves UI2's page and the five `/api/bench/*` questions
//! only that window asks (Decision D17).

pub mod bench;
pub mod blocks;
pub mod blocklinks;
pub mod convert;
pub mod edges;
pub mod file;
pub mod files;
pub mod health;
pub mod neighborhood;
pub mod run;
pub mod search;
pub mod source;
pub mod story;
pub mod tablegraph;
