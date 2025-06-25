# app.py
from flask import Flask
from flask_socketio import SocketIO

# We embed the viewer's HTML directly into our Python script.
# This avoids the need for a separate 'templates' folder.
HTML_CONTENT = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Live Screen Stream</title>
    <style>
        body {
            margin: 0;
            padding: 0;
            background-color: #111;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            color: #ccc;
            font-family: sans-serif;
        }
        #screen {
            max-width: 100%;
            max-height: 100vh;
            border: 2px solid #333;
        }
        #status {
            position: absolute;
            top: 20px;
            left: 50%;
            transform: translateX(-50%);
            background-color: rgba(0,0,0,0.5);
            padding: 10px 20px;
            border-radius: 5px;
        }
    </style>
    <!-- We need the Socket.IO client library from a CDN -->
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
</head>
<body>
    <div id="status">Connecting to stream...</div>
    <img id="screen" src="" alt="Live stream will appear here.">

    <script>
        // Connect to the Socket.IO server
        const socket = io();
        const imageElement = document.getElementById('screen');
        const statusElement = document.getElementById('status');
        let lastUrl; // To keep track of the previous image URL

        socket.on('connect', () => {
            statusElement.textContent = 'Connected! Waiting for stream...';
            console.log('Connected to server!');
        });

        // Listen for the 'image' event from the server
        socket.on('image', (data) => {
            // Data is raw image bytes (JPEG). Create a Blob.
            const blob = new Blob([data], { type: 'image/jpeg' });
            const url = URL.createObjectURL(blob);
            imageElement.src = url;
            statusElement.style.display = 'none';

            // Clean up the old URL to prevent memory leaks
            imageElement.onload = () => {
                if (lastUrl) {
                    URL.revokeObjectURL(lastUrl);
                }
                lastUrl = url;
            };
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
# 'eventlet' is crucial for production performance on Render
socketio = SocketIO(app, async_mode='eventlet')

# Main route that serves the HTML page
@app.route('/')
def index():
    """Serves the viewing page from the string variable."""
    return HTML_CONTENT

# Listens for stream data from your PC
@socketio.on('stream')
def handle_stream(data):
    """Receives a frame from the PC and broadcasts it to all viewers."""
    socketio.emit('image', data, broadcast=True, include_self=False)

@socketio.on('connect')
def handle_connect():
    print('Client connected')

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

# This part is not used by Render's Gunicorn, but it's good for local testing
if __name__ == '__main__':
    socketio.run(app, debug=True)
