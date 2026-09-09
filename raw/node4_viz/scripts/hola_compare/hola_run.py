import json, sys, time, inspect
from hola_graph import HolaGraph
print('connect sig:', inspect.signature(HolaGraph.connect))
for name in sys.argv[1:]:
    d = json.load(open(f'{name}.json'))
    g = HolaGraph()
    by = {}
    for n in d['nodes']:
        w = max(140, 7 * len(n['label']) + 40); h = 44
        by[n['id']] = g.add_node(w, h, label=n['label'])
    seen = set()
    for e in d['edges']:
        k = (e['src'], e['dst'])
        if k in seen or e['src'] == e['dst']: continue
        seen.add(k); g.connect(by[e['src']], by[e['dst']])
    t = time.time(); g.layout(); dt = time.time() - t
    xs = [n.x for n in g.nodes]; ys = [n.y for n in g.nodes]
    print(f'{name}: nodes={g.num_nodes} edges={g.num_edges} layout={dt*1000:.0f}ms bbox={max(xs)-min(xs):.0f}x{max(ys)-min(ys):.0f}')
    g.to_svg(f'{name}_hola.svg'); g.to_json(f'{name}_hola.json')
