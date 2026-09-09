from orderer import Flow, compute_order

def chain():  # a -> b -> c
    return [Flow("a.sas", "b.sas", ("work.t1",)),
            Flow("b.sas", "c.sas", ("work.t2",))]

def test_dag_scores_are_levels():
    r = compute_order(chain())
    assert (r["a.sas"].score, r["b.sas"].score, r["c.sas"].score) == (0, 1, 2)
    assert not r["b.sas"].cyclic

def test_score0_reasoning_no_flows_in():
    r = compute_order(chain())
    assert "no flows in" in r["a.sas"].reasoning

def test_reasoning_names_incoming_flow():
    r = compute_order(chain())
    assert "work.t2 -> c.sas" in r["c.sas"].reasoning

def test_cycle_shared_score_members_and_break():
    flows = chain() + [Flow("c.sas", "a.sas", ("work.t3",))]
    r = compute_order(flows)
    assert r["a.sas"].score == r["b.sas"].score == r["c.sas"].score
    assert r["a.sas"].cyclic and r["a.sas"].cycle_members == ["a.sas", "b.sas", "c.sas"]
    assert r["a.sas"].break_suggestion == ("c.sas", "a.sas")   # the back edge
    assert "data feeds back into where it started" in r["a.sas"].reasoning
    assert "break the flow c.sas -> a.sas" in r["a.sas"].reasoning

def test_self_loop_is_cycle():
    r = compute_order([Flow("x.sas", "x.sas", ("work.t",))])
    assert r["x.sas"].cyclic and r["x.sas"].cycle_members == ["x.sas"]

def test_two_disjoint_cycles_get_distinct_ids():
    flows = [Flow("a.sas", "b.sas", ("t1",)), Flow("b.sas", "a.sas", ("t2",)),
             Flow("c.sas", "d.sas", ("t3",)), Flow("d.sas", "c.sas", ("t4",))]
    r = compute_order(flows)
    assert r["a.sas"].cycle_id != r["c.sas"].cycle_id

def test_deterministic():
    flows = chain() + [Flow("c.sas", "a.sas", ("t",))]
    assert compute_order(flows) == compute_order(list(reversed(flows)))

def test_isolated_node_via_nodes_arg():
    r = compute_order(chain(), nodes=["a.sas", "b.sas", "c.sas", "lone.sas"])
    assert r["lone.sas"].score == 0 and not r["lone.sas"].cyclic
