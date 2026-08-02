% Core blocker: K5
node(1).
node(2).
node(3).
node(4).
node(5).

% Extra non-blocker nodes
node(6).
node(7).

colour(blue).
colour(green).
colour(yellow).
colour(violet).

% Complete graph on nodes 1..5
link(1,2).
link(1,3).
link(1,4).
link(1,5).

link(2,3).
link(2,4).
link(2,5).

link(3,4).
link(3,5).

link(4,5).

% Extra satisfiable structure outside the blocker
link(5,6).
link(6,7).