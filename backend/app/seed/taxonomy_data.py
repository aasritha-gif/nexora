"""Canonical academic taxonomy: departments, subjects, topics.

This is reference data that ships with NEXORA — registration validates a
department against it, `RuleClassifier` votes subject/topic names against it,
and the Neo4j graph is built from it. It is *not* demo data and carries no
seed label.

Subject names are load-bearing: `app.ingestion.classifier._SYNONYMS` is keyed by
the lowercased subject name, so renaming a subject here silently disables its
synonym expansion until the classifier is updated to match.
"""

from __future__ import annotations

import re

from app.models.taxonomy import Department, Subject, Topic

# (code, name, description, sort_order, icon, color)
DEPARTMENTS: tuple[tuple[str, str, str, int, str, str], ...] = (
    ("CSE", "Computer Science & Engineering",
     "Algorithms, data, software systems, networks and intelligent computing.",
     10, "cpu", "#6366F1"),
    ("ECE", "Electronics & Communication Engineering",
     "Electronic circuits, signals, communication systems and embedded devices.",
     20, "radio", "#0EA5E9"),
    ("EEE", "Electrical & Electronics Engineering",
     "Power generation, electrical machines, drives and control systems.",
     30, "zap", "#F59E0B"),
    ("MECH", "Mechanical Engineering",
     "Thermal sciences, materials, manufacturing and machine design.",
     40, "cog", "#EF4444"),
    ("CIVIL", "Civil Engineering",
     "Structures, geotechnics, surveying and the built environment.",
     50, "building", "#78716C"),
    ("BIOTECH", "Biotechnology",
     "Genetic engineering, bioprocesses, microbiology and bioinformatics.",
     60, "dna", "#10B981"),
    ("MATH", "Mathematics",
     "The analytical foundation every other department builds on.",
     70, "sigma", "#8B5CF6"),
    ("PHYS", "Physics",
     "Classical, quantum and statistical descriptions of the physical world.",
     80, "atom", "#3B82F6"),
    ("CHEM", "Chemistry",
     "Structure, reactivity and analysis of matter.",
     90, "flask", "#EC4899"),
)

