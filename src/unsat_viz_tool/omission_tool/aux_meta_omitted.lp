rule(pos(atom(omitted(X))),pos(conjunction(-1))) :- guessedomitted(X).
omitted(atom(X)) :- guessedomitted(X).

#show omitted/1.

%#maximize {1, atom(A) : omitted(atom(A)), elem(atom(A))}.
