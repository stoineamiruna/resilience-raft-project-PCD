# Resilience in Distributed Systems: Raft-Based Key-Value Store

This repository contains the complete reproducibility package for a containerized distributed-systems testbed designed to evaluate resilience, leader election, and recovery mechanisms under failure conditions (crashes and network partitions). The implementation is a simplified version of the Raft consensus algorithm.

## Prerequisites
* Docker and Docker Compose
* Python 3.9+
* Required Python packages: `pip install matplotlib requests numpy`

## Project Structure
* `src/node.py`: The core logic for the Raft node (Leader Election, Heartbeats, Quorum-based State Replication via Flask API).
* `src/watchdog_remediation.py`: An external orchestrator that monitors container health and performs automated remediation.
* `docker-compose.yaml`: Configures the 3-node distributed testbed.
* `experiments/workload_benchmark.py`: Generates synthetic traffic to measure availability, throughput, and latency under normal operation.
* `experiments/experiment_baseline.py`: Baseline comparison between single-node reads (no consensus) and quorum writes, reporting latency percentiles and replication overhead.
* `experiments/experiments.py`: Injects a "Crash Fault" (kills the leader) to measure Recovery Time.
* `experiments/experiment_partition.py`: Injects a "Network Partition" (Split-Brain) using Docker networks to evaluate strict data consistency and quorum behavior.
* `experiments/experiment_negative.py`: Kills a majority of nodes (2/3) to demonstrate that quorum cannot be formed and the cluster loses write availability.
* `experiments/experiment_remediation.py`: An automated test that kills a node to verify the watchdog's self-healing capabilities.
* `docs/`: Directory for generated performance graphs (`latency_graph.png`, `baseline_comparison.png`) and the IEEE-style research paper.

## Implementation Notes

The Raft implementation uses **full-state replication** rather than incremental log-based replication. The leader transmits the complete key-value store snapshot on each AppendEntries RPC instead of individual log entries with indices. This preserves the core safety and liveness properties required for the experiments while simplifying the implementation. See the paper (Sections V and XI) for a full discussion of this design choice and its limitations.

* **Crash Recovery / Persistence:** Committed data is persisted to a local JSON file (/tmp/raft_store_{NODE_ID}.json) immediately upon quorum validation, ensuring data survives hard container restarts.
---

## How to Run & Expected Outputs

**Important notes:**
- All scripts must be executed from the **root directory** of the repository.
- Run experiments in the order listed below for consistent results.
- **Stop the watchdog** (`Ctrl+C`) before running `experiment_negative.py`.

---

### 1. Start the Cluster
```bash
docker-compose up --build
```
*Wait approximately 5–10 seconds for the initial leader election to complete before running any experiment.*

---

### 2. Run Normal Operation Benchmark
```bash
python experiments/workload_benchmark.py
```
**Actual Output:**
```
Finding leader...
Leader found at http://localhost:5003. Starting benchmark (100 requests)...

=== Benchmark Results ===
Successful Requests: 100/100
Total Time: 8.92 seconds
Throughput: 11.21 req/sec
Average Latency: 38.82 ms
Min Latency: 21.04 ms
Max Latency: 62.50 ms
Total Internal Messages (Overhead): 218
Messages per Request: 2.18
Graph saved as 'docs/latency_graph.png'
```
*Generates `docs/latency_graph.png` showing per-request latency with average line.*

---

### 3. Run Baseline Comparison (Read vs Quorum Write)
```bash
python experiments/experiment_baseline.py
```
**Actual Output:**
```
=== Baseline Comparison: Single-Node Read vs Quorum Write ===
Finding leader...
Leader found at http://localhost:5003.
Waiting 3s for cluster to stabilize...
[Phase] Measuring Read  (no consensus) (50 requests)...
[Phase] Measuring Write (quorum consensus) (50 requests)...

=== Baseline Comparison Results ===
  Read  — no consensus (single-node response)
    Avg:        24.96 ms   |  Throughput: ~40.1 req/s
    Min:         9.90 ms
    p50:        26.27 ms
    p95:        27.89 ms
    p99:        27.92 ms
    Max:        27.92 ms

  Write — quorum consensus (2/3 nodes must ACK)
    Avg:        40.03 ms   |  Throughput: ~25.0 req/s
    Min:        21.10 ms
    p50:        41.56 ms
    p95:        44.37 ms
    p99:        46.69 ms
    Max:        46.69 ms

Consensus replication overhead (avg): ~15.07 ms per write
Consensus replication overhead (p99): ~18.76 ms per write

Conclusion: Raft quorum replication adds ~15.1 ms avg latency
in exchange for fault-tolerance guarantees (tolerates 1 node failure).

Graph saved as 'docs/baseline_comparison.png'
```
*Generates `docs/baseline_comparison.png` with two panels: latency over time and percentile bar chart.*

---

### 4. Run Leader Crash Experiment (Recovery Time Metric)
```bash
python experiments/experiments.py
```
**Actual Output:**
```
=== Starting Leader Crash Experiment ===
Waiting for cluster to stabilize...
Current Leader: node3 (Term: 3)

[!] INJECTING FAULT: Killing node3 container...
[!] node3 is down.

Monitoring for new leader election (Timeout: 40s)...
Sec 01 | node1 [FOLLOWER t:3] | node2 [FOLLOWER t:3] | node3 [DOWN t:?]
Sec 02 | node1 [LEADER t:4]   | node2 [FOLLOWER t:4] | node3 [DOWN t:?]

[SUCCESS] New leader elected: node1 (Term: 4)
[METRIC] Recovery Time: 10.15 seconds

[+] RECOVERING: Starting node3 container...
[+] node3 is back up.

Experiment finished. Waiting 5s for network to heal...
```
> **Note on Recovery Time:** The ~10s value includes the container shutdown phase from `docker stop` plus the Raft election phase (~2s). The election itself is consistent with the configured timeout of 3–6 seconds.

