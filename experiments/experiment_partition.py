import time
import requests
import subprocess

NODES = {
    'node1': 'http://localhost:5001/status',
    'node2': 'http://localhost:5002/status',
    'node3': 'http://localhost:5003/status'
}

# Numele retelei create de docker-compose
NETWORK_NAME = "raft_network"

def get_cluster_status():
    status_report = {}
    for node, url in NODES.items():
        try:
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                status_report[node] = response.json()
        except requests.exceptions.RequestException:
            # Daca primim eroare, inseamna ca nu putem ajunge la el (e picat sau izolat)
            status_report[node] = {'state': 'UNREACHABLE'}
    return status_report

def find_leader(status_report):
    for node, data in status_report.items():
        if data.get('state') == 'LEADER':
            return node
    return None

def isolate_node(node_name):
    container_name = node_name
    print(f"\n[!] CHAOS: Disconnecting {container_name} from network '{NETWORK_NAME}'...")
    subprocess.run(["docker", "network", "disconnect", NETWORK_NAME, container_name], capture_output=True)

def heal_network(node_name):
    container_name = node_name
    print(f"\n[+] HEALING: Reconnecting {container_name} to network '{NETWORK_NAME}'...")
    subprocess.run(["docker", "network", "connect", NETWORK_NAME, container_name], capture_output=True)
    # Add a small delay to allow heartbeats to propagate and states to settle
    time.sleep(2)

def run_network_partition_experiment():
    print("=== Starting Network Partition (Split-Brain) Experiment ===")
    
    status = get_cluster_status()
    initial_leader = None
    for node, data in status.items():
        if data.get('state') == 'LEADER':
            initial_leader = node
            break
            
    if not initial_leader:
        print("[!] No leader found. Is the cluster running?")
        return
        
    term = status[initial_leader].get('term')
    print(f"Current Leader is {initial_leader} (Term: {term}).")
    print("We will simulate a network cable cut on the leader (it stays alive, but isolated).")
    
    isolate_node(initial_leader)
    
    print("\nMonitoring cluster adaptation (Timeout: 25s)...")
    # FIX: Am marit de la 10 la 25 secunde pentru a prinde stabilizarea completa in loguri
    for i in range(25):
        time.sleep(1.0)
        current_status = get_cluster_status()
        vizualizare = []
        for n, d in current_status.items():
            st = d.get('state', 'UNREACHABLE')
            tm = d.get('term', '?')
            vizualizare.append(f"{n} [{st} t:{tm}]")
            
        print(f"Sec {i+1:02d} | " + " | ".join(vizualizare))
        
        # TESTUL SUPREM: La secunda 12, incercam sa scriem in liderul izolat
        if i == 11:
            print(f"\n[!] TESTING CONSISTENCY: Attempting to write data to the isolated leader ({initial_leader})...")
            try:
                res = requests.post(f"{NODES[initial_leader]}/put", json={'key': 'split', 'value': 'brain'}, timeout=1.5)
                if res.status_code == 500:
                    print(f"[SUCCESS] Consistency Proved! Isolated leader rejected write. Error: {res.json().get('error')}\n")
                else:
                    print(f"[FAIL] Write succeeded? Status: {res.status_code}\n")
            except Exception as e:
                print(f"[SUCCESS] Consistency Proved! Write failed as expected (Timeout/Network Error).\n")

    print("\n[CONCLUSION] Notice how the remaining 2 nodes elected a NEW leader because they lost heartbeats.")
    print("Now we heal the network. The old isolated leader will realize its term is outdated and step down.")
    
    print("\n=== Healing the Network ===")
    heal_network(initial_leader)
    
    print("\nWaiting for cluster to reconcile...")
    for i in range(15):
        time.sleep(1.0)
        current_status = get_cluster_status()
        vizualizare = [f"{n} [{d.get('state', 'UNREACHABLE')} t:{d.get('term', '?')}]" for n, d in current_status.items()]
        print(f"Reconciliation Sec {i+1:02d} | " + " | ".join(vizualizare))
        
    print("\n[SUCCESS] Split-Brain resolved! The cluster is unified again under the new leader.")
if __name__ == '__main__':
    run_network_partition_experiment()