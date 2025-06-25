from flask import Flask, render_template_string
from flask_socketio import SocketIO, emit
import base64
from PIL import Image
import io
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = 'your-secret-key-here'
socketio = SocketIO(app, cors_allowed_origins="*")

# Store the latest frame
latest_frame = None

# HTML template
HTML_TEMPLATE = '''
<!DOCTYPE html>
<html>
<head>
    <title>1 FPS Screen Stream</title>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: Arial, sans-serif;
            background: #000;
            color: #fff;
            text-align: center;
        }
        #screen {
            max-width: 100%;
            max-height: 80vh;
            border: 2px solid #333;
            margin: 20px auto;
            display: block;
        }
        .status {
            margin: 10px;
            padding: 10px;
            background: #333;
            border-radius: 5px;
        }
        .connected { color: #0f0; }
        .disconnected { color: #f00; }
    </style>
</head>
<body>
    <h1>1 FPS Screen Stream</h1>
    <div id="status" class="status disconnected">Waiting for connection...</div>
    <img id="screen" src="data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNkYPhfDwAChwGA60e6kgAAAABJRU5ErkJggg==" alt="No stream">
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        const screenImg = document.getElementById('screen');
        const status = document.getElementById('status');
        
        socket.on('connect', function() {
            status.textContent = 'Connected - Waiting for stream...';
            status.className = 'status connected';
        });
        
        socket.on('disconnect', function() {
            status.textContent = 'Disconnected';
            status.className = 'status disconnected';
        });
        
        socket.on('screen_data', function(data) {
            try {
                // Convert raw data to image
                const canvas = document.createElement('canvas');
                const ctx = canvas.getContext('2d');
                
                canvas.width = data.width;
                canvas.height = data.height;
                
                const imageData = ctx.createImageData(data.width, data.height);
                const rawData = new Uint8Array(atob(data.pixels).split('').map(char => char.charCodeAt(0)));
                
                for (let i = 0; i < rawData.length; i += 3) {
                    const pixelIndex = (i / 3) * 4;
                    imageData.data[pixelIndex] = rawData[i];     // R
                    imageData.data[pixelIndex + 1] = rawData[i + 1]; // G
                    imageData.data[pixelIndex + 2] = rawData[i + 2]; // B
                    imageData.data[pixelIndex + 3] = 255;        // A
                }
                
                ctx.putImageData(imageData, 0, 0);
                screenImg.src = canvas.toDataURL();
                
                status.textContent = `Streaming - ${data.width}x${data.height}`;
                status.className = 'status connected';
            } catch (error) {
                console.error('Error processing frame:', error);
            }
        });
        
        socket.on('frame_update', function(data) {
            screenImg.src = 'data:image/png;base64,' + data.image;
            status.textContent = `Streaming - ${data.width}x${data.height}`;
            status.className = 'status connected';
        });
    </script>
</body>
</html>
'''

@app.route('/')
def index():
    return render_template_string(HTML_TEMPLATE)

@socketio.on('connect')
def handle_connect():
    print('Client connected')
    emit('status', {'message': 'Connected to server'})

@socketio.on('disconnect')
def handle_disconnect():
    print('Client disconnected')

@socketio.on('screen_frame')
def handle_screen_frame(data):
    """Handle incoming screen frame data from PC client"""
    try:
        # Convert raw RGB data to PNG image
        width = data['width']
        height = data['height']
        raw_data = base64.b64decode(data['pixels'])
        
        # Create PIL Image from raw RGB data
        img = Image.frombytes('RGB', (width, height), raw_data)
        
        # Convert to PNG and encode as base64
        img_buffer = io.BytesIO()
        img.save(img_buffer, format='PNG')
        img_base64 = base64.b64encode(img_buffer.getvalue()).decode()
        
        # Broadcast to all connected web clients
        socketio.emit('frame_update', {
            'image': img_base64,
            'width': width,
            'height': height
        })
        
        print(f"Frame processed: {width}x{height}")
        
    except Exception as e:
        print(f"Error processing frame: {e}")

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
