from flask import Flask, render_template, request, jsonify
import socket
import pickle
import threading
import queue
import os
import json

app = Flask(__name__)

# Global connection state
connection = {
    "socket": None,
    "running": False,
    "host": "192.168.1.9",
    "port": 12345,
    "status": "Disconnected",
    "received_messages": []
}

# Function to handle receiving data from the server
def handle_received_data(sock):
    while connection["running"]:
        try:
            data = pickle.loads(sock.recv(4096))
            print("Received:", data)
            if isinstance(data, dict) and data.get("type") == "speak":
                # Add to received messages
                connection["received_messages"].insert(0, data["text"])
                # Keep only the last 10 messages
                connection["received_messages"] = connection["received_messages"][:10]
        except Exception as e:
            if connection["running"]:
                print(f"Error receiving data: {e}")
                connection["status"] = f"Error: {e}"
            break
    
    # Clean up when thread ends
    if connection["socket"]:
        connection["socket"].close()
        connection["socket"] = None
    connection["running"] = False
    connection["status"] = "Disconnected"

# Routes
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/connect', methods=['POST'])
def connect():
    data = request.json
    connection["host"] = data.get("host", "192.168.1.9")
    connection["port"] = int(data.get("port", 12345))
    
    # Check if already connected
    if connection["running"]:
        return jsonify({"success": False, "message": "Already connected"})
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((connection["host"], connection["port"]))
        
        connection["socket"] = sock
        connection["running"] = True
        connection["status"] = f"Connected to {connection['host']}:{connection['port']}"
        
        # Start receiver thread
        receiver_thread = threading.Thread(target=handle_received_data, args=(sock,), daemon=True)
        receiver_thread.start()
        
        return jsonify({"success": True, "message": "Connected successfully"})
    except Exception as e:
        print(f"Connection failed: {e}")
        return jsonify({"success": False, "message": f"Connection failed: {e}"})

@app.route('/api/disconnect', methods=['POST'])
def disconnect():
    if connection["running"] and connection["socket"]:
        connection["running"] = False
        connection["socket"].close()
        connection["socket"] = None
        connection["status"] = "Disconnected"
        return jsonify({"success": True, "message": "Disconnected"})
    else:
        return jsonify({"success": False, "message": "Not connected"})

@app.route('/api/status', methods=['GET'])
def status():
    return jsonify({
        "connected": connection["running"],
        "status": connection["status"],
        "host": connection["host"],
        "port": connection["port"],
        "received_messages": connection["received_messages"]
    })

@app.route('/api/send', methods=['POST'])
def send_text():
    if not connection["running"] or not connection["socket"]:
        return jsonify({"success": False, "message": "Not connected"})
    
    data = request.json
    text = data.get("text", "")
    
    if not text:
        return jsonify({"success": False, "message": "No text provided"})
    
    try:
        connection["socket"].send(pickle.dumps(text))
        return jsonify({"success": True, "message": "Text sent"})
    except Exception as e:
        connection["running"] = False
        connection["status"] = f"Error: {e}"
        return jsonify({"success": False, "message": f"Failed to send: {e}"})

# Create templates directory and HTML file
os.makedirs('templates', exist_ok=True)
with open('templates/index.html', 'w') as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Audio Sender</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0-alpha1/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        .status-connected { color: green; }
        .status-disconnected { color: red; }
        .message-box {
            height: 200px;
            overflow-y: auto;
            border: 1px solid #ddd;
            border-radius: 5px;
            padding: 10px;
            margin-bottom: 10px;
        }
        .speech-controls {
            display: flex;
            gap: 10px;
            align-items: center;
        }
        #btnListen {
            background-color: #007bff;
            color: white;
            border: none;
            padding: 15px;
            border-radius: 50%;
            width: 60px;
            height: 60px;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        #btnListen.listening {
            background-color: #dc3545;
        }
        #recognizedText {
            flex-grow: 1;
            padding: 10px;
            border: 1px solid #ced4da;
            border-radius: 5px;
            min-height: 60px;
        }
    </style>
