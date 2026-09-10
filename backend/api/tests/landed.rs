//! `LANDED` and the router can never disagree (Ruling D6).
//!
//! **What this checks, and why it changed in M4b.** Until Task 14 there was a `/api/*`
//! fallback that forwarded every unlanded name to a Python oracle, so "is this name
//! landed?" was answered by whether the request came back as `502` (the forwarder's
//! unreachable signal, made deterministic by pointing `oracle_a` at a closed port). Task
//! 14 deleted the fallback and the oracle with it: every name in `ALL_ROUTES` is landed,
//! an unlanded `/api/*` path is now a plain `404`, and the question this file asks is the
//! simpler one it always meant — every name the two lists carry has a handler wired up,
//! and nothing that is not a question answers at all.

mod support;
use support::get_raw;

#[tokio::test]
async fn every_named_question_is_wired_and_nothing_else_answers() {
    assert_eq!(
        lineageq_api::LANDED, lineageq_api::ALL_ROUTES,
        "Task 14 (M4b): with the forwarder gone the two lists are the same list"
    );
    for name in lineageq_api::ALL_ROUTES {
        let res = get_raw(&format!("/api/{name}")).await;
        // Called with no arguments most of these answer `400 fileid is required`, and the
        // POSTs answer `405`; what matters is that *something here* answered, i.e. axum
        // matched a route. A missing handler is a 404, and nothing else is.
        assert_ne!(
            res.status, 404,
            "{name} is in ALL_ROUTES but `app()` wires no handler for it"
        );
    }
    // ... and a name that is not a question of ours is a real 404 now, not a forward.
    let res = get_raw("/api/not_a_question_this_api_answers").await;
    assert_eq!(
        res.status, 404,
        "with `oracle.rs` deleted an unknown /api/ path is a 404, not a 502 from a forwarder"
    );
}
