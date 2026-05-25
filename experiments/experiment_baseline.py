import time
import requests
import matplotlib.pyplot as plt
import numpy as np
import os

NODES = ['http://localhost:5001', 'http://localhost:5002', 'http://localhost:5003']

def find_leader():
    for node in NODES:
        try:
            res = requests.get(f"{node}/status", timeout=1)
            if res.status_code == 200 and res.json().get('state') == 'LEADER':
                return node
        except:
            pass
    return None

def percentile(data, p):
    sorted_data = sorted(data)
    idx = int(len(sorted_data) * p / 100)
    return sorted_data[min(idx, len(sorted_data) - 1)]

def measure_latencies(label, fn, n=50, delay=0.02):
    print(f"[Phase] Measuring {label} ({n} requests)...")
    latencies = []
    for i in range(n):
        start = time.time()
        try:
            fn(i)
        except:
            pass
        latencies.append((time.time() - start) * 1000)
        time.sleep(delay)
    return latencies

def print_stats(label, latencies):
    avg  = sum(latencies) / len(latencies)
    p50  = percentile(latencies, 50)
    p95  = percentile(latencies, 95)
    p99  = percentile(latencies, 99)
    mn   = min(latencies)
    mx   = max(latencies)
    tput = 1000 / avg
    print(f"\n  {label}")
    print(f"    Avg:        {avg:.2f} ms   |  Throughput: ~{tput:.1f} req/s")
    print(f"    Min:        {mn:.2f} ms")
    print(f"    p50:        {p50:.2f} ms")
    print(f"    p95:        {p95:.2f} ms")
    print(f"    p99:        {p99:.2f} ms")
    print(f"    Max:        {mx:.2f} ms")
    return {'avg': avg, 'p50': p50, 'p95': p95, 'p99': p99, 'min': mn, 'max': mx}

def plot_comparison(read_lat, write_lat, read_stats, write_stats):
    fig, axes = plt.subplots(1, 2, figsize=(12, 4))

    # --- Plot 1: Latency over time ---
    ax1 = axes[0]
    ax1.plot(read_lat,  color='steelblue', linewidth=0.9, alpha=0.8, label='Read (no consensus)')
    ax1.plot(write_lat, color='crimson',   linewidth=0.9, alpha=0.8, label='Write (quorum)')
    ax1.axhline(read_stats['avg'],  color='steelblue', linestyle='--', linewidth=1.2)
    ax1.axhline(write_stats['avg'], color='crimson',   linestyle='--', linewidth=1.2)
    ax1.set_title('Read vs Write Latency over Time', fontsize=11)
    ax1.set_xlabel('Request Number')
    ax1.set_ylabel('Latency (ms)')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)

    # --- Plot 2: Percentile bar chart ---
    ax2 = axes[1]
    metrics    = ['Avg', 'p50', 'p95', 'p99']
    read_vals  = [read_stats['avg'],  read_stats['p50'],  read_stats['p95'],  read_stats['p99']]
    write_vals = [write_stats['avg'], write_stats['p50'], write_stats['p95'], write_stats['p99']]

    x     = np.arange(len(metrics))
    width = 0.35
    bars1 = ax2.bar(x - width/2, read_vals,  width, label='Read (no consensus)', color='steelblue', alpha=0.85)
    bars2 = ax2.bar(x + width/2, write_vals, width, label='Write (quorum)',      color='crimson',   alpha=0.85)

    ax2.set_title('Latency Percentiles: Read vs Quorum Write', fontsize=11)
    ax2.set_xlabel('Percentile')
    ax2.set_ylabel('Latency (ms)')
    ax2.set_xticks(x)
    ax2.set_xticklabels(metrics)
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3, axis='y')

    for bar in bars1:
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                 f'{bar.get_height():.1f}', ha='center', va='bottom', fontsize=7.5)
    for bar in bars2:
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                 f'{bar.get_height():.1f}', ha='center', va='bottom', fontsize=7.5)

    overhead = write_stats['avg'] - read_stats['avg']
    fig.suptitle(
        f'Baseline Comparison – Consensus Replication Overhead: ~{overhead:.1f} ms per write',
        fontsize=12, fontweight='bold'
    )
    plt.tight_layout()
    os.makedirs('docs', exist_ok=True)
    plt.savefig('docs/baseline_comparison.png', dpi=150)
    print("\nGraph saved as 'docs/baseline_comparison.png'")

def run_baseline():
    print("=== Baseline Comparison: Single-Node Read vs Quorum Write ===")
    print("Finding leader...")
    leader_url = find_leader()
    if not leader_url:
        print("No leader found. Is the cluster running?")
        return

    print(f"Leader found at {leader_url}.")
    print("Waiting 3s for cluster to stabilize...")
    time.sleep(3)

    read_lat  = measure_latencies(
        "Read  (no consensus)",
        lambda i: requests.get(f"{leader_url}/get", params={'key': f'key_{i}'}, timeout=2)
    )
    write_lat = measure_latencies(
        "Write (quorum consensus)",
        lambda i: requests.post(f"{leader_url}/put",
                                json={'key': f'bl_key_{i}', 'value': f'v_{i}'},
                                timeout=2)
    )

    print("\n=== Baseline Comparison Results ===")
    read_stats  = print_stats("Read  — no consensus (single-node response)", read_lat)
    write_stats = print_stats("Write — quorum consensus (2/3 nodes must ACK)", write_lat)

    overhead     = write_stats['avg'] - read_stats['avg']
    p99_overhead = write_stats['p99'] - read_stats['p99']
    print(f"\n  Consensus replication overhead (avg): ~{overhead:.2f} ms per write")
    print(f"  Consensus replication overhead (p99): ~{p99_overhead:.2f} ms per write")
    print(f"\n  Conclusion: Raft quorum replication adds ~{overhead:.1f} ms avg latency")
    print(f"  in exchange for fault-tolerance guarantees (tolerates 1 node failure).")

    plot_comparison(read_lat, write_lat, read_stats, write_stats)

if __name__ == '__main__':
    run_baseline()