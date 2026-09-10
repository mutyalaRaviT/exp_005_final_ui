//! `routes` — one file per question the API answers (plan §6), landed one at a time.
//! All twelve exist today: `health` plus `files`, `search`, `neighborhood`, `convert`,
//! `blocklinks`, `edges`, `source`, `file`, `blocks`, `tablegraph`, `story` and `run`.
//! `convert` (Task 6b, M4a) was the last to land, and `forward`'s fallback now has no
//! `/api/*` GET left to forward — deleting it is Task 14.

pub mod bench;
pub mod blocks;
pub mod blocklinks;
pub mod convert;
pub mod edges;
pub mod file;
pub mod files;
pub mod forward;
pub mod health;
pub mod neighborhood;
pub mod run;
pub mod search;
pub mod source;
pub mod story;
pub mod tablegraph;
