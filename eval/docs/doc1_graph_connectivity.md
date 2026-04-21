# Graph Connectivity

## 1. Basic Definitions

**Definition (Graph):** A graph $G = (V, E)$ consists of a finite nonempty set $V$ of *vertices* and a set $E \subseteq \binom{V}{2}$ of *edges*, where each edge is an unordered pair of distinct vertices.

**Definition (Path):** A *path* in $G$ is a sequence of vertices $v_1, v_2, \ldots, v_k$ such that $\{v_i, v_{i+1}\} \in E$ for all $1 \leq i < k$, and all vertices are distinct. The *length* of the path is $k - 1$.

**Definition (Connected Graph):** A graph $G$ is *connected* if for every pair of vertices $u, v \in V$ there exists a path from $u$ to $v$ in $G$.

**Definition (Connected Component):** A *connected component* of $G$ is a maximal connected subgraph of $G$.

## 2. Cut Vertices and Bridges

**Definition (Cut Vertex):** A vertex $v \in V$ is a *cut vertex* (or *articulation point*) of $G$ if the graph $G - v$ (obtained by removing $v$ and all its incident edges) has more connected components than $G$.

**Definition (Bridge):** An edge $e \in E$ is a *bridge* of $G$ if the graph $G - e$ has more connected components than $G$.

**Lemma (Bridge Characterization):** An edge $e = \{u, v\}$ is a bridge of $G$ if and only if $e$ does not lie on any cycle in $G$.

*Proof sketch:* If $e$ lies on a cycle $C$, then removing $e$ still leaves a path between $u$ and $v$ via the rest of $C$, so connectivity is preserved. Conversely, if $e$ is not on any cycle, then the only path between $u$ and $v$ uses $e$, so removing it disconnects $G$. $\square$

**Theorem (DFS Bridge Detection):** All bridges of a connected graph $G = (V, E)$ can be found in $O(|V| + |E|)$ time using a depth-first search.

## 3. $k$-Connectivity

**Definition ($k$-Connected Graph):** A graph $G$ with $|V| \geq k+1$ is *$k$-connected* if $G$ remains connected after the removal of any set of fewer than $k$ vertices. The *connectivity* $\kappa(G)$ is the largest $k$ for which $G$ is $k$-connected.

**Example:** The complete graph $K_n$ is $(n-1)$-connected. A cycle $C_n$ on $n \geq 3$ vertices is 2-connected (removing any single vertex leaves the graph connected, but removing two adjacent vertices disconnects it).

**Theorem (Menger's Theorem):** For any two non-adjacent vertices $s$ and $t$ in $G$, the maximum number of internally vertex-disjoint paths from $s$ to $t$ equals the minimum number of vertices whose removal disconnects $s$ from $t$.

**Open Question:** What is the best known algorithm for computing $\kappa(G)$ for general graphs, and can it be improved below $O(|V|^{1.5})$?

## 4. Euler Paths

**Definition (Eulerian Circuit):** An *Eulerian circuit* of $G$ is a closed walk that visits every edge exactly once.

**Theorem (Euler's Theorem):** A connected graph $G$ has an Eulerian circuit if and only if every vertex of $G$ has even degree.

**Note:** The analogous condition for an *Eulerian path* (open walk visiting every edge once) is that $G$ has exactly two vertices of odd degree.