# (department_code, slug, name, semester, description, (topic names))
SUBJECTS: tuple[tuple[str, str, str, int, str, tuple[str, ...]], ...] = (
    # ── Computer Science & Engineering ────────────────────────────────
    ("CSE", "DSA", "Data Structures", 3,
     "Organising data so the operations you actually perform stay cheap.",
     ("Arrays", "Linked Lists", "Stacks", "Queues", "Trees", "Binary Search Trees",
      "Heaps", "Hashing", "Sorting Algorithms", "Graph Algorithms", "Complexity Analysis")),
    ("CSE", "AI", "Artificial Intelligence", 5,
     "Agents that search, reason, perceive and act in uncertain environments.",
     ("Search Strategies", "Knowledge Representation", "Natural Language Processing",
      "Computer Vision", "Automated Planning", "Constraint Satisfaction", "AI Ethics")),
    ("CSE", "ML", "Machine Learning", 6,
     "Learning predictive structure from data instead of hand-coding it.",
     ("Supervised Learning", "Unsupervised Learning", "Reinforcement Learning",
      "Neural Networks", "Deep Learning", "Feature Engineering", "Model Evaluation",
      "Regularization")),
    ("CSE", "DBMS", "Database Management", 4,
     "Modelling, storing and querying data with correctness guarantees.",
     ("Relational Model", "SQL", "Query Processing", "Normalization",
      "Transactions And Concurrency", "Indexing", "NoSQL Databases",
      "Distributed Databases", "Data Warehousing")),
    ("CSE", "OS", "Operating Systems", 4,
     "The layer that arbitrates hardware between competing programs.",
     ("Process Management", "Process Scheduling", "Deadlock", "Synchronization",
      "Memory Management", "Virtual Memory", "File Systems", "Kernel Design")),
    ("CSE", "NET", "Computer Networks", 5,
     "How data moves between machines across a layered protocol stack.",
     ("OSI Model", "TCP/IP Suite", "Routing Protocols", "Transport Layer",
      "DNS And Addressing", "Network Security", "Wireless Networks",
      "Quality Of Service")),
    ("CSE", "SE", "Software Engineering", 5,
     "Building software that survives contact with real teams and real users.",
     ("Requirements Engineering", "Agile Methods", "Software Testing",
      "Design Patterns", "DevOps", "Software Architecture", "Software Metrics",
      "Version Control")),
    ("CSE", "SEC", "Cyber Security", 7,
     "Protecting systems and data against deliberate attack.",
     ("Cryptography", "Intrusion Detection", "Malware Analysis", "Penetration Testing",
      "Vulnerability Assessment", "Network Firewalls", "Security Policies",
      "Secure Coding")),

    # ── Electronics & Communication Engineering ───────────────────────
    ("ECE", "EDC", "Electronics", 3,
     "Semiconductor devices and the analogue circuits built from them.",
     ("Semiconductor Diodes", "Bipolar Junction Transistors", "Field Effect Transistors",
      "Operational Amplifiers", "VLSI Design", "Biasing Circuits")),
    ("ECE", "SIG", "Signals And Systems", 4,
     "Representing and transforming signals in time and frequency domains.",
     ("Continuous Time Signals", "Discrete Time Signals", "Convolution",
      "Laplace Transform", "Z Transform", "Sampling Theorem")),
    ("ECE", "DSP", "Digital Signal Processing", 5,
     "Algorithms that process sampled signals in hardware and software.",
     ("Discrete Fourier Transform", "Fast Fourier Transform", "Digital Filters",
      "Windowing", "Multirate Processing", "DSP Processors")),
    ("ECE", "COMM", "Communication Systems", 6,
     "Getting information across a noisy channel reliably.",
     ("Analog Modulation", "Digital Modulation", "Information Theory",
      "Wireless Communication", "Antennas", "Error Correction Codes",
      "Multiplexing")),
    ("ECE", "EMB", "Embedded Systems", 6,
     "Computers dedicated to a single task under real-time constraints.",
     ("Microcontrollers", "Real Time Operating Systems", "Sensor Interfacing",
      "ARM Architecture", "Embedded Firmware", "Internet Of Things")),

    # ── Electrical & Electronics Engineering ──────────────────────────
    ("EEE", "PS", "Power Systems", 5,
     "Generation, transmission and stability of electrical grids.",
     ("Power Generation", "Transmission Lines", "Load Flow Analysis",
      "Power Grid Stability", "Renewable Energy Integration", "Fault Analysis",
      "Switchgear And Protection")),
    ("EEE", "EM", "Electrical Machines", 4,
     "Electromechanical energy conversion in motors, generators and transformers.",
     ("Transformers", "DC Machines", "Induction Motors", "Synchronous Machines",
      "Magnetic Circuits", "Machine Testing")),
    ("EEE", "CS", "Control Systems", 5,
     "Making dynamic systems track a target despite disturbance.",
     ("Transfer Functions", "Stability Analysis", "PID Controllers",
      "State Space Models", "Root Locus", "Frequency Response")),
    ("EEE", "PE", "Power Electronics", 6,
     "Solid-state conversion and conditioning of electrical power.",
     ("Rectifiers", "Inverters", "DC-DC Converters", "Thyristors",
      "Pulse Width Modulation", "Motor Drives")),

    # ── Mechanical Engineering ────────────────────────────────────────
    ("MECH", "THERMO", "Thermodynamics", 3,
     "Energy, entropy and the limits of what heat engines can do.",
     ("Laws Of Thermodynamics", "Entropy", "Heat Transfer", "Thermal Cycles",
      "Gas Mixtures", "Availability Analysis")),
    ("MECH", "FM", "Fluid Mechanics", 4,
     "Behaviour of liquids and gases at rest and in motion.",
     ("Bernoulli Equation", "Viscous Flow", "Boundary Layers", "Turbomachinery",
      "Dimensional Analysis", "Pipe Flow")),
    ("MECH", "SOM", "Strength Of Materials", 4,
     "How solid components deform and fail under load.",
     ("Stress And Strain", "Bending Of Beams", "Torsion", "Column Buckling",
      "Principal Stresses", "Failure Theories")),
    ("MECH", "MANU", "Manufacturing Processes", 5,
     "Turning raw material into a finished part.",
     ("Casting", "Machining", "Welding", "Metal Forming", "Additive Manufacturing",
      "Metrology", "CNC Programming")),
    ("MECH", "ICE", "Internal Combustion Engines", 6,
     "Thermodynamics and design of reciprocating engines.",
     ("Spark Ignition Engines", "Compression Ignition Engines", "Engine Performance",
      "Fuel Injection", "Emissions Control", "Turbocharging")),

    # ── Civil Engineering ─────────────────────────────────────────────
    ("CIVIL", "SA", "Structural Analysis", 5,
     "Determining forces and displacements in load-bearing structures.",
     ("Truss Analysis", "Moment Distribution", "Influence Lines", "Beams And Frames",
      "Finite Element Method", "Cable Structures")),
    ("CIVIL", "RC", "Concrete Design", 6,
     "Proportioning reinforced and prestressed concrete members.",
     ("Reinforced Concrete Beams", "Columns And Footings", "Prestressed Concrete",
      "Limit State Design", "Slab Design", "Retaining Walls")),
    ("CIVIL", "GT", "Geotechnical Engineering", 5,
     "Soil behaviour and the foundations built on it.",
     ("Soil Mechanics", "Foundation Design", "Slope Stability", "Bearing Capacity",
      "Consolidation", "Earth Pressure")),
    ("CIVIL", "SURV", "Surveying", 3,
     "Measuring and mapping the physical surface of the earth.",
     ("Levelling", "Total Station", "Photogrammetry", "Remote Sensing",
      "Contour Mapping", "Geographic Information Systems")),

    # ── Biotechnology ─────────────────────────────────────────────────
    ("BIOTECH", "CORE", "Biotechnology", 3,
     "Using living systems to make useful products at scale.",
     ("Fermentation Technology", "Bioprocess Engineering", "Tissue Culture",
      "Downstream Processing", "Enzyme Technology", "Bioreactors")),
    ("BIOTECH", "GENE", "Genetic Engineering", 5,
     "Deliberate modification of genetic material.",
     ("Recombinant DNA", "CRISPR", "Gene Cloning", "PCR Techniques",
      "Gene Expression", "Transgenic Organisms")),
    ("BIOTECH", "MICRO", "Microbiology", 4,
     "Bacteria, viruses and the immune systems that contend with them.",
     ("Bacterial Growth", "Immunology", "Sterilization", "Virology",
      "Microbial Genetics", "Antibiotics")),
    ("BIOTECH", "BIOINFO", "Bioinformatics", 6,
     "Computational analysis of biological sequences and structures.",
     ("Sequence Alignment", "Genome Assembly", "Protein Structure Prediction",
      "Biological Databases", "Phylogenetics", "Molecular Docking")),

    # ── Mathematics ───────────────────────────────────────────────────
    ("MATH", "CALC", "Calculus", 1,
     "Continuity, change and accumulation.",
     ("Limits And Continuity", "Derivatives", "Integration", "Multivariable Calculus",
      "Differential Equations", "Series And Sequences", "Partial Derivatives")),
    ("MATH", "LA", "Linear Algebra", 2,
     "Vector spaces and the linear maps between them.",
     ("Matrix Operations", "Eigenvalues And Eigenvectors", "Vector Spaces",
      "Linear Transformations", "Determinants", "Singular Value Decomposition",
      "Systems Of Linear Equations")),
    ("MATH", "DM", "Discrete Mathematics", 2,
     "Countable structures behind computing and proof.",
     ("Set Theory", "Combinatorics", "Graph Theory", "Logic And Proofs",
      "Boolean Algebra", "Recurrence Relations", "Number Theory")),
    ("MATH", "PROB", "Probability And Statistics", 3,
     "Reasoning under uncertainty from data.",
     ("Random Variables", "Probability Distributions", "Hypothesis Testing",
      "Bayesian Inference", "Regression Analysis", "Sampling Theory",
      "Stochastic Processes")),
    ("MATH", "NUM", "Numerical Methods", 4,
     "Approximate solutions when closed-form ones are unavailable.",
     ("Root Finding", "Numerical Integration", "Interpolation", "Iterative Solvers",
      "Numerical Differentiation", "Error Analysis")),

    # ── Physics ───────────────────────────────────────────────────────
    ("PHYS", "CLASS", "Classical Mechanics", 2,
     "Motion of bodies under forces, from Newton to Hamilton.",
     ("Newtonian Mechanics", "Lagrangian Mechanics", "Hamiltonian Mechanics",
      "Rigid Body Motion", "Oscillations", "Central Forces")),
    ("PHYS", "EM", "Electromagnetism", 4,
     "Electric and magnetic fields unified by Maxwell's equations.",
     ("Electrostatics", "Magnetostatics", "Maxwell Equations",
      "Electromagnetic Waves", "Dielectrics", "Magnetic Materials")),
    ("PHYS", "QM", "Quantum Mechanics", 6,
     "The non-classical rules governing matter at small scales.",
     ("Wave Functions", "Schrodinger Equation", "Operators And Observables",
      "Quantum Entanglement", "Angular Momentum", "Perturbation Theory",
      "Quantum Computing")),
    ("PHYS", "STAT", "Statistical Mechanics", 7,
     "Deriving bulk behaviour from the statistics of many particles.",
     ("Partition Functions", "Boltzmann Distribution", "Entropy And Ensembles",
      "Phase Transitions", "Fermi Dirac Statistics", "Bose Einstein Statistics")),

    # ── Chemistry ─────────────────────────────────────────────────────
    ("CHEM", "IC", "Inorganic Chemistry", 2,
     "Elements, periodic trends and coordination compounds.",
     ("Periodic Trends", "Coordination Compounds", "Crystal Field Theory",
      "Solid State Chemistry", "Organometallics", "Bioinorganic Chemistry")),
    ("CHEM", "OC", "Organic Chemistry", 3,
     "Structure, reactivity and synthesis of carbon compounds.",
     ("Reaction Mechanisms", "Stereochemistry", "Aromatic Compounds",
      "Synthesis Routes", "Functional Groups", "Alkanes And Alkenes",
      "Spectroscopic Identification")),
    ("CHEM", "PC", "Physical Chemistry", 4,
     "The physics underlying chemical behaviour.",
     ("Chemical Kinetics", "Thermochemistry", "Electrochemistry", "Quantum Chemistry",
      "Surface Chemistry", "Chemical Equilibrium")),
    ("CHEM", "AC", "Analytical Chemistry", 5,
     "Identifying and quantifying what a sample contains.",
     ("Chromatography", "Spectroscopy", "Titration Methods", "Mass Spectrometry",
      "Electroanalytical Methods", "Sample Preparation")),
)

# Topic names are common across subjects ("Entropy", "Graph Theory"), so codes
# carry their subject prefix to stay unique in MongoDB and Neo4j.
_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    return _SLUG_RE.sub("-", text.lower()).strip("-").upper()


def build_departments() -> list[Department]:
    return [
        Department(code=code, name=name, description=description,
                   sort_order=sort_order, icon=icon, color=color)
        for code, name, description, sort_order, icon, color in DEPARTMENTS
    ]


def build_subjects() -> list[Subject]:
    return [
        Subject(code=f"{dept}-{slug}", name=name, department_code=dept,
                description=description, semester=semester)
        for dept, slug, name, semester, description, _ in SUBJECTS
    ]


def build_topics() -> list[Topic]:
    topics: list[Topic] = []
    for dept, slug, _name, _semester, _description, names in SUBJECTS:
        subject_code = f"{dept}-{slug}"
        for topic_name in names:
            topics.append(Topic(
                code=f"{subject_code}-{_slug(topic_name)}",
                name=topic_name,
                subject_code=subject_code,
            ))
    return topics
