# Unsat Viz Tool

Unsat Viz Tool generates visual explanations for inconsistent Answer Set Programming (ASP) programs in the form of graph visualizations.

The tool assumes that the ASP encoding correctly models the problem domain and focuses on explaining unsatisfiable instances rather than debugging modeling errors. The goal is to help users understand why a particular problem instance has no solution. Explanations are generated on the problem-domain level rather than on the level of ASP rules.

To achieve this, the tool combines two complementary explanation approaches:

* **Omission-based abstraction** identifies parts of the instance that can be omitted while preserving inconsistency. These elements are visually de-emphasized and provide a global explanation of the inconsistency.

* **Candidate conflict highlighting** explains why a specific solution candidate is not a valid solution. It analyzes violations in a relaxed version of the program and highlights domain structures associated with violated constraints. These highlighted structures provide local explanations of potential causes of inconsistency.

The final visualization shows both perspectives.

At present, the implementation is limited to graph-based domains. The visualization and explanation mechanisms operate on the domain predicates `node/1` and `link/2`, which represent graph nodes and edges. Additional predicates may be used within the ASP encoding, but only nodes and links can currently be visualized and highlighted as part of the generated explanations.

The current prototype has been evaluated on graph coloring instances.
Examples of encodings, problem instances, and visualization specifications are provided in the `examples` directory. These examples can be used as a starting point for applying the tool to custom ASP encodings and instances.

---

## Requirements

* Python
* `clingo`
* `clingraph`

Install:

```bash
pip install -e .
```

---

## Required Inputs

The following files are needed:

### 1. Instance

```prolog
node(1).
node(2).
...
link(1,2).
...
```

### 2. Encoding

The original ASP encoding.
 
Note: 
Domain predicates (like node/1 and edge/2 for the graph coloring example) have to appear in every rule body where their variables are used.

Example:

```prolog
% Guess colours.
chosenColour(N,C) :- not notchosenColour(N,C), node(N), colour(C).
notchosenColour(N,C) :- not chosenColour(N,C), node(N), colour(C).

% At least one color per node.
:- node(X), not colored(X).

colored(X) :- chosenColour(X,C), node(X), colour(C).

% Only one color per node.
:- chosenColour(N,C1), chosenColour(N,C2),
   C1 != C2,
   node(N),
   colour(C1),
   colour(C2).

% No two adjacent nodes have the same colour.
:- link(X,Y),
   chosenColour(X,C),
   chosenColour(Y,C),
   node(X),
   node(Y),
   colour(C).
```

### 3. Visualization (`viz.lp`)

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

# Pipeline

---

## 1. Generate omission-tool files

Generate the omission-aware encoding and auxiliary omission files.

```bash
python src/unsat_viz_tool/omission_tool/generate_omission_files.py \
  examples/graph_coloring/graphcoloring.lp \
  node \
  --target-arity 1 \
  --context-preds colour \
  --out-dir out/graph_coloring/encoding
```

Generated files:

```text
out/graph_coloring/encoding/
    graphcoloring_main.lp
    guess_atoms_to_omit_forgrounding.lp
    guess_atoms_to_omit.lp
    infer_omitted_atoms.lp
```

---

## 2. Compute omission result

```bash
python src/unsat_viz_tool/omission_tool/compute_max_omission.py \
  examples/graph_coloring/graph_ex.lp \
  out/graph_coloring/encoding/graphcoloring_main.lp \
  3 \
  node \
  --helper-dir out/graph_coloring/encoding \
  --out-dir out/graph_coloring/graph_ex/omission
```

Generated file:

```text
out/graph_coloring/graph_ex/omission/omission_result.lp
```

Example:

```prolog
output_omitted(atom(node(4))).
output_omitted(atom(node(5))).
.
.
.

omitted(X) :- output_omitted(atom(X)).
```

---

## 3. Transform encoding

Transform the omission-aware encoding into relaxed and cleaned versions for unsat visualization.

```bash
python -m unsat_viz_tool.cli transform \
  --encoding out/graph_coloring/encoding/graphcoloring_main.lp \
  --out-dir out/graph_coloring/graph_ex/transform
```

Generated:

```text
out/graph_coloring/graph_ex/transform/
    cleaned_encoding.lp
    relaxed.lp
    meta.json
```

---

## 4. Solve (find violations)

