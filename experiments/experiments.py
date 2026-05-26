import time
import requests
import subprocess

# --- Configurare ---
NODES = {
    'node1': 'http://localhost:5001/status',
    'node2': 'http://localhost:5002/status',
    'node3': 'http://localhost:5003/status'
}

def get_cluster_status():
    status_report = {}
    for node, url in NODES.items():
        try:
            response = requests.get(url, timeout=2)
            if response.status_code == 200:
                status_report[node] = response.json()
        except requests.exceptions.RequestException:
            status_report[node] = {'state': 'DOWN'}
    return status_report

def find_leader(status_report):
    for node, data in status_report.items():
        if data.get('state') == 'LEADER':
            return node
    return None

def kill_node(node_name):
    print(f"\n[!] INJECTING FAULT: Killing {node_name} container...")
    container_name = node_name
    subprocess.run(["docker", "stop", container_name], capture_output=True)
    print(f"[!] {node_name} is down.")

def start_node(node_name):
    print(f"\n[+] RECOVERING: Starting {node_name} container...")
    container_name = node_name
    subprocess.run(["docker", "start", container_name], capture_output=True)
    print(f"[+] {node_name} is back up.")

def run_leader_crash_experiment():
    print("=== Starting Leader Crash Experiment ===")
    
    print("Waiting for cluster to stabilize...")
    time.sleep(5)
    status = get_cluster_status()
    initial_leader = find_leader(status)
    
    if not initial_leader:
        print("Error: No leader found initially. Aborting.")
        return

    print(f"Current Leader: {initial_leader} (Term: {status[initial_leader].get('term')})")
    
    kill_node(initial_leader)
    crash_time = time.time()
    
    print("\nMonitoring for new leader election (Timeout: 40s)...")
    
    new_leader = None
    
    for i in range(40):
        time.sleep(1.0) # Verificăm o dată pe secundă
        current_status = get_cluster_status()
        
        # Generăm un log vizual curat pentru a vedea ce fac nodurile
        vizualizare = []
        for n, d in current_status.items():
            st = d.get('state', 'DOWN')
            tm = d.get('term', '?')
            vizualizare.append(f"{n} [{st} t:{tm}]")
        
        print(f"Sec {i+1:02d} | " + " | ".join(vizualizare))
        
        potential_leader = find_leader(current_status)
        
        if potential_leader and potential_leader != initial_leader:
            new_leader = potential_leader
            recovery_time = time.time() - crash_time
            print(f"\n[SUCCESS] New leader elected: {new_leader} (Term: {current_status[new_leader].get('term')})")
            print(f"[METRIC] Recovery Time: {recovery_time:.2f} seconds")
            break

    if not new_leader:
        print("\n[FAIL] No new leader elected within 40 seconds.")
            
    start_node(initial_leader)
    print("\nExperiment finished. Waiting 5s for network to heal...")
    time.sleep(5)

if __name__ == '__main__':
    run_leader_crash_experiment()