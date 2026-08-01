% Guess whether each node is selected.
inSet(N) :- not outSet(N), node(N).
outSet(N) :- not inSet(N), node(N).

% Select four distinct witnesses.
chosen(1,N) :- inSet(N), node(N), not notChosen(1,N).
notChosen(1,N) :- inSet(N), node(N), not chosen(1,N).

chosen(2,N) :- inSet(N), node(N), not notChosen(2,N).
notChosen(2,N) :- inSet(N), node(N), not chosen(2,N).

chosen(3,N) :- inSet(N), node(N), not notChosen(3,N).
notChosen(3,N) :- inSet(N), node(N), not chosen(3,N).

chosen(4,N) :- inSet(N), node(N), not notChosen(4,N).
notChosen(4,N) :- inSet(N), node(N), not chosen(4,N).

% Each position must choose some node.
:- not filled(1).
filled(1) :- chosen(1,N), node(N).

:- not filled(2).
filled(2) :- chosen(2,N), node(N).

:- not filled(3).
filled(3) :- chosen(3,N), node(N).

:- not filled(4).
filled(4) :- chosen(4,N), node(N).

% Positions must choose distinct nodes.
:- chosen(P1,N), chosen(P2,N), P1 != P2, node(N).

% Chosen nodes must form an independent set.
:- chosen(P1,X), chosen(P2,Y), P1 != P2, link(X,Y), node(X), node(Y).