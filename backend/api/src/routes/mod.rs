//! `routes` — one file per question the API answers (plan §6), landed one at a time.
//! `health`, `files` and `search` exist today; each later task adds its own file here and
//! wires it into `crate::app`.

pub mod files;
pub mod health;
pub mod search;
