"""DEVELOPMENT DATA — illustrative users, resources and engagement.

Nothing in this module is a real publication. There are deliberately no DOIs,
ISBNs, arXiv IDs, citation counts or YouTube video IDs: inventing identifiers
would poison deduplication and send users to broken links. Every resource is
attributed to a single obvious source ("NEXORA Demo Corpus") and carries
`flags.is_seed_data = True` plus `flags.seed_label`, so the UI can badge it and
`runner.purge_demo()` can delete it.

The prose below is original teaching material written for NEXORA. It is real
enough for the RAG pipeline to chunk, embed and answer questions against, which
is the point of shipping it.
"""

from __future__ import annotations

from app.models.resource import (
    AcademicLevel,
    AccessType,
    Difficulty,
    ResourceType,
)

SEED_LABEL = "DEVELOPMENT DATA — sample record created by scripts/seed.py, not a real publication"
DEMO_SOURCE_NAME = "NEXORA Demo Corpus"
DEMO_SOURCE_LICENSE = "Sample text written for NEXORA (development use only)"

# Every demo account shares this password. It is printed by the CLI after
# seeding and is meaningless outside a local development database.
DEMO_PASSWORD = "Nexora#Demo2026"

# (email, student_id, name, role, department_code, academic_year, semester)
DEMO_USERS: tuple[tuple[str, str | None, str, str, str | None, int | None, int | None], ...] = (
    ("student.demo@nexora.local", "DEMO-CSE-001", "Ananya Sharma",
     "student", "CSE", 2, 4),
    ("student2.demo@nexora.local", "DEMO-ECE-014", "Rohan Verma",
     "student", "ECE", 3, 6),
    ("student3.demo@nexora.local", "DEMO-MATH-007", "Leah Okonkwo",
     "student", "MATH", 1, 2),
    ("faculty.demo@nexora.local", "DEMO-FAC-CSE-01", "Dr. Meera Iyer",
     "faculty", "CSE", None, None),
    ("faculty2.demo@nexora.local", "DEMO-FAC-PHYS-02", "Prof. Daniel Reyes",
     "faculty", "PHYS", None, None),
)

# (user_email, resource_slug, bookmarked, viewed, progress_percent)
DEMO_ENGAGEMENT: tuple[tuple[str, str, bool, bool, int], ...] = (
    ("student.demo@nexora.local", "dsa-arrays-hashing", True, True, 80),
    ("student.demo@nexora.local", "dbms-transactions", True, True, 45),
    ("student.demo@nexora.local", "os-processes-scheduling", False, True, 100),
    ("student.demo@nexora.local", "ml-regularization", True, False, 0),
    ("student.demo@nexora.local", "dns-resolution", False, True, 30),
    ("student2.demo@nexora.local", "dsp-fourier", True, True, 60),
    ("student2.demo@nexora.local", "electronics-opamps", False, True, 15),
    ("student3.demo@nexora.local", "la-eigenvalues", True, True, 90),
    ("student3.demo@nexora.local", "prob-distributions", True, True, 50),
    ("faculty.demo@nexora.local", "dbms-transactions", True, True, 100),
    ("faculty.demo@nexora.local", "ai-search-strategies", True, True, 70),
    ("faculty2.demo@nexora.local", "qm-wavefunctions", True, True, 55),
)

# (user_email, resource_slug, rating, title, body)
DEMO_REVIEWS: tuple[tuple[str, str, int, str | None, str], ...] = (
    ("student.demo@nexora.local", "dsa-arrays-hashing", 5, "Finally understood amortized cost",
     "The resizing-account walkthrough is the clearest explanation I have read. "
     "Worked through the practice table twice and the exam question that used to "
     "stump me became obvious."),
    ("student.demo@nexora.local", "dbms-transactions", 4, "Solid, wants more on isolation levels",
     "Locking and the write-ahead log sections are excellent. I would have liked "
     "one more example contrasting read-committed with snapshot isolation, but "
     "that is a small gap."),
    ("faculty.demo@nexora.local", "dbms-transactions", 5, "Using this in my DBMS class",
     "Assigned chapters 1-3 as pre-reading. Students arrive knowing what a dirty "
     "read is, which buys back a whole lecture."),
    ("student2.demo@nexora.local", "dsp-fourier", 4, None,
     "Good bridge from the continuous transform to what an FFT actually computes. "
     "The bit-reversal diagram helped."),
    ("student3.demo@nexora.local", "la-eigenvalues", 5, "The geometric picture matters",
     "Seeing eigenvectors as directions that survive a transformation made the "
     "algebra stop feeling arbitrary."),
    ("student.demo@nexora.local", "os-processes-scheduling", 3, "Accurate but dry",
     "Correct throughout and the banker's algorithm trace is genuinely useful, "
     "but it reads like a specification. I kept needing to re-read paragraphs."),
)


def _text(*paragraphs: str) -> str:
    return "\n\n".join(p.strip() for p in paragraphs)


