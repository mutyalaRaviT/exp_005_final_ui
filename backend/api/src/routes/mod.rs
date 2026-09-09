//! `routes` — one file per question the API answers (plan §6), landed one at a time.
//! Only `health` exists today; each later task adds its own file here and wires it into
//! `crate::app`.

pub mod health;
