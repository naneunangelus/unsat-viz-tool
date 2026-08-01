node(X) :- node(X).

edge((X,Y)) :- link(X,Y), X < Y.

attr(node, X, label, X) :-
    node(X).

attr(node, X, style, filled) :-
    node(X).

attr(edge, (X,Y), label, "") :-
    edge((X,Y)).


#show node/1.
#show edge/1.
#show attr/4.