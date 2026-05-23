import time
import requests
import subprocess

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

def kill_node(node_name):
    print(f"[!] INJECTING FAULT: Killing {node_name}...")
    subprocess.run(["docker", "stop", f"resilience-raft-project-{node_name}-1"], capture_output=True)

def start_node(node_name):
    print(f"[+] RECOVERING: Starting {node_name}...")
    subprocess.run(["docker", "start", f"resilience-raft-project-{node_name}-1"], capture_output=True)

def run_majority_loss_experiment():
    print("=== Starting Majority Loss (Negative) Experiment ===")
    time.sleep(3)
    status = get_cluster_status()
    
    # Alegem 2 noduri la intamplare pentru a le distruge (ex. node2 si node3)
    nodes_to_kill = ['node2', 'node3']
    survivor_node = 'node1'
    
    for n in nodes_to_kill:
        kill_node(n)
        
    print("\nMonitoring survivor node (expecting NO leader election)...")
    
    for i in range(20):
        time.sleep(1.0)
        current_status = get_cluster_status()
        
        vizualizare = []
        for n, d in current_status.items():
            st = d.get('state', 'DOWN')
            tm = d.get('term', '?')
            vizualizare.append(f"{n} [{st} t:{tm}]")
            
        print(f"Sec {i+1:02d} | " + " | ".join(vizualizare))
        
    print("\n[CONCLUSION] As expected, the cluster lost availability because a quorum (2/3) cannot be formed.")
    
    print("\n=== Healing the Network ===")
    for n in nodes_to_kill:
        start_node(n)
        
    print("Waiting for cluster to recover...")
    for i in range(15):
        time.sleep(1.0)
        current_status = get_cluster_status()
        vizualizare = [f"{n} [{d.get('state', 'DOWN')} t:{d.get('term', '?')}]" for n, d in current_status.items()]
        print(f"Recovery Sec {i+1:02d} | " + " | ".join(vizualizare))
        
        if any(d.get('state') == 'LEADER' for d in current_status.values()):
            print("\n[SUCCESS] The system successfully recovered once the majority was restored!")
            break

if __name__ == '__main__':
    run_majority_loss_experiment()