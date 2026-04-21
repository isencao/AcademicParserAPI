# Approximation Algorithms

## 1. Optimization Problems and Approximation

**Definition (Optimization Problem):** An *optimization problem* $\Pi$ consists of a set of instances. For each instance $I$, there is a set of feasible solutions $\text{SOL}(I)$ and an objective function $\text{obj}: \text{SOL}(I) \to \mathbb{R}_{\geq 0}$. We seek a solution $S^* \in \text{SOL}(I)$ that minimizes (or maximizes) $\text{obj}(S)$.

**Definition (Approximation Ratio):** An algorithm $A$ has *approximation ratio* $\alpha \geq 1$ for a minimization problem if, for every instance $I$, $A(I) \leq \alpha \cdot \text{OPT}(I)$, where $A(I)$ is the cost of the solution returned by $A$ and $\text{OPT}(I)$ is the cost of an optimal solution.

**Definition (PTAS):** A *polynomial-time approximation scheme* (PTAS) for a minimization problem is a family of algorithms $\{A_\varepsilon\}_{\varepsilon > 0}$ such that for every fixed $\varepsilon > 0$, $A_\varepsilon$ runs in polynomial time and achieves approximation ratio $1 + \varepsilon$.

**Definition (APX):** The complexity class *APX* contains all NP optimization problems that admit a constant-factor approximation algorithm (i.e., approximation ratio $\alpha$ for some constant $\alpha$).

## 2. Vertex Cover Approximation

**Definition (Vertex Cover):** A *vertex cover* of $G = (V, E)$ is a set $C \subseteq V$ such that for every edge $\{u, v\} \in E$, at least one of $u$ or $v$ belongs to $C$.

**Theorem (2-Approximation for Vertex Cover):** There exists a polynomial-time 2-approximation algorithm for the minimum vertex cover problem.

*Proof:* The following greedy algorithm achieves ratio 2: pick any uncovered edge $\{u, v\}$, add both $u$ and $v$ to the cover $C$, remove all edges incident to $u$ or $v$, repeat. Let $M$ be the set of edges picked. Since $M$ is a matching (no two share an endpoint), $\text{OPT} \geq |M|$. The algorithm outputs $|C| = 2|M| \leq 2 \cdot \text{OPT}$. $\square$

**Note:** It is known that Vertex Cover is APX-hard (assuming the Unique Games Conjecture, a ratio below 2 is NP-hard). The 2-approximation above is essentially tight under this conjecture.

## 3. Set Cover

**Definition (Set Cover):** Given a universe $U$ of $n$ elements and a family $\mathcal{F}$ of subsets of $U$, find the smallest sub-collection $\mathcal{C} \subseteq \mathcal{F}$ such that $\bigcup_{S \in \mathcal{C}} S = U$.

**Theorem (Greedy $H_n$-Approximation):** The greedy algorithm for Set Cover — at each step, pick the set that covers the most uncovered elements — achieves approximation ratio $H_n = \sum_{i=1}^{n} \frac{1}{i} = \Theta(\log n)$.

**Lemma (Greedy Progress):** After the greedy algorithm selects its first $k$ sets, the number of uncovered elements is at most $n \cdot (1 - 1/\text{OPT})^k \leq n \cdot e^{-k/\text{OPT}}$.

**Example:** Let $U = \{1, 2, 3, 4, 5, 6\}$ and $\mathcal{F} = \{\{1,2,3,4\}, \{1,3,5\}, \{2,4,6\}, \{5,6\}\}$. The greedy algorithm first picks $\{1,2,3,4\}$ (covers 4 elements), then $\{5,6\}$ (covers 2 remaining), giving a cover of size 2, which is optimal.

**Open Question:** Is there a polynomial-time algorithm achieving approximation ratio $o(\log n)$ for Set Cover? Current inapproximability results suggest $(1 - o(1)) \ln n$ is a lower bound under $P \neq NP$.
