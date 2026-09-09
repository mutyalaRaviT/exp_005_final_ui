//! `lineageq_api` binary — a thin wrapper: parse the flags, open the real store, serve
//! `lineageq_api::app`. All routing and handler logic lives in `lib.rs` / `routes/` so a
//! test can drive the very same router in-process with no TCP listener at all
//! (`tests/support/mod.rs`) — see `lib.rs` for why that split exists.

use lineageq_api::{app, AppState};
use std::path::PathBuf;
use std::sync::{Arc, Mutex};

struct Flags {
    db: PathBuf,
    oracle_a: String,
    oracle_b: String,
    port: u16,
}

fn parse_flags() -> Flags {
    let mut db = PathBuf::from("lineageq.duckdb");
    let mut oracle_a = "http://127.0.0.1:8000".to_string();
    let mut oracle_b = "http://127.0.0.1:8042".to_string();
    // Default :8110, not :8100 — :8100 is already held on the dev machine by an
    // unrelated long-running server (deck_server.py), and a default that silently
    // fails to bind (or worse, gets mistaken for ours, as :5174/:8042 once were) is a
    // trap for whoever runs this next. See the Task 3 report for the ruling.
    let mut port: u16 = 8110;

    let args: Vec<String> = std::env::args().collect();
    let mut i = 1;
    while i < args.len() {
        match args[i].as_str() {
            "--db" => {
                i += 1;
                db = PathBuf::from(args.get(i).expect("--db needs a path"));
            }
            "--oracle-a" => {
                i += 1;
                oracle_a = args.get(i).expect("--oracle-a needs a URL").clone();
            }
            "--oracle-b" => {
                i += 1;
                oracle_b = args.get(i).expect("--oracle-b needs a URL").clone();
            }
            "--port" => {
                i += 1;
                port = args
                    .get(i)
                    .expect("--port needs a number")
                    .parse()
                    .expect("--port must be a u16");
            }
            other => panic!("unknown flag: {other}"),
        }
        i += 1;
    }
    Flags { db, oracle_a, oracle_b, port }
}

#[tokio::main]
async fn main() {
    let flags = parse_flags();

    let conn = inferred_duckdb::open(&flags.db).expect("open store");
    let state = AppState {
        db: Arc::new(Mutex::new(conn)),
        oracle_a: flags.oracle_a,
        oracle_b: flags.oracle_b,
    };

    let addr = format!("127.0.0.1:{}", flags.port);
    let listener = tokio::net::TcpListener::bind(&addr)
        .await
        .unwrap_or_else(|e| panic!("bind {addr}: {e}"));
    println!("lineageq_api listening on http://{addr}");

    axum::serve(listener, app(state)).await.expect("serve");
}
