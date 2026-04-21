# Matching in Graphs

## 1. Matchings

**Definition (Matching):** A *matching* in a graph $G = (V, E)$ is a set $M \subseteq E$ of edges such that no two edges in $M$ share a common endpoint. A vertex $v$ is *matched* if some edge in $M$ is incident to $v$; otherwise $v$ is *free* (or *exposed*).

**Definition (Maximum Matching):** A matching $M$ is a *maximum matching* if $|M|$ is as large as possible, i.e., no matching in $G$ has more edges than $M$.

**Definition (Perfect Matching):** A matching $M$ is *perfect* if every vertex of $G$ is matched, i.e., $|M| = |V|/2$.

**Definition (Augmenting Path):** Given a matching $M$, an *augmenting path* is a path $P = v_1, v_2, \ldots, v_{2k+1}$ such that $v_1$ and $v_{2k+1}$ are free, and the edges alternate between $E \setminus M$ and $M$ (i.e., odd-indexed edges are unmatched, even-indexed edges are matched).

## 2. Berge's Theorem

**Theorem (Berge's Theorem, 1957):** A matching $M$ in $G$ is maximum if and only if $G$ contains no $M$-augmenting path.

*Proof sketch:* ($\Rightarrow$) If an augmenting path $P$ exists, we can obtain a larger matching by flipping the matched and unmatched edges along $P$, contradicting maximality. ($\Leftarrow$) If $M$ is not maximum, let $M^*$ be a larger matching. Consider $M \oplus M^*$ (symmetric difference). This graph has maximum degree 2 and each connected component is a path or an even cycle. Since $|M^*| > |M|$, at least one component is a path that starts and ends with an edge from $M^*$; this path is an $M$-augmenting path. $\square$

**Lemma (Symmetric Difference):** Let $M$ and $M'$ be matchings in $G$. The subgraph $M \oplus M' = (M \setminus M') \cup (M' \setminus M)$ consists of vertex-disjoint paths and even cycles, where edges alternate between $M$ and $M'$.

## 3. Bipartite Matching

**Definition (Bipartite Graph):** A graph $G = (V, E)$ is *bipartite* if $V$ can be partitioned into two sets $A$ and $B$ such that every edge has one endpoint in $A$ and one in $B$. We write $G = (A \cup B, E)$.

**Theorem (König's Theorem, 1931):** In any bipartite graph, the size of a maximum matching equals the size of a minimum vertex cover.

**Example:** Consider the bipartite graph with $A = \{a_1, a_2, a_3\}$, $B = \{b_1, b_2, b_3\}$, and edges $\{a_1b_1, a_1b_2, a_2b_2, a_3b_3\}$. A maximum matching is $M = \{a_1b_1, a_2b_2, a_3b_3\}$ with $|M| = 3$. A minimum vertex cover is $\{a_1, a_2, a_3\}$, confirming König's Theorem.

**Theorem (Hall's Marriage Theorem, 1935):** A bipartite graph $G = (A \cup B, E)$ has a matching that saturates every vertex of $A$ if and only if for every subset $S \subseteq A$, $|N(S)| \geq |S|$, where $N(S)$ denotes the set of neighbors of $S$ in $B$.

**Open Question:** Can maximum bipartite matching be computed in $o(m \sqrt{n})$ time (below the Hopcroft–Karp bound), perhaps via fast matrix multiplication or algebraic techniques?