</head>
<body>
    <div class="container mt-4">
        <h1 class="mb-4">Audio Sender</h1>
        
        <!-- Connection Settings -->
        <div class="card mb-4">
            <div class="card-header">Connection Settings</div>
            <div class="card-body">
                <div class="mb-3 row">
                    <label for="serverIP" class="col-sm-2 col-form-label">Server IP</label>
                    <div class="col-sm-10">
                        <input type="text" class="form-control" id="serverIP" value="192.168.1.9">
                    </div>
                </div>
                <div class="mb-3 row">
                    <label for="serverPort" class="col-sm-2 col-form-label">Port</label>
                    <div class="col-sm-10">
                        <input type="number" class="form-control" id="serverPort" value="12345">
                    </div>
                </div>
                <div class="d-flex gap-2">
                    <button id="btnConnect" class="btn btn-success">Connect</button>
                    <button id="btnDisconnect" class="btn btn-danger" disabled>Disconnect</button>
                </div>
            </div>
        </div>
        
        <!-- Status -->
        <div class="alert" id="statusAlert" role="alert">
            Not connected
        </div>
        
        <!-- Speech Recognition -->
        <div class="card mb-4">
            <div class="card-header">Voice Input</div>
            <div class="card-body">
                <div class="speech-controls mb-3">
                    <button id="btnListen" disabled>
                        <i class="bi bi-mic-fill"></i>
                    </button>
                    <div id="recognizedText">Click microphone to speak</div>
                </div>
                <button id="btnSend" class="btn btn-primary" disabled>Send</button>
            </div>
        </div>
        
        <!-- Received Messages -->
        <div class="card">
            <div class="card-header">Received Messages</div>
            <div class="card-body">
                <div id="receivedMessages" class="message-box">
                    <p class="text-muted">No messages received yet</p>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Elements
        const btnConnect = document.getElementById('btnConnect');
        const btnDisconnect = document.getElementById('btnDisconnect');
        const btnListen = document.getElementById('btnListen');
        const btnSend = document.getElementById('btnSend');
        const serverIP = document.getElementById('serverIP');
        const serverPort = document.getElementById('serverPort');
        const statusAlert = document.getElementById('statusAlert');
        const recognizedText = document.getElementById('recognizedText');
        const receivedMessages = document.getElementById('receivedMessages');
        
        // State
        let isConnected = false;
        let isListening = false;
        let recognition = null;
        
        // Set up speech recognition
        function setupSpeechRecognition() {
            if ('webkitSpeechRecognition' in window) {
                recognition = new webkitSpeechRecognition();
                recognition.continuous = false;
                recognition.interimResults = true;
                
                recognition.onstart = function() {
                    isListening = true;
                    btnListen.classList.add('listening');
                    btnListen.innerHTML = '<i class="bi bi-stop-fill"></i>';
                    recognizedText.textContent = "Listening...";
                };
                
                recognition.onresult = function(event) {
                    const transcript = Array.from(event.results)
                        .map(result => result[0].transcript)
                        .join('');
                    recognizedText.textContent = transcript;
                    
                    if (event.results[0].isFinal) {
                        btnSend.disabled = false;
                    }
                };
                
                recognition.onend = function() {
                    isListening = false;
                    btnListen.classList.remove('listening');
                    btnListen.innerHTML = '<i class="bi bi-mic-fill"></i>';
                };
                
                recognition.onerror = function(event) {
                    console.error('Speech recognition error', event.error);
                    isListening = false;
                    btnListen.classList.remove('listening');
                    btnListen.innerHTML = '<i class="bi bi-mic-fill"></i>';
                    recognizedText.textContent = "Error: " + event.error;
                };
                
                return true;
            } else {
                alert("Speech recognition is not supported in this browser.");
                return false;
            }
        }
        
        // Connect to server
        btnConnect.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/connect', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        host: serverIP.value,
                        port: serverPort.value
                    })
                });
                
                const data = await response.json();
                
                if (data.success) {
                    isConnected = true;
                    updateUI();
                    startStatusPolling();
                } else {
                    statusAlert.className = 'alert alert-danger';
                    statusAlert.textContent = data.message;
                }
            } catch (error) {
                console.error('Connection error:', error);
                statusAlert.className = 'alert alert-danger';
                statusAlert.textContent = 'Connection error: ' + error.message;
            }
        });
        
        // Disconnect from server
        btnDisconnect.addEventListener('click', async () => {
            try {
                const response = await fetch('/api/disconnect', {
                    method: 'POST'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    isConnected = false;
                    updateUI();
                }
            } catch (error) {
                console.error('Disconnect error:', error);
            }
        });
        
        // Toggle listening
        btnListen.addEventListener('click', () => {
            if (!isListening) {
                recognition.start();
            } else {
                recognition.stop();
            }
        });
        
        // Send recognized text
        btnSend.addEventListener('click', async () => {
            const text = recognizedText.textContent;
            
            if (text && text !== 'Listening...' && text !== 'Click microphone to speak') {
                try {
                    const response = await fetch('/api/send', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({
                            text: text
                        })
                    });
                    
                    const data = await response.json();
                    
                    if (data.success) {
                        recognizedText.textContent = 'Click microphone to speak';
                        btnSend.disabled = true;
                    } else {
                        statusAlert.className = 'alert alert-danger';
                        statusAlert.textContent = data.message;
                    }
                } catch (error) {
                    console.error('Send error:', error);
                }
            }
        });
        
        // Update UI based on connection state
        function updateUI() {
            btnConnect.disabled = isConnected;
            btnDisconnect.disabled = !isConnected;
            btnListen.disabled = !isConnected;
            btnSend.disabled = !isConnected || recognizedText.textContent === 'Listening...' || recognizedText.textContent === 'Click microphone to speak';
            
            if (isConnected) {
                statusAlert.className = 'alert alert-success';
                serverIP.disabled = true;
                serverPort.disabled = true;
            } else {
                statusAlert.className = 'alert alert-warning';
                serverIP.disabled = false;
                serverPort.disabled = false;
                recognizedText.textContent = 'Click microphone to speak';
            }
        }
        
        // Poll for status updates
        function startStatusPolling() {
            const poll = async () => {
                if (!isConnected) return;
                
                try {
                    const response = await fetch('/api/status');
                    const data = await response.json();
                    
                    isConnected = data.connected;
                    statusAlert.textContent = data.status;
                    
                    if (data.received_messages.length > 0) {
                        receivedMessages.innerHTML = data.received_messages
                            .map(msg => `<p>${msg}</p>`)
                            .join('');
                    }
                    
                    updateUI();
                    
                    if (isConnected) {
                        setTimeout(poll, 1000);
                    }
                } catch (error) {
                    console.error('Status polling error:', error);
                    setTimeout(poll, 3000);
                }
            };
            
            poll();
        }
        
        // Initialize
        document.addEventListener('DOMContentLoaded', () => {
            if (setupSpeechRecognition()) {
                updateUI();
            } else {
                btnListen.disabled = true;
                btnListen.title = "Speech recognition not supported";
            }
        });
    </script>

    <!-- Bootstrap Icons -->
    <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/bootstrap-icons@1.10.0/font/bootstrap-icons.css">
</body>
</html>
    ''')

if __name__ == '__main__':
    # Use environment variables for host/port when running on Render
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