# Each entry: slug, type, title, subtitle, department, subjects, topics,
# authors, year, publisher, access, price, difficulty, level, semester,
# keywords, description, text.
DEMO_RESOURCES: tuple[dict, ...] = (
    {
        "slug": "dsa-arrays-hashing",
        "type": ResourceType.STUDY_MATERIAL,
        "title": "Arrays, Hashing and Amortized Cost",
        "subtitle": "A worked primer on the structures underneath every other structure",
        "department": "CSE",
        "subjects": ["CSE-DSA"],
        "topics": ["CSE-DSA-ARRAYS", "CSE-DSA-HASHING", "CSE-DSA-COMPLEXITY-ANALYSIS"],
        "authors": ["NEXORA Curriculum Team"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.BEGINNER,
        "level": AcademicLevel.INTRODUCTORY,
        "semester": 3,
        "keywords": ["array", "dynamic array", "hash table", "amortized analysis",
                     "collision resolution", "big-O"],
        "description": "Contiguous storage, load factors and why a doubling array "
                       "is O(1) per append even though some appends are expensive.",
        "text": _text(
            "An array stores elements in contiguous memory, which is what makes "
            "indexing a single arithmetic operation: the address of element i is "
            "the base address plus i times the element size. Everything costly "
            "about arrays follows from that same fact. Inserting at the front "
            "means shifting every later element one slot right, so it is linear. "
            "Appending at the end touches one slot, so it is constant.",
            "A dynamic array keeps a capacity separate from its length. When an "
            "append finds the two equal, the array allocates a larger block — "
            "conventionally double the old one — copies every element across, and "
            "then writes. That single append cost O(n). But it happens once per n "
            "appends, so across n appends the total copying work is n + n/2 + n/4 "
            "+ ..., which is bounded by 2n. Dividing by n gives an amortized cost "
            "of 2, which is O(1). Amortized analysis is a statement about a whole "
            "sequence, not about any individual operation, and confusing the two is "
            "the most common mistake made with dynamic arrays.",
            "A hash table trades the array's ordered indexing for near-constant "
            "lookup by key. A hash function maps a key to a bucket. Two keys can "
            "land in the same bucket — a collision — and the table resolves it "
            "either by chaining, where each bucket holds a small list, or by open "
            "addressing, where the table probes for the next free slot. The load "
            "factor, entries divided by buckets, controls how often collisions "
            "happen; most implementations rehash into a bigger table when it "
            "passes 0.75.",
            "The practical consequence is that hash lookup is O(1) on average and "
            "O(n) in the worst case, which happens when every key collides. That "
            "worst case is reachable by an adversary who can choose keys, which is "
            "why production runtimes randomize their string hashing per process "
            "rather than using one fixed function.",
            "Practice: build a table of the cost of append, insert-at-front, "
            "lookup-by-index and lookup-by-key for a sorted array, an unsorted "
            "array and a hash table. Then explain in one sentence each why the "
            "array's index lookup beats the hash table's, and why the hash table's "
            "key lookup beats the unsorted array's.",
        ),
    },
    {
        "slug": "dbms-transactions",
        "type": ResourceType.LECTURE_NOTES,
        "title": "Transactions and Concurrency Control",
        "subtitle": "Isolation, locking and the write-ahead log",
        "department": "CSE",
        "subjects": ["CSE-DBMS"],
        "topics": ["CSE-DBMS-TRANSACTIONS-AND-CONCURRENCY", "CSE-DBMS-INDEXING",
                   "CSE-DBMS-NOSQL-DATABASES"],
        "authors": ["NEXORA Curriculum Team", "S. Raghunathan"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.INTERMEDIATE,
        "level": AcademicLevel.CORE,
        "semester": 4,
        "keywords": ["transaction", "ACID", "isolation level", "two-phase locking",
                     "write-ahead log", "serializability", "MVCC"],
        "description": "What a transaction guarantees, the anomalies weaker "
                       "isolation levels permit, and the two mechanisms that "
                       "actually deliver durability and isolation.",
        "text": _text(
            "A transaction is a group of operations the database treats as one "
            "indivisible unit. ACID names the four properties: atomicity, all of "
            "it commits or none of it does; consistency, invariants hold at every "
            "commit boundary; isolation, concurrent transactions do not see each "
            "other's intermediate state; durability, a committed transaction "
            "survives a crash.",
            "Isolation is the expensive one, and databases sell it in grades. Read "
            "uncommitted lets you see another transaction's uncommitted write — a "
            "dirty read — which can be rolled back out from under you. Read "
            "committed prevents dirty reads but still permits a non-repeatable "
            "read: you read the same row twice inside one transaction and get "
            "different values because someone committed in between. Repeatable read "
            "prevents that but still permits a phantom, where a repeated query "
            "returns a new row that matched the predicate. Serializable permits "
            "none of them; it behaves as if the transactions had run one after "
            "another.",
            "Two mechanisms deliver these guarantees. Two-phase locking splits each "
            "transaction into a growing phase where it only acquires locks and a "
            "shrinking phase where it only releases them. That discipline is "
            "provably enough to produce a serializable schedule, and it is why "
            "locks are held until commit rather than released early. The write-"
            "ahead log records a change's before-and-after images on stable storage "
            "before the change reaches the data pages. On recovery the log is "
            "replayed forward for committed transactions and undone backward for "
            "uncommitted ones, which is what makes durability real rather than "
            "aspirational.",
            "Multiversion concurrency control takes a different trade: writers "
            "create a new version of a row and readers pick the newest version "
            "visible to their snapshot. Readers never block writers. The cost is "
            "version storage and a garbage collector, and the semantics are "
            "snapshot isolation rather than full serializability — which admits a "
            "write-skew anomaly that serializable databases must rule out "
            "explicitly.",
            "Deadlock is the predictable failure mode of locking. Two transactions "
            "each hold what the other wants and neither can proceed. Databases "
            "detect this with a wait-for graph and abort one victim, so application "
            "code must be written to retry a transaction on a deadlock error "
            "rather than treating it as a hard failure.",
        ),
    },
    {
        "slug": "os-processes-scheduling",
        "type": ResourceType.BOOK,
        "title": "Processes, Scheduling and Deadlock",
        "subtitle": "How one CPU convincingly pretends to be many",
        "department": "CSE",
        "subjects": ["CSE-OS"],
        "topics": ["CSE-OS-PROCESS-MANAGEMENT", "CSE-OS-PROCESS-SCHEDULING",
                   "CSE-OS-DEADLOCK", "CSE-OS-SYNCHRONIZATION"],
        "authors": ["NEXORA Curriculum Team"],
        "year": 2024,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.INTERMEDIATE,
        "level": AcademicLevel.CORE,
        "semester": 4,
        "keywords": ["process", "context switch", "scheduler", "round robin",
                     "deadlock", "banker's algorithm", "semaphore"],
        "description": "The process abstraction, the scheduling policies that "
                       "allocate CPU time, and the four conditions that make "
                       "deadlock possible.",
        "text": _text(
            "A process is a program in execution plus everything the kernel needs to "
            "stop and restart it: the address space, open file descriptors, "
            "register state and accounting information, gathered into a process "
            "control block. Saving that state and loading another process's state is "
            "a context switch. It is pure overhead — no user work happens during it "
            "— so switching too often wastes cycles and switching too rarely makes "
            "the machine feel unresponsive. Every scheduling policy is a position on "
            "that trade-off.",
            "First-come first-served is simple and starves nobody, but one long job "
            "at the head of the queue delays everything behind it: the convoy "
            "effect. Shortest-job-first minimizes average waiting time and is "
            "provably optimal when you know the runtimes, which you do not, so "
            "real systems estimate them from an exponential average of past "
            "bursts. Round robin preempts after a fixed time quantum, which bounds "
            "response time; with a quantum much larger than a context switch it "
            "approaches first-come first-served, and with a quantum comparable to "
            "one it spends most of its time switching. Multilevel feedback queues "
            "combine the two: new processes enter a high-priority short-quantum "
            "queue and are demoted if they keep using their whole quantum, so "
            "interactive jobs stay snappy and CPU-bound jobs eventually get "
            "throughput-oriented treatment.",
            "Deadlock requires four conditions to hold at once: mutual exclusion, "
            "hold and wait, no preemption, and a circular wait. Break any one and "
            "deadlock becomes impossible. In practice operating systems mostly "
            "decline to prevent it, because the prevention techniques are costly, "
            "and instead detect and recover, or — as most general-purpose systems "
            "do — ignore it on the grounds that it is rare and a reboot fixes it.",
            "The banker's algorithm is the avoidance approach. Before granting a "
            "request the kernel checks whether the system would remain in a safe "
            "state, meaning some ordering of the remaining processes could still "
            "run to completion. It requires every process to declare its maximum "
            "need in advance, which is why it is taught more than deployed.",
            "Synchronization primitives exist because shared mutable state accessed "
            "concurrently produces races. A mutex grants exclusive access and must "
            "be released by the thread that took it. A semaphore is a counted "
            "permit that any thread may release, which makes it usable for "
            "signalling as well as exclusion. Condition variables let a thread wait "
            "for a predicate; the wait must be in a loop, because a wakeup can be "
            "delivered spuriously or consumed by another waiter.",
        ),
    },
    {
        "slug": "ai-search-strategies",
        "type": ResourceType.EBOOK,
        "title": "Search Strategies for Intelligent Agents",
        "subtitle": "From breadth-first to A* and why heuristics must be admissible",
        "department": "CSE",
        "subjects": ["CSE-AI"],
        "topics": ["CSE-AI-SEARCH-STRATEGIES", "CSE-AI-CONSTRAINT-SATISFACTION",
                   "CSE-AI-AUTOMATED-PLANNING"],
        "authors": ["NEXORA Curriculum Team", "P. Deshpande"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.INTERMEDIATE,
        "level": AcademicLevel.CORE,
        "semester": 5,
        "keywords": ["search", "A*", "heuristic", "admissible", "branch and bound",
                     "constraint satisfaction", "state space"],
        "description": "Uninformed and informed search over a state space, the "
                       "admissibility condition that keeps A* optimal, and how "
                       "constraint propagation shrinks the problem before search "
                       "starts.",
        "text": _text(
            "Most classical AI problems can be cast as search: a start state, a set "
            "of operators, a goal test and a path cost. The state space is usually "
            "far too large to enumerate, so the interesting question is which part "
            "of it to expand next.",
            "Uninformed strategies use no domain knowledge. Breadth-first expands "
            "the shallowest frontier node, which finds a shortest path when every "
            "step costs the same, at the price of holding the whole frontier in "
            "memory — exponential in depth. Depth-first holds only one path, so its "
            "memory is linear, but it can descend an infinitely deep branch and "
            "miss a shallow solution. Iterative deepening gets breadth-first's "
            "completeness with depth-first's memory by restarting depth-limited "
            "search at increasing limits; the repeated work is a constant factor, "
            "not an extra exponential.",
            "Informed search uses a heuristic h(n), an estimate of the cost from n "
            "to the goal. Greedy best-first expands whichever node looks closest "
            "and is neither optimal nor complete. A* expands by f(n) = g(n) + h(n), "
            "the true cost so far plus the estimate ahead, and is optimal when h is "
            "admissible — it never overestimates. The intuition is that an "
            "underestimate keeps the true goal's f value at or below its real cost, "
            "so no suboptimal node can be expanded first without the goal already "
            "having been reached. Consistency, the triangle-inequality form of the "
            "same condition, additionally guarantees that no node needs reopening.",
            "A good heuristic dominates a weak one: if h1 >= h2 everywhere and both "
            "are admissible, h1 expands fewer nodes. Heuristics are usually built by "
            "solving a relaxed problem — removing constraints makes the problem "
            "easier, and the cost of an optimal solution to a relaxation is a "
            "guaranteed underestimate for the original. Manhattan distance for a "
            "sliding-tile puzzle is exactly this: it relaxes the rule that tiles "
            "cannot occupy the same square.",
            "Constraint satisfaction problems are search where the state is an "
            "assignment of values to variables and the goal test is that every "
            "constraint holds. The structure is exploitable. Arc consistency "
            "prunes values that cannot participate in any consistent assignment "
            "before search begins, and the least-constraining-value and "
            "minimum-remaining-values heuristics order the search so failures "
            "surface early. When a problem decomposes into independent subproblems, "
            "solving them separately turns an exponential product into a sum.",
        ),
    },
    {
        "slug": "ml-regularization",
        "type": ResourceType.RESEARCH_PAPER,
        "title": "Regularization in Deep Networks: A Practical Survey",
        "subtitle": "Why overfitting persists and which countermeasures earn their cost",
        "department": "CSE",
        "subjects": ["CSE-ML", "CSE-AI"],
        "topics": ["CSE-ML-REGULARIZATION", "CSE-ML-NEURAL-NETWORKS",
                   "CSE-ML-MODEL-EVALUATION", "CSE-ML-DEEP-LEARNING"],
        "authors": ["NEXORA Curriculum Team", "R. Kulkarni", "A. Fernandes"],
        "year": 2026,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.PREMIUM,
        "price": 4.99,
        "difficulty": Difficulty.ADVANCED,
        "level": AcademicLevel.RESEARCH,
        "semester": 6,
        "keywords": ["overfitting", "regularization", "dropout", "weight decay",
                     "data augmentation", "early stopping", "generalization"],
        "description": "A survey of the techniques that close the train-test gap, "
                       "organized by what each one actually constrains.",
        "text": _text(
            "Abstract. A model that memorizes its training set generalizes poorly. "
            "This survey reviews the mechanisms used to prevent that, grouped by "
            "what they constrain: the hypothesis space, the data, the optimization "
            "path, or the ensemble. We argue that the grouping matters more than "
            "the individual technique, because techniques in different groups "
            "compose while techniques in the same group often duplicate effort.",
            "1. Constraining the hypothesis. Weight decay adds a penalty "
            "proportional to the squared magnitude of the weights to the loss, which "
            "shrinks the function class toward smoother functions. L1 penalty "
            "instead drives weights exactly to zero and produces sparse models. "
            "Architectural constraints — fewer parameters, weight sharing in "
            "convolutions, low-rank factorization — are the strongest form of this "
            "group because they make overfitting structurally harder rather than "
            "merely costlier.",
            "2. Constraining the data. Data augmentation generates additional "
            "training examples by applying label-preserving transformations: "
            "crops, flips and colour jitter for images; back-translation and "
            "synonym substitution for text. It is consistently the highest-value "
            "technique in this group, because it enlarges the effective training "
            "set rather than restricting the model. Its limitation is that it "
            "encodes an invariance assumption, and a wrong assumption injects bias "
            "that no amount of data volume removes.",
            "3. Constraining the optimization path. Early stopping halts training "
            "when validation loss stops improving, which limits how far the model "
            "travels toward a memorizing solution. Learning-rate schedules and "
            "gradient clipping act in the same spirit. This group is nearly free to "
            "apply and should be the default starting point before anything more "
            "elaborate.",
            "4. Ensembling. Dropout zeroes a random subset of activations on each "
            "forward pass, so no single unit can become load-bearing, and at test "
            "time the full network approximates an average over the sub-networks it "
            "trained. Batch normalization was designed to stabilize training but "
            "regularizes as a side effect, because the per-minibatch statistics add "
            "noise to each activation. Label smoothing replaces hard targets with "
            "soft ones, which stops the model from becoming arbitrarily confident.",
            "5. Evaluation discipline. None of the above can be judged without a "
            "validation set that the tuning process never trains on. Reusing the "
            "test set to select among regularizers leaks information and produces "
            "optimistic numbers that do not replicate. Where the dataset is small, "
            "k-fold cross-validation reduces the variance of the estimate at the "
            "cost of k times the training runs.",
            "6. Practical ordering. Establish a baseline with early stopping. Add "
            "augmentation if the domain admits a correct invariance. Add weight "
            "decay and tune it once. Add dropout only if the previous three leave a "
            "measurable gap. Reaching for an elaborate technique before the cheap "
            "ones is the most common way to spend a week and gain nothing.",
        ),
    },
    {
        "slug": "dns-resolution",
        "type": ResourceType.ARTICLE,
        "title": "How DNS Actually Resolves a Name",
        "subtitle": "The full path from a browser keystroke to an IP address",
        "department": "CSE",
        "subjects": ["CSE-NET"],
        "topics": ["CSE-NET-DNS-AND-ADDRESSING", "CSE-NET-TCP-IP-SUITE",
                   "CSE-NET-NETWORK-SECURITY"],
        "authors": ["NEXORA Curriculum Team"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.BEGINNER,
        "level": AcademicLevel.INTRODUCTORY,
        "semester": 5,
        "keywords": ["DNS", "recursive resolver", "authoritative nameserver",
                     "TTL", "caching", "DNSSEC"],
        "description": "A step-by-step trace of an iterative resolution chain and "
                       "the caching layers that keep it from happening on every "
                       "request.",
        "text": _text(
            "When a browser needs the address for a hostname it asks a recursive "
            "resolver — usually operated by the ISP or a public DNS provider. "
            "Recursive means the resolver does all the work and returns a final "
            "answer; the client asks one question and gets one answer.",
            "The resolver starts at the root. Root servers do not know the answer; "
            "they refer the resolver to the servers responsible for the top-level "
            "domain, here .com. The .com servers do not know either; they refer the "
            "resolver to the authoritative nameservers for example.com. Those do "
            "know, and they return the record. Every step after the first is a "
            "referral rather than an answer, which is why the process is called "
            "iterative resolution even though the client's view of it is recursive.",
            "Caching is what keeps this from running on every page load. Each "
            "response carries a time-to-live, and the resolver stores it for that "
            "long. The operating system keeps its own cache, the browser keeps "
            "another, and the resolver keeps the largest one. A low TTL means "
            "changes propagate quickly at the cost of more queries; a high TTL "
            "means fewer queries and a longer window during which an old address is "
            "still being served.",
            "The system has known weaknesses. Responses travel over UDP by default "
            "and were originally unauthenticated, so a resolver can be given a "
            "forged answer — cache poisoning. DNSSEC addresses this by signing zone "
            "data and letting a resolver verify the chain of signatures back to a "
            "trusted root key. Encrypted transports, DNS-over-TLS and "
            "DNS-over-HTTPS, solve a different problem: they stop an on-path "
            "observer from reading or tampering with the query, but they do not by "
            "themselves authenticate the answer's contents.",
            "One more detail that surprises people: a resolver asked for a name with "
            "no A record may still return useful data, because negative answers are "
            "cached too. An NXDOMAIN response carries its own TTL, so a domain that "
            "does not exist will keep not existing, from this resolver's point of "
            "view, until that TTL expires.",
        ),
    },
    {
        "slug": "sec-credential-stuffing",
        "type": ResourceType.CASE_STUDY,
        "title": "Anatomy of a Credential-Stuffing Attack",
        "subtitle": "A teaching case in authentication abuse and its defences",
        "department": "CSE",
        "subjects": ["CSE-SEC", "CSE-NET"],
        "topics": ["CSE-SEC-SECURITY-POLICIES", "CSE-SEC-PENETRATION-TESTING",
                   "CSE-SEC-VULNERABILITY-ASSESSMENT", "CSE-NET-NETWORK-SECURITY"],
        "authors": ["NEXORA Curriculum Team"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.INTERMEDIATE,
        "level": AcademicLevel.CORE,
        "semester": 7,
        "keywords": ["credential stuffing", "password reuse", "rate limiting",
                     "multi-factor authentication", "bot detection", "incident response"],
        "description": "A reconstructed attack against a fictional service, used to "
                       "teach why password reuse is the root cause and which "
                       "controls actually reduce it.",
        "text": _text(
            "This case describes an attack on a fictional e-commerce service. All "
            "details are constructed for teaching. The pattern, however, is the one "
            "most frequently reported by real services.",
            "The attack begins with no exploit at all. A list of email-and-password "
            "pairs leaked from an unrelated breach is purchased on a forum. The "
            "attacker loads it into a tool that replays each pair against the "
            "target's login endpoint from a rotating pool of residential proxies. "
            "Nothing about the traffic is malformed; every request is a legitimate "
            "login attempt with valid-looking credentials.",
            "The attack works because of password reuse. Between one and two "
            "percent of the pairs succeed — a low rate per request, but on a list "
            "of fifty million pairs that is half a million compromised accounts. The "
            "attacker then filters for accounts with stored payment methods and "
            "resells or drains them.",
            "Detection is delayed because the usual signals are absent. There is no "
            "SQL injection in the logs, no anomalous payload, no single source IP "
            "making many attempts. What is present, on inspection afterwards, is a "
            "sustained elevation in failed-login rate spread across thousands of "
            "distinct IPs, and a login-success distribution skewed toward accounts "
            "that had not been used in months. Neither triggers an alert tuned for "
            "brute force against one account.",
            "The controls that matter, in order of effect. Multi-factor "
            "authentication removes the value of a correct password almost "
            "entirely, and is the single highest-impact change. Checking submitted "
            "passwords against a corpus of known-breached credentials at "
            "registration and at password change stops reuse from entering the "
            "system in the first place. Per-account rate limiting with exponential "
            "backoff, distinct from per-IP limiting, caps how many attempts one "
            "account can absorb. Alerting on aggregate failed-login rate rather "
            "than per-source rate catches the distributed pattern. Device and "
            "session fingerprinting raises the cost per attempt without blocking "
            "legitimate users on shared networks.",
            "The lesson generalizes: credential stuffing is not a vulnerability in "
            "the target's code. It is a consequence of an ecosystem-wide failure, "
            "and it is defended against by assuming every password the service "
            "holds has already leaked elsewhere.",
        ),
    },
    {
        "slug": "dbms-question-paper",
        "type": ResourceType.QUESTION_PAPER,
        "title": "Database Management — Model Question Paper",
        "subtitle": "Three hours, five units, with worked marking scheme",
        "department": "CSE",
        "subjects": ["CSE-DBMS"],
        "topics": ["CSE-DBMS-RELATIONAL-MODEL", "CSE-DBMS-SQL",
                   "CSE-DBMS-NORMALIZATION", "CSE-DBMS-QUERY-PROCESSING"],
        "authors": ["NEXORA Curriculum Team"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.INTERMEDIATE,
        "level": AcademicLevel.CORE,
        "semester": 4,
        "keywords": ["question paper", "model paper", "normalization", "SQL",
                     "relational algebra", "examination"],
        "description": "A full model paper with a marking scheme, usable for "
                       "revision or as a template for setting one.",
        "text": _text(
            "Instructions: answer all questions. Time three hours. Maximum one "
            "hundred marks. Assume a relational schema where a question does not "
            "supply one.",
            "Unit I — Relational model (20 marks). 1a. Define candidate key, "
            "primary key and foreign key, and explain why a relation may have "
            "several candidate keys but at most one primary key. [6] 1b. Given "
            "R(A,B,C,D) with functional dependencies A->B, B->C and C->D, list all "
            "candidate keys and state whether R is in second normal form. Justify. "
            "[8] 1c. Express 'find the names of students enrolled in every course "
            "offered by the CSE department' in relational algebra using division. "
            "[6]",
            "Unit II — SQL (20 marks). 2a. Write a query returning each department "
            "and its average salary, restricted to departments whose average "
            "exceeds the overall average, ordered descending. [8] 2b. Explain the "
            "difference in result between a LEFT JOIN and an INNER JOIN on the same "
            "tables, with a two-row example. [6] 2c. Why is a correlated subquery "
            "in a WHERE clause often slower than an equivalent join? [6]",
            "Unit III — Normalization (20 marks). 3a. State and prove the lossless-"
            "join property for a binary decomposition. [8] 3b. Decompose the schema "
            "from 1b into BCNF and show each step. [8] 3c. Give an example where "
            "BCNF decomposition loses a functional dependency, and explain the "
            "consequence. [4]",
            "Unit IV — Transactions (20 marks). 4a. Construct a schedule of two "
            "transactions that is conflict-serializable but not recoverable, and "
            "explain why recoverability is a separate property. [8] 4b. Describe "
            "how a write-ahead log supports redo and undo during crash recovery. "
            "[8] 4c. State the two phases of two-phase locking and why releasing a "
            "lock early can break serializability. [4]",
            "Unit V — Storage and indexing (20 marks). 5a. Compare a B+ tree index "
            "with a hash index for range queries, giving the structural reason for "
            "the difference. [8] 5b. Explain why B+ trees store data only at the "
            "leaves and what that buys for range scans. [6] 5c. Define a clustered "
            "index and explain why a table can have at most one. [6]",
            "Marking scheme note: award full marks for a correct answer with "
            "reasoning, half marks for a correct answer with no reasoning, and no "
            "marks for reasoning without a conclusion. A diagram in place of prose "
            "is acceptable wherever the question does not require a written "
            "justification.",
        ),
    },
    {
        "slug": "la-eigenvalues",
        "type": ResourceType.LECTURE_NOTES,
        "title": "Eigenvalues, Eigenvectors and the SVD",
        "subtitle": "The directions a linear map leaves alone",
        "department": "MATH",
        "subjects": ["MATH-LA"],
        "topics": ["MATH-LA-EIGENVALUES-AND-EIGENVECTORS", "MATH-LA-LINEAR-TRANSFORMATIONS",
                   "MATH-LA-SINGULAR-VALUE-DECOMPOSITION", "MATH-LA-MATRIX-OPERATIONS"],
        "authors": ["NEXORA Curriculum Team", "Dr. K. Bhattacharya"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.INTERMEDIATE,
        "level": AcademicLevel.CORE,
        "semester": 2,
        "keywords": ["eigenvalue", "eigenvector", "diagonalization", "singular value decomposition",
                     "characteristic polynomial", "spectral theorem"],
        "description": "Eigen-decomposition and the SVD from the geometric idea "
                       "outward, with the conditions under which each exists.",
        "text": _text(
            "A linear map usually changes both the length and the direction of a "
            "vector. Some special vectors only change length: applying the map "
            "leaves them pointing the same way, possibly reversed. Those are the "
            "eigenvectors, and the factor by which they are scaled is the "
            "eigenvalue. Formally, Av = lambda v for a nonzero v.",
            "Rearranging gives (A - lambda I)v = 0 with v nonzero, so the matrix "
            "A - lambda I must be singular and its determinant must vanish. That "
            "determinant, expanded, is the characteristic polynomial, and its roots "
            "are the eigenvalues. An n-by-n matrix therefore has at most n distinct "
            "eigenvalues, counted with multiplicity, and they may be complex even "
            "when A is real.",
            "Diagonalization is the payoff. If A has n linearly independent "
            "eigenvectors, they form a basis in which A acts by scaling each axis "
            "separately: A = P D P-inverse, with D diagonal. Raising A to a power "
            "then becomes raising D to a power, which is trivial, and this is why "
            "eigen-decomposition underlies the analysis of iterative processes and "
            "of systems of linear differential equations. Not every matrix is "
            "diagonalizable — a repeated eigenvalue can come with too few "
            "independent eigenvectors — and symmetric matrices are the important "
            "case where it always works.",
            "The spectral theorem states that a real symmetric matrix has real "
            "eigenvalues and an orthonormal basis of eigenvectors. That orthogonality "
            "is what makes symmetric matrices behave: P becomes an orthogonal matrix, "
            "so the inverse is just the transpose, and the decomposition is "
            "numerically stable.",
            "The singular value decomposition generalizes the idea to any matrix, "
            "square or not, diagonalizable or not. Every A factors as U Sigma "
            "V-transpose where U and V are orthogonal and Sigma is diagonal with "
            "nonnegative entries, the singular values. Geometrically it says every "
            "linear map is a rotation, then an axis-aligned scaling, then another "
            "rotation. The singular values are the square roots of the eigenvalues "
            "of A-transpose A.",
            "Truncating the SVD to its k largest singular values gives the best "
            "rank-k approximation to A in the Frobenius norm. That single fact is "
            "behind low-rank compression, principal component analysis, latent "
            "semantic indexing and a large share of practical dimensionality "
            "reduction: keep the directions along which the data varies most, "
            "discard the rest, and the discarded error is provably minimal for the "
            "rank you chose.",
        ),
    },
    {
        "slug": "prob-distributions",
        "type": ResourceType.STUDY_MATERIAL,
        "title": "Probability Distributions: Worked Examples",
        "subtitle": "Choosing the right model for a counting or measuring problem",
        "department": "MATH",
        "subjects": ["MATH-PROB", "MATH-CALC"],
        "topics": ["MATH-PROB-PROBABILITY-DISTRIBUTIONS", "MATH-PROB-RANDOM-VARIABLES",
                   "MATH-PROB-SAMPLING-THEORY"],
        "authors": ["NEXORA Curriculum Team"],
        "year": 2024,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.BEGINNER,
        "level": AcademicLevel.INTRODUCTORY,
        "semester": 3,
        "keywords": ["binomial", "poisson", "normal distribution", "expectation",
                     "variance", "central limit theorem"],
        "description": "The four distributions encountered most often, what "
                       "assumption each one encodes, and how to tell them apart in "
                       "a word problem.",
        "text": _text(
            "Choosing a distribution is choosing an assumption. The right question "
            "is never 'which formula applies' but 'what do I believe about the "
            "process that generated this number'.",
            "The binomial distribution models the number of successes in a fixed "
            "number n of independent trials, each with the same success probability "
            "p. Its mean is np and its variance np(1-p). The assumptions are the "
            "part that gets violated: if you sample without replacement from a "
            "small population the trials are not independent, and the correct model "
            "is hypergeometric. As a rule of thumb the binomial is an acceptable "
            "approximation when the sample is under five percent of the population.",
            "The Poisson distribution models the number of events in a fixed "
            "interval when events occur independently at a constant average rate. "
            "Its mean and variance are both equal to lambda, which is a testable "
            "signature: if your counts have variance much larger than the mean, "
            "Poisson is the wrong model and the data is overdispersed. A binomial "
            "with large n and small p is well approximated by a Poisson with "
            "lambda = np.",
            "The normal distribution models a quantity produced by the accumulation "
            "of many small independent effects. Its importance is not that many "
            "things are normally distributed — incomes are not, waiting times are "
            "not — but the central limit theorem: the mean of a large sample from "
            "almost any distribution with finite variance is approximately normal, "
            "regardless of the shape of the original. That is what licenses "
            "confidence intervals built on sample means.",
            "Worked example. A call centre receives on average 4 calls per minute. "
            "What is the probability of exactly 6 in a given minute? The setup is "
            "counts in a fixed interval at a constant rate, so Poisson with "
            "lambda = 4: P(X=6) = e^-4 * 4^6 / 6! which is about 0.104. If instead "
            "the question asked for the probability that 6 of 20 randomly chosen "
            "minutes each contain a call, that is a fixed number of independent "
            "trials with a constant probability, and the model is binomial. Same "
            "numbers, different assumption, different answer.",
            "Two habits prevent most errors. First, write down the random variable "
            "in words before writing any symbol — 'X = number of defective items in "
            "the sample of 50', not 'X = defects'. Second, after computing, check "
            "that the answer is a probability between zero and one and that its "
            "magnitude is plausible for the question asked.",
        ),
    },
    {
        "slug": "qm-wavefunctions",
        "type": ResourceType.EBOOK,
        "title": "Wave Functions and the Schrodinger Equation",
        "subtitle": "From the postulates to the particle in a box",
        "department": "PHYS",
        "subjects": ["PHYS-QM"],
        "topics": ["PHYS-QM-WAVE-FUNCTIONS", "PHYS-QM-SCHRODINGER-EQUATION",
                   "PHYS-QM-OPERATORS-AND-OBSERVABLES"],
        "authors": ["NEXORA Curriculum Team", "Prof. H. Lindqvist"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.PREMIUM,
        "price": 6.99,
        "difficulty": Difficulty.ADVANCED,
        "level": AcademicLevel.ADVANCED,
        "semester": 6,
        "keywords": ["wave function", "Schrodinger equation", "Born rule",
                     "particle in a box", "quantization", "expectation value"],
        "description": "The postulates stated plainly, then the simplest solvable "
                       "system worked through in full to show where quantization "
                       "comes from.",
        "text": _text(
            "The state of a quantum system is described by a wave function, usually "
            "written psi(x,t). It is a complex-valued function, and it is not itself "
            "an observable quantity. What is observable is the squared magnitude: "
            "the Born rule says the probability of finding the particle between x "
            "and x+dx is |psi|^2 dx. Because probabilities over all space must sum "
            "to one, the wave function must be normalized, and this single "
            "requirement constrains everything that follows.",
            "Physical quantities are represented by operators acting on the wave "
            "function. Position is multiplication by x; momentum is -i hbar d/dx; "
            "energy is the Hamiltonian, the sum of kinetic and potential operators. "
            "The measurable values of a quantity are the eigenvalues of its "
            "operator, and the expected value of a measurement over many identically "
            "prepared systems is the integral of psi* A psi.",
            "The Schrodinger equation states how the wave function evolves: "
            "i hbar d(psi)/dt = H psi. For a time-independent potential it separates "
            "into a spatial equation, H psi = E psi, which is an eigenvalue problem, "
            "and a trivial time dependence, a phase factor exp(-iEt/hbar). The "
            "spatial equation is the time-independent Schrodinger equation and is "
            "what one actually solves.",
            "The particle in a box makes the mechanism visible. Take a particle "
            "confined to 0 < x < L by infinitely high walls. Inside, the potential "
            "is zero and the equation reduces to a second-order differential "
            "equation whose general solution is a combination of sine and cosine. "
            "The boundary conditions — the wave function must vanish at both walls, "
            "because the probability of finding the particle inside an infinite "
            "potential is zero — force the cosine coefficient to zero and force "
            "sin(kL) = 0. That is satisfied only when kL is an integer multiple of "
            "pi.",
            "So k = n pi / L, and substituting back gives E_n = n^2 pi^2 hbar^2 / "
            "(2 m L^2). The integer n did not come from any assumption about "
            "energy. It came from a boundary condition on a wave. Quantization is "
            "what happens when a wave is confined, exactly as a guitar string "
            "supports only certain frequencies because it is fixed at both ends. "
            "Note also that the lowest energy, n = 1, is not zero: a confined "
            "particle cannot be at rest, because a precisely known zero momentum "
            "would require a completely delocalized wave function.",
            "The general solution is a superposition of these stationary states, "
            "with coefficients fixed by the initial wave function. Measurement "
            "returns one of the eigenvalues, with probability given by the squared "
            "magnitude of the corresponding coefficient, and after the measurement "
            "the state is the corresponding eigenstate. That last clause is the "
            "part of the theory with no classical analogue and the source of every "
            "interpretational difficulty.",
        ),
    },
    {
        "slug": "oc-reaction-mechanisms",
        "type": ResourceType.STUDY_MATERIAL,
        "title": "Reaction Mechanisms: Arrow-Pushing Practice",
        "subtitle": "Reading a mechanism as a sequence of electron movements",
        "department": "CHEM",
        "subjects": ["CHEM-OC"],
        "topics": ["CHEM-OC-REACTION-MECHANISMS", "CHEM-OC-FUNCTIONAL-GROUPS",
                   "CHEM-OC-STEREOCHEMISTRY"],
        "authors": ["NEXORA Curriculum Team", "Dr. A. Menon"],
        "year": 2024,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.INTERMEDIATE,
        "level": AcademicLevel.CORE,
        "semester": 3,
        "keywords": ["nucleophile", "electrophile", "arrow pushing", "SN1", "SN2",
                     "carbocation", "leaving group"],
        "description": "The vocabulary of curved arrows, then the substitution and "
                       "elimination mechanisms that use it, with the structural "
                       "features that decide which path a reaction takes.",
        "text": _text(
            "A curved arrow always moves electrons, never atoms. It starts at a lone "
            "pair or a bond and ends at an atom or a bond. Every arrow you draw must "
            "leave the atom it starts from with a valid valence, and no second-row "
            "element may ever exceed an octet. Those two rules catch most mistakes "
            "before they propagate.",
            "The actors are a nucleophile, which donates electrons, and an "
            "electrophile, which accepts them. Nucleophilicity increases with "
            "negative charge, with polarizability down a group, and — in protic "
            "solvents — decreases for small anions that get heavily solvated. A good "
            "leaving group is one that is stable on its own after departure, which "
            "is why halides and tosylate leave readily and hydroxide and amide do "
            "not; converting an alcohol to a tosylate is precisely a way of "
            "installing a leaving group.",
            "SN2 is concerted: the nucleophile attacks the carbon as the leaving "
            "group departs, in a single step through a pentacoordinate transition "
            "state. The rate depends on both concentrations. The backside attack "
            "inverts the stereocentre, and steric bulk around the carbon slows the "
            "reaction sharply, so methyl and primary substrates react fastest and "
            "tertiary substrates essentially do not react this way.",
            "SN1 is stepwise: the leaving group departs first to give a carbocation, "
            "and only then does the nucleophile attack. The rate depends on the "
            "substrate alone, because the slow step involves only it. The planar "
            "carbocation can be attacked from either face, so the product is "
            "racemized rather than inverted. Carbocation stability therefore governs "
            "the rate — tertiary beats secondary beats primary — the exact opposite "
            "of the steric ordering in SN2, and that reversal is how you decide "
            "which mechanism a given substrate will follow.",
            "Elimination competes with substitution in both cases. E2, like SN2, is "
            "concerted and requires the leaving group and the beta-hydrogen to be "
            "antiperiplanar; a strong bulky base favours it. E1, like SN1, proceeds "
            "through the same carbocation intermediate, and whether that intermediate "
            "loses a proton or captures a nucleophile depends on conditions. Heat "
            "favours elimination over substitution in both families, because "
            "elimination increases the number of particles and so has a more "
            "favourable entropy change.",
            "The decision procedure, then, is fixed and worth memorizing: identify "
            "the substrate's substitution pattern, identify whether the nucleophile "
            "or base is strong and whether it is bulky, note the solvent and the "
            "temperature, and only then choose. Trying to guess the product before "
            "classifying the substrate is what makes mechanisms feel arbitrary.",
        ),
    },
    {
        "slug": "dsp-fourier",
        "type": ResourceType.LECTURE_NOTES,
        "title": "From the Fourier Transform to the FFT",
        "subtitle": "Why the discrete transform costs N log N and what that unlocked",
        "department": "ECE",
        "subjects": ["ECE-DSP", "ECE-SIG"],
        "topics": ["ECE-DSP-DISCRETE-FOURIER-TRANSFORM", "ECE-DSP-FAST-FOURIER-TRANSFORM",
                   "ECE-SIG-SAMPLING-THEOREM", "ECE-DSP-DIGITAL-FILTERS"],
        "authors": ["NEXORA Curriculum Team"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.INTERMEDIATE,
        "level": AcademicLevel.CORE,
        "semester": 5,
        "keywords": ["Fourier transform", "DFT", "FFT", "sampling", "Nyquist",
                     "aliasing", "spectral leakage"],
        "description": "The discrete Fourier transform defined, the divide-and-"
                       "conquer step that makes it fast, and the sampling "
                       "discipline that has to hold before any of it means "
                       "anything.",
        "text": _text(
            "The Fourier transform expresses a signal as a sum of sinusoids, "
            "trading the time domain for the frequency domain. Computed directly, "
            "the N-point discrete Fourier transform needs N outputs each formed by "
            "summing N terms, so N-squared complex multiply-accumulates. For N of a "
            "million that is a trillion operations, which is why spectral analysis "
            "was impractical before 1965.",
            "The fast Fourier transform is a divide-and-conquer factorization of "
            "that sum. Split the input into even-indexed and odd-indexed halves and "
            "the DFT of length N becomes a combination of two DFTs of length N/2, "
            "joined by twiddle factors. Recursing gives a cost of N log N. The "
            "algorithm assumes N is a power of two, or more generally highly "
            "composite; a prime-length transform degenerates back toward N-squared. "
            "That constant-factor speedup of several orders of magnitude is what "
            "made real-time audio processing, medical imaging and OFDM "
            "communications feasible.",
            "Before any of this applies, sampling must have been done correctly. "
            "The Nyquist-Shannon theorem states that a signal band-limited to B hertz "
            "is exactly recoverable from samples taken above 2B hertz. Sample slower "
            "and high-frequency content folds back into the band as aliasing — an "
            "irreversible corruption that no later processing can undo, because the "
            "aliased component is indistinguishable from a genuine low-frequency "
            "one. This is why an analogue anti-aliasing filter precedes every "
            "analogue-to-digital converter rather than following it.",
            "Two further artefacts appear in practice. Spectral leakage arises "
            "because the DFT implicitly assumes the sampled window repeats "
            "periodically; if the signal does not complete whole cycles inside the "
            "window, energy smears across adjacent bins. Windowing functions taper "
            "the edges to reduce this, trading main-lobe width for sidelobe "
            "suppression. Picketing, or scalloping loss, arises when a true "
            "frequency falls between two bins; zero-padding interpolates the "
            "spectrum and makes the peak easier to locate, though it adds no new "
            "information and does not improve true resolution.",
            "Frequency resolution is set by the window length, not by the "
            "transform size: two sinusoids separated by delta f require an "
            "observation of roughly 1/delta f seconds. Zero-padding cannot buy "
            "resolution. Confusing the two is the most common error in practical "
            "spectral analysis.",
        ),
    },
    {
        "slug": "electronics-opamps",
        "type": ResourceType.STUDY_MATERIAL,
        "title": "Operational Amplifiers in Practice",
        "subtitle": "The two ideal-opamp assumptions and the circuits they make trivial",
        "department": "ECE",
        "subjects": ["ECE-EDC"],
        "topics": ["ECE-EDC-OPERATIONAL-AMPLIFIERS", "ECE-EDC-BIASING-CIRCUITS"],
        "authors": ["NEXORA Curriculum Team"],
        "year": 2024,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.BEGINNER,
        "level": AcademicLevel.INTRODUCTORY,
        "semester": 3,
        "keywords": ["op-amp", "negative feedback", "inverting amplifier",
                     "virtual ground", "gain-bandwidth product", "slew rate"],
        "description": "Analysis of ideal op-amp circuits from two assumptions, "
                       "followed by the non-ideal parameters that break the model "
                       "at high frequency.",
        "text": _text(
            "An ideal operational amplifier has infinite open-loop gain, infinite "
            "input impedance and zero output impedance. With negative feedback "
            "applied, two consequences follow and they are all you need to analyse "
            "most circuits: no current flows into either input terminal, and the "
            "voltage difference between the inputs is driven to zero.",
            "The second one is the source of the virtual ground. In an inverting "
            "amplifier the non-inverting input is tied to ground, so the inverting "
            "input sits at ground potential too — not because it is connected there "
            "but because feedback holds it there. All the input current therefore "
            "flows through the feedback resistor, and the gain is simply negative "
            "Rf over Rin. In the non-inverting configuration the input is applied "
            "directly, and the gain is one plus Rf over Rg, never less than unity.",
            "The same two assumptions produce the summing amplifier, where several "
            "inputs each feed the virtual ground through their own resistor and the "
            "output is the weighted negative sum; the integrator, where a capacitor "
            "replaces the feedback resistor and the output becomes the time integral "
            "of the input; the differentiator, with the roles swapped; and the "
            "voltage follower, which has unity gain but converts a high-impedance "
            "source into a low-impedance one and is used purely for buffering.",
            "Real devices depart from the model in ways that matter. The gain is "
            "finite and falls with frequency at a fixed rate, so the product of gain "
            "and bandwidth is roughly constant: an amplifier with a 1 MHz "
            "gain-bandwidth product closed for a gain of 100 has only 10 kHz of "
            "bandwidth. Slew rate limits how fast the output can change, in volts "
            "per microsecond, and a large-amplitude high-frequency signal will be "
            "clipped into a triangle regardless of the bandwidth figure. Input "
            "offset voltage appears as a small DC error amplified by the closed-loop "
            "gain, which dominates in precision DC circuits. Input bias currents "
            "flow through the source resistances and create offset errors of their "
            "own, mitigated by matching the DC resistance seen at both inputs.",
            "The design procedure is therefore two-stage. Analyse the circuit with "
            "the ideal assumptions to get the intended transfer function, then check "
            "the result against the gain-bandwidth product, the slew rate and the "
            "offset specification at the actual signal amplitude and frequency. "
            "Most circuits that behave on paper and fail on a bench fail at the "
            "second stage.",
        ),
    },
    {
        "slug": "bioinfo-sequence-alignment",
        "type": ResourceType.ACADEMIC_REPORT,
        "title": "Sequence Alignment Methods: A Teaching Report",
        "subtitle": "Dynamic programming for global and local alignment",
        "department": "BIOTECH",
        "subjects": ["BIOTECH-BIOINFO", "CSE-DSA"],
        "topics": ["BIOTECH-BIOINFO-SEQUENCE-ALIGNMENT", "BIOTECH-BIOINFO-BIOLOGICAL-DATABASES",
                   "CSE-DSA-COMPLEXITY-ANALYSIS"],
        "authors": ["NEXORA Curriculum Team", "Dr. S. Nair"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.PREMIUM,
        "price": 3.99,
        "difficulty": Difficulty.ADVANCED,
        "level": AcademicLevel.RESEARCH,
        "semester": 6,
        "keywords": ["sequence alignment", "dynamic programming", "Needleman-Wunsch",
                     "Smith-Waterman", "substitution matrix", "gap penalty"],
        "description": "The two foundational alignment algorithms derived from "
                       "first principles, with the scoring choices that determine "
                       "what each one finds.",
        "text": _text(
            "Aligning two sequences means arranging them, inserting gaps where "
            "necessary, so that homologous positions line up. The number of possible "
            "arrangements grows combinatorially, so exhaustive search is impossible "
            "for sequences of realistic length. Both foundational algorithms avoid "
            "it by dynamic programming.",
            "The shared structure is a matrix F with one sequence along each axis. "
            "F(i,j) holds the best score for aligning the first i characters of one "
            "sequence with the first j of the other. Each cell is the maximum of "
            "three possibilities: a diagonal move that pairs character i with "
            "character j, scored by a substitution matrix; a vertical move that gaps "
            "out character i; and a horizontal move that gaps out character j. "
            "Filling the matrix costs O(mn) time and space, and the alignment is "
            "recovered by tracing back from a chosen cell to the origin.",
            "Needleman-Wunsch performs global alignment. The first row and column are "
            "initialized to multiples of the gap penalty, and traceback starts at the "
            "bottom-right corner, so every character of both sequences participates. "
            "This is right for comparing two sequences of similar length and similar "
            "function end to end, and wrong when one is much longer than the other or "
            "when only a region is conserved.",
            "Smith-Waterman performs local alignment and differs in exactly two "
            "places: the first row and column are initialized to zero, and zero is "
            "included as a fourth option in the cell recurrence. Including zero means "
            "a negative-scoring region can be abandoned rather than carried, and "
            "starting traceback at the highest-scoring cell anywhere in the matrix "
            "means the algorithm reports only the best-scoring subregion. That makes "
            "it the right tool for finding a conserved domain inside two otherwise "
            "unrelated proteins.",
            "The scoring parameters decide what the algorithm finds, and this is "
            "where biological judgement enters. A substitution matrix such as BLOSUM62 "
            "encodes observed replacement frequencies in related proteins, so "
            "conservative substitutions score mildly positive and improbable ones "
            "strongly negative; the 62 in the name denotes the divergence level the "
            "matrix was built from, and lower numbers suit more distant comparisons. "
            "The gap penalty is usually affine — a larger cost to open a gap than to "
            "extend it — because a single insertion of ten residues is far more "
            "plausible evolutionarily than ten independent insertions of one.",
            "Both algorithms are exact but quadratic, which limits them to pairwise "
            "comparison of moderate-length sequences. Database search at scale uses "
            "heuristics that seed on short exact word matches and extend only the "
            "promising ones, sacrificing guaranteed optimality for orders of "
            "magnitude in speed. The dynamic-programming step survives inside those "
            "tools as the extension phase, which is why understanding it is "
            "prerequisite to understanding anything built on top of it.",
        ),
    },
    {
        "slug": "civil-structural-analysis",
        "type": ResourceType.BOOK,
        "title": "Structural Analysis of Beams and Frames",
        "subtitle": "Determinacy, moment distribution and influence lines",
        "department": "CIVIL",
        "subjects": ["CIVIL-SA", "MECH-SOM"],
        "topics": ["CIVIL-SA-BEAMS-AND-FRAMES", "CIVIL-SA-MOMENT-DISTRIBUTION",
                   "CIVIL-SA-INFLUENCE-LINES", "MECH-SOM-BENDING-OF-BEAMS"],
        "authors": ["NEXORA Curriculum Team", "Er. V. Kulkarni"],
        "year": 2024,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.PREMIUM,
        "price": 8.99,
        "difficulty": Difficulty.ADVANCED,
        "level": AcademicLevel.ADVANCED,
        "semester": 5,
        "keywords": ["statical determinacy", "bending moment", "shear force",
                     "moment distribution", "influence line", "deflection"],
        "description": "From the determinacy check that decides which method to use, "
                       "through moment distribution, to influence lines for moving "
                       "loads.",
        "text": _text(
            "The first question in any analysis is whether the structure is "
            "statically determinate. Count the unknown reactions and internal "
            "releases and compare against the available equilibrium equations: three "
            "per rigid body in a plane. If the unknowns equal the equations, the "
            "structure is determinate and statics alone solves it. If the unknowns "
            "exceed the equations, it is indeterminate, and the extra conditions "
            "come from compatibility — the deformed structure must still fit "
            "together — which requires knowing member stiffnesses.",
            "For a beam, the relationships between load, shear and moment are "
            "differential and worth internalizing. The rate of change of shear along "
            "the span equals the negative of the distributed load; the rate of "
            "change of moment equals the shear. So a uniform load gives a linear "
            "shear diagram and a parabolic moment diagram, a point load gives a "
            "jump in shear and a kink in moment, and the moment is extremal wherever "
            "the shear crosses zero. Drawing diagrams from these rules is faster and "
            "less error-prone than computing values at many points.",
            "The moment distribution method, Hardy Cross's contribution, solves "
            "indeterminate frames iteratively without setting up simultaneous "
            "equations. Each joint is temporarily fixed, the fixed-end moments are "
            "computed for every member, and then joints are released one at a time. "
            "Releasing a joint unbalances it, and the unbalanced moment is "
            "distributed to the meeting members in proportion to their stiffness — "
            "the distribution factor — with half of each distributed moment carried "
            "to the far end of that member. The process repeats until the carried "
            "moments are negligible. It converges because each cycle attenuates, and "
            "it was the standard practical method for decades before matrix "
            "formulations made computer solution routine.",
            "An influence line plots the value of one response function — a "
            "reaction, a shear at a section, a moment at a section — as a unit load "
            "moves across the structure. It answers a different question from a "
            "bending moment diagram: the moment diagram is for one fixed load "
            "arrangement, whereas the influence line tells you where to put any load "
            "to maximize that response. For a determinate structure the influence "
            "lines are straight-segmented, which follows from the fact that the "
            "response varies linearly with load position between supports.",
            "The Muller-Breslau principle gives them quickly: remove the restraint "
            "corresponding to the response, apply a unit displacement in its "
            "direction, and the resulting deflected shape is the influence line to "
            "scale. For a simply supported beam's midspan moment that produces a "
            "triangle peaking at the centre, which immediately tells you the "
            "critical load position for design.",
            "Deflection matters independently of strength, because serviceability "
            "limits are often more restrictive than ultimate ones. The "
            "double-integration method integrates the moment-curvature relation "
            "twice and applies boundary conditions; the moment-area method uses the "
            "area and first moment of the M/EI diagram between two points; and "
            "unit-load or virtual-work methods give deflection at a specific point "
            "directly. Choose by what you need: a full elastic curve, a slope and "
            "deflection between two points, or a single displacement.",
        ),
    },
    {
        "slug": "biotech-fermentation",
        "type": ResourceType.STUDY_MATERIAL,
        "title": "Fermentation Technology and Bioreactor Operation",
        "subtitle": "Scaling a culture from flask to production vessel",
        "department": "BIOTECH",
        "subjects": ["BIOTECH-CORE"],
        "topics": ["BIOTECH-CORE-FERMENTATION-TECHNOLOGY", "BIOTECH-CORE-BIOREACTORS",
                   "BIOTECH-CORE-BIOPROCESS-ENGINEERING", "BIOTECH-CORE-DOWNSTREAM-PROCESSING"],
        "authors": ["NEXORA Curriculum Team"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.INTERMEDIATE,
        "level": AcademicLevel.CORE,
        "semester": 3,
        "keywords": ["fermentation", "bioreactor", "sterilization", "oxygen transfer",
                     "scale-up", "batch culture", "downstream processing"],
        "description": "Growth phases in batch culture, the parameters a bioreactor "
                       "controls, and why scale-up is an oxygen-transfer problem "
                       "rather than a geometry problem.",
        "text": _text(
            "A batch culture passes through predictable phases. The lag phase is "
            "adaptation: cells are synthesizing the enzymes the new medium requires "
            "and the count is not yet rising. The exponential phase follows, where "
            "growth is limited only by the cells' own kinetics and the specific "
            "growth rate is constant. As a substrate is exhausted or an inhibitory "
            "product accumulates, growth slows into the stationary phase where the "
            "division rate equals the death rate. Prolonged starvation leads to "
            "decline. Many commercially important products are secondary metabolites "
            "made in the stationary phase rather than the growth phase, which is why "
            "the process is not simply run as fast as possible.",
            "A bioreactor exists to hold the environment at the set point the "
            "organism wants while keeping everything else out. Temperature is "
            "controlled by a jacket or internal coil. pH is controlled by dosing acid "
            "or base, since metabolism usually shifts it. Dissolved oxygen is "
            "controlled by agitation speed and sparged air flow, and it is the "
            "parameter that becomes limiting first in aerobic processes. Foam is "
            "controlled mechanically or chemically because it carries cells out of "
            "the vessel and risks breaching the sterile boundary.",
            "Sterility is the governing constraint. The vessel, the medium and every "
            "inlet must be free of contaminating organisms for the whole run, "
            "because a contaminant grows faster than the production strain and will "
            "outcompete it. Medium is sterilized by heat, but heat also degrades "
            "nutrients, so the time-temperature combination is optimized rather than "
            "maximized; heat-labile components such as vitamins are filter-sterilized "
            "and added separately. Sampling ports, shaft seals and the exhaust are "
            "the usual failure points, and the exhaust carries a filter because the "
            "vessel must not become a route for releasing organisms.",
            "Scale-up is where intuition fails. Doubling the linear dimension of a "
            "vessel multiplies its volume by eight but its surface area by only "
            "four. Heat generation scales with volume while heat removal through the "
            "jacket scales with area, so a large vessel has proportionally less "
            "cooling capacity. Oxygen supply has the same asymmetry: demand scales "
            "with volume, transfer with area and with the residence time of bubbles. "
            "Consequently scale-up is normally done at constant power input per unit "
            "volume or constant oxygen transfer coefficient, not at constant "
            "geometric similarity or constant stirring speed.",
            "Operation modes differ in what they optimize. Batch is simple and "
            "robust, with everything charged at the start. Fed-batch adds substrate "
            "gradually, which avoids the inhibition that a high initial concentration "
            "causes and extends the productive phase — it is the dominant mode in "
            "industrial practice. Continuous culture feeds fresh medium and removes "
            "broth at equal rates, holding the culture in steady exponential growth "
            "indefinitely, which maximizes productivity but greatly increases "
            "contamination risk over a long run.",
            "Downstream processing typically costs more than the fermentation itself. "
            "Cells are separated by centrifugation or filtration, then disrupted if "
            "the product is intracellular, then the product is purified by "
            "precipitation, chromatography or membrane separation, and finally "
            "concentrated and dried. Each step loses yield, so the number of steps is "
            "minimized aggressively once purity requirements are known.",
        ),
    },
    {
        "slug": "eee-power-systems",
        "type": ResourceType.LECTURE_NOTES,
        "title": "Power Systems: Load Flow and Stability",
        "subtitle": "Why the grid is a solved steady state and an unsolved transient",
        "department": "EEE",
        "subjects": ["EEE-PS", "EEE-CS"],
        "topics": ["EEE-PS-LOAD-FLOW-ANALYSIS", "EEE-PS-POWER-GRID-STABILITY",
                   "EEE-PS-TRANSMISSION-LINES", "EEE-CS-STABILITY-ANALYSIS"],
        "authors": ["NEXORA Curriculum Team", "Dr. R. Bandyopadhyay"],
        "year": 2025,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.ADVANCED,
        "level": AcademicLevel.ADVANCED,
        "semester": 5,
        "keywords": ["load flow", "per-unit system", "power swing", "transient stability",
                     "reactive power", "grid frequency"],
        "description": "The per-unit system, the iterative load-flow solution, and "
                       "the distinction between steady-state, transient and dynamic "
                       "stability.",
        "text": _text(
            "Power system analysis begins with the per-unit system, which normalizes "
            "every quantity by a chosen base. Voltages, currents, impedances and "
            "powers are all expressed as ratios to their base values, which removes "
            "transformer turns ratios from the equations entirely — a transformer "
            "becomes a simple series impedance — and puts quantities across a wide "
            "range of magnitudes on a comparable scale. A per-unit impedance near 0.1 "
            "tells an engineer immediately whether a value is plausible, which the "
            "same impedance in ohms at 400 kV does not.",
            "The load-flow problem asks for the steady-state voltages at every bus "
            "and the flows on every line, given the generation and demand. It is not "
            "solvable in closed form because power injection is a product of voltage "
            "and conjugate current, making the equations nonlinear. Newton-Raphson "
            "solves it iteratively and converges quadratically near the solution; "
            "Gauss-Seidel converges more slowly but is simpler per iteration. A "
            "practical structure is imposed by classifying buses: load buses have "
            "known P and Q and unknown voltage magnitude and angle; generator buses "
            "have known P and voltage magnitude with unknown Q and angle; and one "
            "slack bus absorbs the system's losses by fixing both magnitude and "
            "angle as the reference.",
            "Reactive power deserves separate attention because it does not travel "
            "well. Real power flows according to the angle difference between buses; "
            "reactive power flows according to the voltage magnitude difference. "
            "Moving reactive power over long distances is lossy, so it is supplied "
            "locally by capacitors, synchronous condensers or power electronics. "
            "Voltage collapse, where a region's voltage progressively sags and cannot "
            "be arrested, is fundamentally a failure of local reactive supply to "
            "keep up with reactive demand.",
            "Stability divides into three time scales. Steady-state stability is "
            "whether the system returns to its operating point after a small "
            "disturbance, analysed by linearizing about the operating point. "
            "Transient stability concerns the first few seconds after a large "
            "disturbance such as a fault, and is governed by the swing equation "
            "relating rotor acceleration to the difference between mechanical input "
            "and electrical output power; the equal-area criterion gives a graphical "
            "answer for a single machine against an infinite bus. Dynamic stability "
            "covers the tens of seconds afterwards, where control systems — "
            "excitation, governor, power system stabilizers — determine whether "
            "oscillations damp or grow.",
            "The grid's frequency is the visible symptom of the real-power balance. "
            "Generation and demand are matched continuously; when demand exceeds "
            "generation, machines slow and frequency falls. A synchronous grid has "
            "one frequency everywhere, so a deficit in one region is instantly "
            "shared by every generator connected to it. Under-frequency load shedding "
            "deliberately disconnects blocks of demand at preset frequency thresholds "
            "to arrest a decline before it cascades — an admission that shedding some "
            "load is preferable to losing the whole system.",
        ),
    },
    {
        "slug": "se-agile-testing",
        "type": ResourceType.STUDY_MATERIAL,
        "title": "Software Testing and Agile Delivery",
        "subtitle": "What a test proves, and how a team keeps proving it every day",
        "department": "CSE",
        "subjects": ["CSE-SE", "CSE-ML"],
        "topics": ["CSE-SE-SOFTWARE-TESTING", "CSE-SE-AGILE-METHODS",
                   "CSE-SE-DEVOPS", "CSE-ML-MODEL-EVALUATION"],
        "authors": ["NEXORA Curriculum Team"],
        "year": 2026,
        "publisher": "NEXORA Demo Corpus",
        "access": AccessType.FREE,
        "difficulty": Difficulty.INTERMEDIATE,
        "level": AcademicLevel.CORE,
        "semester": 5,
        "keywords": ["unit test", "integration test", "test coverage", "regression",
                     "continuous integration", "iterative development"],
        "description": "The testing pyramid, what coverage does and does not "
                       "guarantee, and the practices that let a team release "
                       "frequently without accumulating risk.",
        "text": _text(
            "A test can prove the presence of a defect, never its absence. Every "
            "strategy follows from accepting that: the goal is to spend a fixed "
            "testing budget where defects are most likely and most costly, not to "
            "achieve completeness.",
            "The testing pyramid expresses that budget allocation. Unit tests are "
            "numerous, fast and isolated, exercising a single function or class with "
            "its collaborators replaced by test doubles. Integration tests are fewer "
            "and slower, checking that the real components work together — a "
            "repository against a real database, a client against a real service. "
            "End-to-end tests are fewest and slowest of all, driving the actual user "
            "interface. An inverted pyramid, heavy on end-to-end tests, is slow, "
            "flaky and expensive to diagnose, because a failure at that level rarely "
            "tells you which component broke.",
            "Coverage measures how much code a test suite executes. Statement "
            "coverage asks whether each line ran; branch coverage asks whether each "
            "decision went both ways, which is strictly stronger. High coverage is "
            "necessary but far from sufficient: a test can execute a line and assert "
            "nothing about it, and no coverage metric detects a missing assertion. "
            "Coverage is best used as a negative signal — uncovered code is "
            "definitely untested — rather than a positive one.",
            "Equivalence partitioning and boundary-value analysis are the two "
            "techniques that raise defect-finding per test case. Partitioning divides "
            "the input space into classes expected to behave identically and tests "
            "one member of each, on the assumption that if one fails they all fail. "
            "Boundary analysis targets the edges of those classes, because off-by-one "
            "errors cluster there: test the value at the boundary, one below and one "
            "above.",
            "Regression is the risk that a change breaks something that worked. A "
            "regression suite is the accumulated set of tests that guards against it, "
            "and it only functions if it runs on every change — which requires it to "
            "be fast. This is the real engineering constraint behind the pyramid: a "
            "suite that takes an hour does not run on every commit, and a suite that "
            "does not run on every commit does not prevent regressions.",
            "Continuous integration means every change is built and tested against "
            "the shared trunk within minutes of being pushed. Its value is not "
            "automation for its own sake but the drastic reduction in integration "
            "cost: a conflict between two changes is found while both authors still "
            "remember writing them, rather than at the end of a phase when nobody "
            "does. Continuous delivery extends this by keeping the artifact always "
            "deployable, so that releasing becomes a routine decision rather than a "
            "project.",
            "Agile methods change what testing has to support. Short iterations mean "
            "requirements arrive continuously and are expected to change, so tests "
            "are the only durable specification of behaviour — a property usually "
            "called executable documentation. A definition of done that includes "
            "passing tests and reviewed code turns quality into a per-iteration "
            "constraint rather than a final phase, which is the substantive "
            "difference between iterative development and a waterfall schedule with "
            "shorter boxes.",
        ),
    },
)
