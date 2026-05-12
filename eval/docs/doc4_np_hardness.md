# NP-Hardness Reductions and Approximation Lower Bounds

## 1. Computational Problems and Reductions

A *decision problem* is a function mapping problem instances to {YES, NO}. We say a
problem L is in the class **P** if there exists a deterministic algorithm solving every
instance of L in time polynomial in the input size n. The class **NP** contains all
problems whose YES-instances have polynomial-length certificates verifiable in
polynomial time.

A central concept in complexity theory is the polynomial-time many-one reduction.
Given two decision problems A and B, we write A ≤_p B if there exists a polynomial-time
computable function f such that x ∈ A if and only if f(x) ∈ B. Intuitively, B is
"at least as hard" as A. A problem B is **NP-hard** if every problem in NP reduces to B
in polynomial time. If additionally B ∈ NP, then B is **NP-complete**.

The canonical NP-complete problem is 3-SAT. An instance of 3-SAT consists of a Boolean
formula φ in conjunctive normal form where every clause contains exactly three literals.
The question is whether there exists a truth assignment satisfying all clauses. Cook and
Levin independently showed in 1971 that every NP problem reduces to SAT in polynomial
time, and the restriction to 3-literal clauses preserves NP-completeness.

## 2. The Vertex Cover Problem

Given an undirected graph G = (V, E), a *vertex cover* is a subset S ⊆ V such that
every edge (u, v) ∈ E has at least one endpoint in S. The **Minimum Vertex Cover**
problem asks for the smallest such set. A dual view: the complement V \ S of a vertex
cover is an independent set — a set of vertices with no edges between them. Therefore,
Minimum Vertex Cover and Maximum Independent Set are equivalent in the sense that
solving one immediately solves the other.

Minimum Vertex Cover is NP-hard. The reduction is from 3-SAT: given a 3-CNF formula φ
with variables x_1, ..., x_n and clauses C_1, ..., C_m, we construct a graph G such that
G has a vertex cover of size k if and only if φ is satisfiable. The construction creates
a *variable gadget* — a pair of nodes (x_i, ¬x_i) connected by an edge — for each
variable, and a *clause gadget* — a triangle on three nodes (l_1, l_2, l_3) — for each
clause. Edges between gadgets enforce consistency. This reduction runs in polynomial time
and the correctness proof follows from case analysis.

## 3. Approximation and Inapproximability

Since NP-hard optimisation problems are unlikely to have exact polynomial-time solutions,
we ask: how close can an efficient algorithm get? An algorithm A is an *α-approximation*
for a minimisation problem if for every instance I it returns a solution with cost at
most α · OPT(I), where OPT(I) denotes the optimal value.

The simple greedy 2-approximation for Vertex Cover works as follows: repeatedly pick any
uncovered edge (u, v), add both u and v to the cover, and remove all edges incident to u
or v. The algorithm terminates with a valid cover whose size is at most twice the
optimum, because each chosen edge belongs to a maximal matching and every optimal cover
must include at least one endpoint of every matching edge.

Beating this factor of 2 is believed to be hard. Specifically, the **Unique Games
Conjecture** (Khot, 2002) implies that Minimum Vertex Cover cannot be approximated
within any factor better than 2 − ε for any ε > 0, assuming P ≠ NP. Whether the factor
2 barrier can be broken unconditionally remains one of the central open questions in
approximation complexity.

## 4. The PCP Theorem and Hardness of Approximation

The **PCP Theorem** states that NP = PCP(O(log n), O(1)): every NP problem has a
probabilistically checkable proof system that reads only a constant number of bits and
accepts correct proofs with probability 1 while rejecting incorrect proofs with
probability at least 1/2. This theorem is the foundation of essentially all
inapproximability results.

As a direct corollary, Max-3-SAT — the problem of maximising the number of satisfied
clauses in a 3-CNF formula — cannot be approximated beyond a ratio of 7/8 + ε unless
P = NP. The constant 7/8 matches the expected fraction of clauses satisfied by a random
assignment, showing that the naive random algorithm is essentially optimal.
