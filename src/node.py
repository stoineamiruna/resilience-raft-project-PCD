import os
import time
import threading
import requests
import random
import json
from flask import Flask, jsonify, request

app = Flask(__name__)

NODE_ID = os.environ.get('NODE_ID', 'unknown')
PORT = int(os.environ.get('PORT', 5000))
ALL_NODES = {'node1': 5001, 'node2': 5002, 'node3': 5003}
PEERS = {k: v for k, v in ALL_NODES.items() if k != NODE_ID}

# --- STAREA RAFT & DATE ---
state = 'FOLLOWER'
term = 0
voted_for = None
leader_id = None
store = {}  # Baza de date Key-Value locala

# --- PERSISTENTA DATE (Crash Recovery) ---
STORE_FILE = f"/tmp/raft_store_{NODE_ID}.json"

def load_store():
    global store
    if os.path.exists(STORE_FILE):
        try:
            with open(STORE_FILE, 'r') as f:
                store = json.load(f)
            print(f"[{NODE_ID}] Loaded {len(store)} keys from persistent storage.", flush=True)
        except Exception as e:
            print(f"[{NODE_ID}] Could not load store: {e}", flush=True)
            store = {}

def save_store():
    try:
        with open(STORE_FILE, 'w') as f:
            json.dump(store, f)
    except Exception as e:
        print(f"[{NODE_ID}] Could not save store: {e}", flush=True)

# --- MESSAGE OVERHEAD COUNTER ---
internal_message_count = 0
message_count_lock = threading.Lock()

ELECTION_TIMEOUT_MIN = 3.0
ELECTION_TIMEOUT_MAX = 6.0
HEARTBEAT_INTERVAL = 1.0

last_heartbeat_time = time.time()

def reset_election_timer():
    global last_heartbeat_time
    last_heartbeat_time = time.time()

def election_timer_thread():
    global state, term
    while True:
        time.sleep(0.5)
        if state != 'LEADER':
            timeout = random.uniform(ELECTION_TIMEOUT_MIN, ELECTION_TIMEOUT_MAX)
            if time.time() - last_heartbeat_time > timeout:
                start_election()

