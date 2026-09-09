//! `routes` — one file per question the API answers (plan §6), landed one at a time.
//! `health`, `files`, `search` and `neighborhood` exist today; each later task adds its
//! own file here and wires it into `crate::app`.

pub mod bench;
pub mod files;
pub mod forward;
pub mod health;
pub mod neighborhood;
pub mod search;
