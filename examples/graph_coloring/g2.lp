% nodes
node(1).
node(2).
node(3).
node(4).
node(5).
node(6).
node(7).
node(8).

% 3 colors
colour(red).
colour(green).
colour(blue).

% central K4
link(1,2).
link(1,3).
link(1,4).
link(2,3).
link(2,4).
link(3,4).

% outer structure
link(2,7).
link(3,7).

link(1,5).
link(4,5).

link(2,6).
link(1,6).

link(3,8).
link(4,8).