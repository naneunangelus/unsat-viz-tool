# Unsat Viz Tool

Explain why an ASP program is unsatisfiable by highlighting violated parts in a graph.

---

## Requirements

* Python 3.10+
* `clingo`
* `clingraph`

Install:

```bash
pip install -e .
```

---

## Required Inputs

You need 4 files:

### 1. Instance

```prolog
node(1..5).
link(1,2).
...
```

### 2. Encoding (with annotations)

```prolog
%!unsat no_same_colour
%!affects edge(X,Y)
%!affects node(X)
%!affects node(Y)

f :- link(X,Y), X < Y,
     chosenColour(X,C),
     chosenColour(Y,C),
     not f.
```

### 3. Omission result

```prolog
output_omitted(atom(node(4))).
...
omitted(X) :- output_omitted(atom(X)).
```

### 4. Visualization (`viz.lp`)

```prolog
edge((X,Y)) :- link(X,Y), X < Y.
node(X) :- node(X).

attr(node, X, label, X) :- node(X).
attr(node, X, style, filled) :- node(X).

#show node/1.
#show edge/1.
#show attr/4.
```

---

## Run

### 1. Transform encoding

```bash
python -m unsat_viz_tool.cli transform \
  --encoding examples/graph_coloring/graphcoloring.lp \
  --out-dir out
```

---

### 2. Solve (find violations)

```bash
python -m unsat_viz_tool.cli solve \
  --instance examples/graph_coloring/graph_ex.lp \
  --omission examples/graph_coloring/omission_result.lp \
  --cleaned-encoding out/cleaned_encoding.lp \
  --relaxed out/relaxed.lp \
  --out-dir out
```

---

### 3. Generate overlay

```bash
python -m unsat_viz_tool.cli overlay \
  --meta out/meta.json \
  --violations out/violations.json \
  --out out/overlay.lp
```

---

### 4. Render

```bash
python -m unsat_viz_tool.cli render \
  --instance examples/graph_coloring/graph_ex.lp \
  --omission examples/graph_coloring/omission_result.lp \
  --cleaned-encoding out/cleaned_encoding.lp \
  --viz examples/graph_coloring/viz.lp \
  --overlay out/overlay.lp \
  --out-dir out/graph_ex \
  --format png
```

---

## Output

```text
out/graph_ex/0/default.png
```

Graph with violated nodes/edges highlighted.

---

## Notes

- Only annotated constraints are relaxed  
- Other rules remain unchanged  
- Multiple violations are supported  
- Intermediate files are kept for debugging  

## Limitations

- Requires manual annotations  
- Visualization depends on user encoding  
- No support yet for multiple rule visualization styles  

