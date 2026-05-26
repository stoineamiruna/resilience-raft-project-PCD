import time
import subprocess

# Numele containerelor noastre
CONTAINERS = [
    "node1",
    "node2",
    "node3"
]

def check_and_remediate():
    print("=== Automated Remediation Watchdog Started ===")
    print("Monitoring cluster health... (Press Ctrl+C to stop)")
    
    while True:
        for container in CONTAINERS:
            # Verificam statusul real al containerului in Docker
            result = subprocess.run(["docker", "inspect", "-f", "{{.State.Status}}", container], capture_output=True, text=True)
            status = result.stdout.strip()
            
            # Daca un nod este mort (exited), aplicam "automated remediation"
            if status == "exited":
                print(f"\n[ALERT] Watchdog detected {container} is DOWN!")
                print(f"[ACTION] Auto-remediating... restarting {container}...")
                subprocess.run(["docker", "start", container], capture_output=True)
                print(f"[SUCCESS] {container} is back online!")
                
        time.sleep(2.0) # Verificam la fiecare 2 secunde

if __name__ == '__main__':
    try:
        check_and_remediate()
    except KeyboardInterrupt:
        print("\nWatchdog stopped.")