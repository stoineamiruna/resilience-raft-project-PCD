import time
import requests
import matplotlib.pyplot as plt
import os

NODES = ['http://localhost:5001', 'http://localhost:5002', 'http://localhost:5003']

def get_total_internal_messages():
    total = 0
    for node in NODES:
        try:
            res = requests.get(f"{node}/status", timeout=1)
            if res.status_code == 200:
                total += res.json().get('internal_messages', 0)
        except: pass
    return total

def find_leader():
    for node in NODES:
        try:
            res = requests.get(f"{node}/status", timeout=1)
            if res.status_code == 200 and res.json().get('state') == 'LEADER':
                return node
        except: pass
    return None

def run_benchmark():
    print("Finding leader...")
    leader_url = find_leader()
    if not leader_url:
        print("No leader found. Is the cluster running?")
        return

    print(f"Leader found at {leader_url}. Starting benchmark (100 requests)...")
    
    # Inregistram cate mesaje s-au trimis inainte de benchmark
    start_messages = get_total_internal_messages()
    
    latencies = []
    success_count = 0
    start_time = time.time()

    for i in range(100):
        req_start = time.time()
        try:
            res = requests.post(f"{leader_url}/put", json={'key': f'key_{i}', 'value': f'val_{i}'}, timeout=1)
            if res.status_code == 200:
                success_count += 1
        except Exception as e:
            pass
        
        latency = (time.time() - req_start) * 1000  # In milisecunde
        latencies.append(latency)
        time.sleep(0.05)  # Mici pauze pentru a nu bloca serverul de test

    total_time = time.time() - start_time
    # Calculam overhead-ul
    end_messages = get_total_internal_messages()
    overhead_messages = end_messages - start_messages

    throughput = success_count / total_time
    avg_latency = sum(latencies) / len(latencies) if latencies else 0
    min_latency = min(latencies) if latencies else 0
    max_latency = max(latencies) if latencies else 0

    print(f"\n=== Benchmark Results ===")
    print(f"Successful Requests: {success_count}/100")
    print(f"Total Time: {total_time:.2f} seconds")
    print(f"Throughput: {throughput:.2f} req/sec")
    print(f"Average Latency: {avg_latency:.2f} ms")
    print(f"Min Latency: {min_latency:.2f} ms")
    print(f"Max Latency: {max_latency:.2f} ms")
    print(f"Total Internal Messages (Overhead): {overhead_messages}")
    if success_count > 0:
        print(f"Messages per Request: {overhead_messages / success_count:.2f}")

    if not latencies:
        return

    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(latencies, color='steelblue', linewidth=0.9, alpha=0.75, label='Per-request latency')
    ax.axhline(avg_latency, color='crimson', linestyle='--', linewidth=1.5,
               label=f'Average: {avg_latency:.1f} ms')
    ax.fill_between(range(len(latencies)), latencies, avg_latency,
                    where=[l > avg_latency for l in latencies],
                    alpha=0.12, color='crimson', label='Above average')
    ax.fill_between(range(len(latencies)), latencies, avg_latency,
                    where=[l <= avg_latency for l in latencies],
                    alpha=0.12, color='steelblue', label='Below average')

    ax.annotate(f'Max: {max_latency:.0f} ms', xy=(latencies.index(max_latency), max_latency),
                xytext=(latencies.index(max_latency) + 3, max_latency - 6),  
                fontsize=8, color='gray',
                arrowprops=dict(arrowstyle='->', color='gray', lw=0.8))

    ax.set_title('Request Latency – Quorum Write Operations (Normal Operation)', fontsize=11)
    ax.set_xlabel('Request Number')
    ax.set_ylabel('Latency (ms)')
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    plt.tight_layout()

    os.makedirs('docs', exist_ok=True)
    plt.savefig('docs/latency_graph.png', dpi=150)
    print("Graph saved as 'docs/latency_graph.png'")

if __name__ == '__main__':
    run_benchmark()