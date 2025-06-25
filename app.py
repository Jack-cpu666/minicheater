# app.py

# --- FIX 1: MONKEY PATCHING ---
# This MUST be at the very top, before any other imports like Flask.
import eventlet
eventlet.monkey_patch()
# -----------------------------

from flask import Flask
from flask_socketio import SocketIO

# We embed the viewer's HTML directly into our Python script.
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Screen Stream</title>
    <style>
        body { margin: 0; padding: 0; background-color: #111; display: flex; justify-content: center; align-items: center; height: 100vh; color: #ccc; font-family: sans-serif; }
        #screen { max-width: 100%; max-height: 100vh; border: 2px solid #333; }
        #status { position: absolute; top: 20px; left: 50%; transform: translateX(-50%); background-color: rgba(0,0,0,0.5); padding: 10px 20px; border-radius: 5px; }
    </style>
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
</head>
<body>
    <div id="status">Connecting to stream...</div>
    <img id="screen" src="" alt="Live stream will appear here.">
    <script>
        const socket = io();
        const imageElement = document.getElementById('screen');
        const statusElement = document.getElementById('status');
        let lastUrl;
        socket.on('connect', () => {
            statusElement.textContent = 'Connected! Waiting for stream...';
            console.log('Connected to server!');
        });
        socket.on('image', (data) => {
            const blob = new Blob([data], { type: 'image/jpeg' });
            const url = URL.createObjectURL(blob);
            imageElement.src = url;
            statusElement.style.display = 'none';
            imageElement.onload = () => { if (lastUrl) { URL.revokeObjectURL(lastUrl); } lastUrl = url; };
        });
        socket.on('disconnect', () => {
            statusElement.style.display = 'block';
            statusElement.textContent = 'Stream disconnected. Attempting to reconnect...';
            console.log('Disconnected from server.');
        });
    </script>
</body>
</html>
"""

# Initialize Flask and SocketIO
app = Flask(__name__)
socketio = SocketIO(app, async_mode='eventlet')

@app.route('/')
def index():
    """Serves the viewing page."""
    return HTML_CONTENT

@socketio.on('stream')
def handle_stream(data):
    """Receives a frame from the PC and broadcasts it to all viewers."""
    # This line is now guaranteed to work with the version-pinned libraries.
    socketio.emit('image', data, broadcast=True, include_self=False)

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

if __name__ == '__main__':
    socketio.run(app, debug=True)
