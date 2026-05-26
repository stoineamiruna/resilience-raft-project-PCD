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
            response = requests.get(url, timeout=1)
            if response.status_code == 200:
                status_report[node] = response.json()
        except requests.exceptions.RequestException:
            status_report[node] = {'state': 'DOWN'}
    return status_report

def kill_node(node_name):
    print(f"\n[!] INJECTING FAULT: Killing {node_name} container...")
    subprocess.run(["docker", "stop", node_name], capture_output=True)

def run_remediation_test():
    print("=== Starting Automated Remediation Test ===")
    print("NOTE: Make sure 'watchdog_remediation.py' is running in another terminal!\n")
    time.sleep(2)
    
    target_node = 'node2'
    
    # 1. Omoram nodul intentionat
    kill_node(target_node)
    
    # 2. Monitorizam daca Watchdog-ul il invie
    print(f"\nMonitoring {target_node} to see if the Watchdog resurrects it (Timeout: 20s)...")
    for i in range(20):
        time.sleep(1.0)
        status = get_cluster_status()
        node_state = status[target_node].get('state', 'DOWN')
        
        print(f"Sec {i+1:02d} | {target_node} is [{node_state}]")
        
        if node_state != 'DOWN':
            print(f"\n[SUCCESS] Amazing! {target_node} was automatically remediated and is back online as {node_state}!")
            break
    else:
        print("\n[FAIL] Node did not recover. Is the watchdog running?")

if __name__ == '__main__':
    run_remediation_test()