```bash
python -m unsat_viz_tool.cli solve \
  --instance examples/graph_coloring/graph_ex.lp \
  --omission out/graph_coloring/graph_ex/omission/omission_result.lp \
  --cleaned-encoding out/graph_coloring/graph_ex/transform/cleaned_encoding.lp \
  --relaxed out/graph_coloring/graph_ex/transform/relaxed.lp \
  --out-dir out/graph_coloring/graph_ex/solve
```

Generated:

```text
out/graph_coloring/graph_ex/solve/
    violations.json
```

---

## 5. Generate overlay

```bash
python -m unsat_viz_tool.cli overlay \
  --meta out/graph_coloring/graph_ex/transform/meta.json \
  --violations out/graph_coloring/graph_ex/solve/violations.json \
  --out out/graph_coloring/graph_ex/overlay/overlay.lp
```

---

## 6. Render

```bash
python -m unsat_viz_tool.cli render \
  --model out/graph_coloring/graph_ex/solve/selected_model.lp \
  --viz examples/graph_coloring/viz.lp \
  --overlay out/graph_coloring/graph_ex/overlay/overlay.lp \
  --out-dir out/graph_coloring/graph_ex/render \
  --format png
```

---

## Output

```text
out/graph_coloring/graph_ex/render/0/default.png
```

Graph with violated nodes/edges highlighted.

---

## Notes

* The tool assumes that the ASP encoding correctly models the problem domain.
* Explanations are generated for unsatisfiable instances.
* Omission-based abstraction and conflict highlighting are combined into a single visualization.
* The highlighted conflict represents a candidate explanation and is not guaranteed to be the unique reason for inconsistency.
* Problem encodings and visualization specifications can be reused across multiple instances of the same domain.
* Intermediate files are preserved to allow inspection of individual processing stages.

---

## Limitations

* Assumes domain predicates appear in rule bodies for all used variables
* The current prototype is restricted to graph-based domains.
* Visual explanations operate on the domain predicates node/1 and link/2.
* The approach currently supports only a restricted ASP fragment.
* The highlighted conflict is not guaranteed to correspond to unique cause of inconsistency.
* Rule-based explanations are currently available only through intermediate output files.
* The workflow is not fully automated. Individual pipeline stages must currently be executed manually by the user through separate terminal commands. Example commands for all stages are provided in the pipeline description.

---

## Generating multiple optimal solution explanations
Following commands are used:

```bash
python -m unsat_viz_tool.cli solve \
  --instance examples/graph_coloring/g1.lp \
  --omission out/graph_coloring/g1/omission/omission_result.lp \
  --cleaned-encoding out/graph_coloring/g1/transform/cleaned_encoding.lp \
  --relaxed out/graph_coloring/g1/transform/relaxed.lp \
  --out-dir out/graph_coloring/g1/solve \
  --mode diverse-optimal \
  --max-models 200
```

Generated:
```text
out/graph_coloring/g1/solve/explanation_0/violations.json
out/graph_coloring/g1/solve/explanation_1/violations.json
```


```bash
python -m unsat_viz_tool.cli overlay \
  --meta out/graph_coloring/g1/transform/meta.json \
  --violations out/graph_coloring/g1/solve/explanation_0/violations.json \
  --out out/graph_coloring/g1/overlay/explanation_0/overlay.lp
```
Generated:
```text
out/graph_coloring/g1/overlay/explanation_0/overlay.lp
```


```bash
python -m unsat_viz_tool.cli overlay \
  --meta out/graph_coloring/g1/transform/meta.json \
  --violations out/graph_coloring/g1/solve/explanation_1/violations.json \
  --out out/graph_coloring/g1/overlay/explanation_1/overlay.lp
```
Generated:
```text
out/graph_coloring/g1/overlay/explanation_1/overlay.lp
```


```bash
python -m unsat_viz_tool.cli render \
  --model out/graph_coloring/g1/solve/selected_model.lp \
  --viz examples/graph_coloring/viz.lp \
  --overlay out/graph_coloring/g1/overlay/explanation_0/overlay.lp \
  --out-dir out/graph_coloring/g1/render/explanation_0 \
  --format png
```

Generated:
```text
out/graph_coloring/g1/render/explanation_0
```


```bash
python -m unsat_viz_tool.cli render \
  --model out/graph_coloring/g1/solve/selected_model.lp \
  --viz examples/graph_coloring/viz.lp \
  --overlay out/graph_coloring/g1/overlay/explanation_1/overlay.lp \
  --out-dir out/graph_coloring/g1/render/explanation_1 \
  --format png
```

Generated:
```text
out/graph_coloring/g1/render/explanation_1
```