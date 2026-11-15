"""List every `x in NAME` / `x not in NAME` that sits inside a loop or comprehension, with the
line where NAME was last assigned, so list-typed containers (O(n) membership) can be checked by eye."""
import ast, sys
for path in sys.argv[1:]:
    src = open(path).read(); tree = ast.parse(src)
    assigned = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for t in node.targets:
                for n in ast.walk(t):
                    if isinstance(n, ast.Name):
                        assigned.setdefault(n.id, []).append((node.lineno, ast.get_source_segment(src, node.value)[:50]))
    def visit(node, in_loop):
        loopish = isinstance(node, (ast.For, ast.While, ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp))
        if isinstance(node, ast.Compare) and in_loop:
            for op, comp in zip(node.ops, node.comparators):
                if isinstance(op, (ast.In, ast.NotIn)) and isinstance(comp, ast.Name):
                    defs = assigned.get(comp.id, [])
                    kinds = {d[1].split("(")[0].split("[")[0].strip() for d in defs}
                    flag = "LIST?" if any(d[1].startswith(("[", "list(", "sorted(")) for d in defs) else ""
                    print(f"{path}:{node.lineno}: in {comp.id}  {flag}  defs={[d[1] for d in defs][:2]}")
        for c in ast.iter_child_nodes(node):
            visit(c, in_loop or loopish)
    visit(tree, False)
