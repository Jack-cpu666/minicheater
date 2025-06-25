import os
from flask import Flask, render_template_string
from flask_socketio import SocketIO

# --- Flask App Setup ---
app = Flask(__name__)
# It's good practice to have a secret key, though not strictly necessary for this simple app.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'a_very_secret_key') 
socketio = SocketIO(app, async_mode='eventlet')

# This will store the latest frame data in memory
latest_frame = {
    'data': None,
    'width': 0,
    'height': 0
}

# --- HTML & JavaScript Template ---
# All the frontend code is embedded here for simplicity.
INDEX_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>1 FPS Raw Stream</title>
    <style>
        body { font-family: sans-serif; background-color: #222; color: #eee; text-align: center; margin-top: 20px; }
        h1 { color: #00aaff; }
        #status { margin: 10px; font-style: italic; color: #999; }
        canvas { background-color: #000; border: 2px solid #555; }
    </style>
</head>
<body>
    <h1>1 FPS Raw Data Stream</h1>
    <p id="status">Connecting to server...</p>
    <canvas id="video-canvas"></canvas>

    <!-- We need the Socket.IO client library -->
    <script src="https://cdn.socket.io/4.7.2/socket.io.min.js"></script>
    <script>
        document.addEventListener('DOMContentLoaded', (event) => {
            const canvas = document.getElementById('video-canvas');
            const ctx = canvas.getContext('2d');
            const status = document.getElementById('status');

            // Connect to the same server that served this page
            const socket = io();

            socket.on('connect', () => {
                status.textContent = 'Connected! Waiting for stream to start...';
                console.log('Connected to server.');
            });

            socket.on('disconnect', () => {
                status.textContent = 'Disconnected from server.';
                console.log('Disconnected.');
            });
            
            // This is the main event listener that receives new frames
            socket.on('new_frame', (frame) => {
                if (!frame || !frame.data) return;

                status.textContent = `Streaming... (Frame dimensions: ${frame.width}x${frame.height})`;
                
                // Set canvas dimensions if they've changed
                if (canvas.width !== frame.width || canvas.height !== frame.height) {
                    canvas.width = frame.width;
                    canvas.height = frame.height;
                }

                // The raw data from MSS is often BGRA. HTML Canvas needs RGBA.
                // We must swap the Red and Blue channels.
                const imageData = ctx.createImageData(frame.width, frame.height);
                const receivedData = new Uint8ClampedArray(frame.data);

                for (let i = 0; i < receivedData.length; i += 4) {
                    imageData.data[i] = receivedData[i+2];     // Red
                    imageData.data[i+1] = receivedData[i+1];   // Green
                    imageData.data[i+2] = receivedData[i];     // Blue
                    imageData.data[i+3] = receivedData[i+3];   // Alpha
                }
                
                // Draw the image data to the canvas
                ctx.putImageData(imageData, 0, 0);
            });
        });
    </script>
</body>
</html>
"""

# --- Server Routes and SocketIO Events ---

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template_string(INDEX_HTML)

@socketio.on('connect')
def handle_connect():
    """A new web browser client connected."""
    print('Web client connected')
    # If a stream is already running, send the last frame immediately
    if latest_frame['data']:
        socketio.emit('new_frame', latest_frame)

@socketio.on('stream_frame')
def handle_stream_frame(frame_data):
    """
    This event is called by our pcapp.py script.
    It receives the raw frame data and broadcasts it to all web clients.
    """
    # Update the latest frame in memory
    global latest_frame
    latest_frame = frame_data
    
    # Broadcast the new frame to all connected web clients
    socketio.emit('new_frame', frame_data)

@socketio.on('disconnect')
def handle_disconnect():
    print('A client disconnected')

# This part is for local testing, Render.com will use Gunicorn
if __name__ == '__main__':
    print("Starting local server at http://127.0.0.1:5000")
    socketio.run(app, debug=True)