---

### 5. Run Network Partition / Split-Brain Experiment
```bash
python experiments/experiment_partition.py
```
**Actual Output:**
```
=== Starting Network Partition (Split-Brain) Experiment ===
Current Leader is node1 (Term: 2).
We will simulate a network cable cut on the leader (it stays alive, but isolated).

[!] CHAOS: Disconnecting resilience-raft-project-node1-1 from network 'resilience-raft-project_raft_network'...

Monitoring cluster adaptation (Timeout: 25s)...
Sec 01 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:2] | node3 [FOLLOWER t:2]
Sec 02 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 03 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 04 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 05 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 06 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 07 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 08 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 09 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 10 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 11 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 12 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]

[!] TESTING CONSISTENCY: Attempting to write data to the isolated leader (node1)...
[SUCCESS] Consistency Proved! Write failed as expected (Timeout/Network Error).

Sec 13 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 14 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 15 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 16 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 17 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 18 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 19 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 20 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 21 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 22 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 23 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 24 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]
Sec 25 | node1 [UNREACHABLE t:?] | node2 [FOLLOWER t:3] | node3 [LEADER t:3]

[CONCLUSION] Notice how the remaining 2 nodes elected a NEW leader because they lost heartbeats.
Now we heal the network. The old isolated leader will realize its term is outdated and step down.

=== Healing the Network ===

[+] HEALING: Reconnecting resilience-raft-project-node1-1 to network 'resilience-raft-project_raft_network'...

Waiting for cluster to reconcile...
Reconciliation Sec 01 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 02 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 03 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 04 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 05 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 06 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 07 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 08 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 09 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 10 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 11 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 12 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 13 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 14 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]
Reconciliation Sec 15 | node1 [LEADER t:4] | node2 [FOLLOWER t:4] | node3 [FOLLOWER t:4]

[SUCCESS] Split-Brain resolved! The cluster is unified again under the new leader.
```

---

### 6. Run Majority Loss Experiment (Negative / Failure Case)

> **Important:** Make sure `watchdog_remediation.py` is **NOT** running before this test.

```bash
python experiments/experiment_negative.py
```
**Actual Output:**
```
=== Starting Majority Loss (Negative) Experiment ===
[!] INJECTING FAULT: Killing node2...
[!] INJECTING FAULT: Killing node3...

Monitoring survivor node (expecting NO leader election)...
Sec 01 | node1 [FOLLOWER t:9]    | node2 [DOWN t:?] | node3 [DOWN t:?]
Sec 02 | node1 [CANDIDATE t:12]  | node2 [DOWN t:?] | node3 [DOWN t:?]
...
Sec 20 | node1 [CANDIDATE t:49]  | node2 [DOWN t:?] | node3 [DOWN t:?]

[CONCLUSION] As expected, the cluster lost availability because a quorum (2/3) cannot be formed.

=== Healing the Network ===
[+] RECOVERING: Starting node2...
[+] RECOVERING: Starting node3...

Waiting for cluster to recover...
Recovery Sec 01 | node1 [CANDIDATE t:52] | node2 [FOLLOWER t:0] | node3 [FOLLOWER t:0]
...
Recovery Sec 05 | node1 [LEADER t:53]    | node2 [FOLLOWER t:53] | node3 [CANDIDATE t:1]

[SUCCESS] The system successfully recovered once the majority was restored!
```
> **Interpretation:** The surviving node (node1) keeps attempting elections (CANDIDATE) but cannot win without quorum. The rapid term increment (9→12→...→49) reflects repeated failed election attempts — expected Raft liveness behavior. Once the two nodes are restored, quorum is re-established and a leader is elected within seconds.

---

### 7. Run Automated Remediation Extension (Self-Healing)

This test requires **two separate terminals**.

**Terminal A — Start the Watchdog:**
```bash
python src/watchdog_remediation.py
```
**Expected Watchdog Output (Terminal A):**
```
=== Automated Remediation Watchdog Started ===
Monitoring cluster health... (Press Ctrl+C to stop)

[ALERT] Watchdog detected resilience-raft-project-node2-1 is DOWN!
[ACTION] Auto-remediating... restarting resilience-raft-project-node2-1...
[SUCCESS] resilience-raft-project-node2-1 is back online!
```

**Terminal B — Run the Remediation Test:**
```bash
python experiments/experiment_remediation.py
```
**Actual Output (Terminal B):**
```
=== Starting Automated Remediation Test ===
NOTE: Make sure 'watchdog_remediation.py' is running in another terminal!

[!] INJECTING FAULT: Killing node2 container...

Monitoring node2 to see if the Watchdog resurrects it (Timeout: 20s)...
Sec 01 | node2 is [DOWN]
Sec 02 | node2 is [FOLLOWER]

[SUCCESS] Amazing! node2 was automatically remediated and is back online as FOLLOWER!
```