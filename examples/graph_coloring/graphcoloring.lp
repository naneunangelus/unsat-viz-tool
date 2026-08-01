% Guess colours.
chosenColour(N,C) :- not notchosenColour(N,C), node(N), colour(C).
notchosenColour(N,C) :- not chosenColour(N,C), node(N), colour(C).

% At least one color per node.
:- node(X), not colored(X).
colored(X) :- chosenColour(X,C), node(X), colour(C).
% bug : node(N) instead of node(X)

% Only one color per node.
:- chosenColour(N,C1), chosenColour(N,C2), C1!=C2, node(N), colour(C1), colour(C2). 

% No two adjacent nodes have the same colour. 
:- link(X,Y), chosenColour(X,C), chosenColour(Y,C), node(X), node(Y), colour(C).