def start_election():
    global state, term, voted_for, leader_id
    state = 'CANDIDATE'
    term += 1
    voted_for = NODE_ID
    votes = [1]  # Se voteaza pe sine
    reset_election_timer()
    lock = threading.Lock()

    print(f"[{NODE_ID}] Triggered election for term {term}...", flush=True)

    def ask_peer(peer_id, peer_port, current_term):
        global state, leader_id
        try:
            url = f"http://{peer_id}:{peer_port}/request_vote"
            response = requests.post(url, json={'term': current_term, 'candidate_id': NODE_ID}, timeout=0.4)
            if response.status_code == 200 and response.json().get('vote_granted'):
                with lock:
                    votes.append(1)
                    # FIX: Verificam si modificam starea DOAR in interiorul Lock-ului
                    if state == 'CANDIDATE' and sum(votes) >= (len(ALL_NODES) // 2) + 1:
                        print(f"[{NODE_ID}] Won election! LEADER for term {current_term}.", flush=True)
                        state = 'LEADER'
                        leader_id = NODE_ID
                        threading.Thread(target=send_heartbeats_thread, daemon=True).start()
        except:
            pass

    for peer_id, peer_port in PEERS.items():
        threading.Thread(target=ask_peer, args=(peer_id, peer_port, term), daemon=True).start()

def send_heartbeats_thread():
    global state, term, store, leader_id
    
    def send_hb(peer_id, peer_port, current_term):
        global state, term, leader_id, internal_message_count
        try:
            url = f"http://{peer_id}:{peer_port}/append_entries"
            res = requests.post(url, json={'term': current_term, 'leader_id': NODE_ID, 'data': store}, timeout=0.3)
            
            with message_count_lock:
                internal_message_count += 1
                
            if res.status_code == 200:
                resp_data = res.json()
                resp_term = resp_data.get('term', 0)
                
                # CRITICAL FIX: Daca descoperim un nod cu un Term mai mare, 
                # inseamna ca suntem un lider invechit (stale) si facem imediat pasul in spate.
                if resp_term > current_term:
                    print(f"[{NODE_ID}] Discovered higher term {resp_term} in heartbeat response. Stepping down.", flush=True)
                    state = 'FOLLOWER'
                    term = resp_term
                    leader_id = None
        except: 
            pass

    while state == 'LEADER':
        # Trimitem heartbeats IN PARALEL catre toti
        for peer_id, peer_port in PEERS.items():
            threading.Thread(target=send_hb, args=(peer_id, peer_port, term), daemon=True).start()
        time.sleep(HEARTBEAT_INTERVAL)

# --- API ENDPOINTS (Raft Protocol) ---
@app.route('/request_vote', methods=['POST'])
def request_vote():
    global term, voted_for, state
    data = request.json
    candidate_term = data.get('term')
    candidate_id = data.get('candidate_id')

    vote_granted = False
    if candidate_term > term:
        term = candidate_term
        state = 'FOLLOWER'
        voted_for = candidate_id
        vote_granted = True
        reset_election_timer()
    elif candidate_term == term and (voted_for is None or voted_for == candidate_id):
        vote_granted = True
        voted_for = candidate_id
        reset_election_timer()

    return jsonify({'term': term, 'vote_granted': vote_granted})

@app.route('/append_entries', methods=['POST'])
def append_entries():
    global term, state, leader_id, store
    data = request.json
    leader_term = data.get('term')
    
    if leader_term >= term:
        term = leader_term
        state = 'FOLLOWER'
        leader_id = data.get('leader_id')
        if 'data' in data:
            store = data['data']
        reset_election_timer()
        return jsonify({'success': True, 'term': term})
        
    return jsonify({'success': False, 'term': term})

# --- API ENDPOINTS (Client Workload + ADVANCED REPLICATION QUORUM) ---
@app.route('/put', methods=['POST'])
def put_data():
    global store, state, term, internal_message_count
    if state != 'LEADER':
        return jsonify({'error': 'Not the leader', 'leader_id': leader_id}), 400
    
    key = request.json.get('key')
    value = request.json.get('value')
    
    # --- CONSENSUS/REPLICATION CHECK ---
    # Implementam replicarea sincrona cu Quorum obligatoriu (nota 10)
    replication_successes = [1] # Liderul a acceptat-o local deja
    lock = threading.Lock()
    threads = []

    def replicate_to_peer(peer_id, peer_port):
        global internal_message_count
        try:
            url = f"http://{peer_id}:{peer_port}/append_entries"
            # Trimitem datele partiale instant pentru replicare
            temp_store = store.copy()
            temp_store[key] = value
            res = requests.post(url, json={'term': term, 'leader_id': NODE_ID, 'data': temp_store}, timeout=0.4)
            
            with message_count_lock:
                internal_message_count += 1
                
            if res.status_code == 200 and res.json().get('success'):
                with lock:
                    replication_successes.append(1)
        except:
            pass

    for peer_id, peer_port in PEERS.items():
        t = threading.Thread(target=replicate_to_peer, args=(peer_id, peer_port))
        t.start()
        threads.append(t)

    # Asteptam ca thread-urile de replicare sa termine (maxim 400ms din timeout)
    for t in threads:
        t.join()

    # Verificam daca am obtinut majoritatea (Quorum)
    quorum_needed = (len(ALL_NODES) // 2) + 1
    if sum(replication_successes) >= quorum_needed:
        store[key] = value # Commit definitiv
        save_store()  # Persist to disk after quorum commit
        return jsonify({'success': True, 'msg': 'Data replicated to quorum', 'store_size': len(store)})
    else:
        return jsonify({'error': 'Write failed. Quorum could not be reached.'}), 500

@app.route('/get', methods=['GET'])
def get_data():
    key = request.args.get('key')
    return jsonify({'value': store.get(key)})

@app.route('/status', methods=['GET'])
def get_status():
    return jsonify({
        'node_id': NODE_ID, 
        'state': state, 
        'term': term, 
        'leader_id': leader_id, 
        'store_size': len(store),
        'internal_messages': internal_message_count
    })

if __name__ == '__main__':
    load_store()
    threading.Thread(target=election_timer_thread, daemon=True).start()
    app.run(host='0.0.0.0', port=PORT, threaded=True)