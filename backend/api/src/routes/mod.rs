//! `routes` — one file per question the API answers (plan §6), landed one at a time.
//! `health`, `files`, `search`, `neighborhood`, `blocklinks`, `edges`, `source`, `file`
//! and `blocks` exist today;
//! each later task adds its own file here and wires it into `crate::app`.

pub mod bench;
pub mod blocks;
pub mod blocklinks;
pub mod edges;
pub mod file;
pub mod files;
pub mod forward;
pub mod health;
pub mod neighborhood;
pub mod search;
pub mod source;
