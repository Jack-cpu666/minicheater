# app.py
import uvicorn
from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncio
import base64 # We'll send binary data directly, base64 is not needed here
import logging

# Basic logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI()

# Store the latest frame received from the streamer
latest_frame_data: bytes | None = None

# Keep track of active viewer WebSocket connections
viewer_websockets: list[WebSocket] = []

# --- WebSocket Endpoint for the PC Streamer ---
@app.websocket("/ws/stream")
async def websocket_endpoint_streamer(websocket: WebSocket):
    global latest_frame_data
    await websocket.accept()
    logger.info("Streamer WebSocket connection accepted.")
    try:
        while True:
            # Receive binary data (the JPEG frame) from the PC client
            data = await websocket.receive_bytes()
            if data:
                latest_frame_data = data
                # Broadcast the new frame to all connected viewers
                await broadcast_frame_to_viewers(latest_frame_data)
            else:
                logger.warning("Received empty data from streamer.")

    except Exception as e:
        logger.error(f"Streamer WebSocket error: {e}")
    finally:
        logger.info("Streamer WebSocket connection closed.")
        # No need to remove from a list, as there's only one streamer

# --- WebSocket Endpoint for Browser Viewers ---
@app.websocket("/ws/viewer")
async def websocket_endpoint_viewer(websocket: WebSocket):
    await websocket.accept()
    viewer_websockets.append(websocket)
    logger.info(f"Viewer WebSocket connection accepted. Total viewers: {len(viewer_websockets)}")

    try:
        # Send the latest frame immediately upon connection if available
        if latest_frame_data:
            try:
                await websocket.send_bytes(latest_frame_data)
            except Exception as e:
                logger.warning(f"Failed to send initial frame to new viewer: {e}")
                # If sending fails, assume disconnect and let the loop handle it

        # Keep the connection open. The server pushes data TO the viewer,
        # so this loop just waits for the viewer to send something (or disconnect).
        # We can ignore messages from the viewer for this simple app.
        while True:
            # Just keep the connection alive. Receiving any message keeps it active.
            # Or you could receive_text(), receive_bytes(), or receive_json()
            # depending on if the client sends anything. For a viewer just receiving,
            # this loop primarily exists to catch the disconnect exception.
            await websocket.receive_text() # Or pass if viewer sends nothing? Let's receive to be safe.

    except Exception as e:
         # Catching generic Exception to handle WebSocketDisconnect and others
        # WebSocketDisconnect is raised when the client closes the connection
        # Other exceptions might indicate network issues
        if not isinstance(e, asyncio.CancelledError): # Avoid logging cancellation during shutdown
             logger.error(f"Viewer WebSocket error or disconnect: {e}")

    finally:
        # Clean up the connection
        if websocket in viewer_websockets:
            viewer_websockets.remove(websocket)
        logger.info(f"Viewer WebSocket connection closed. Remaining viewers: {len(viewer_websockets)}")

# --- Helper function to broadcast the frame ---
async def broadcast_frame_to_viewers(frame_data: bytes):
    # Use a copy of the list in case it's modified while iterating
    disconnected_viewers = []
    for websocket in list(viewer_websockets):
        try:
            await websocket.send_bytes(frame_data)
        except Exception as e:
            # If sending fails, the connection is likely closed or broken
            logger.warning(f"Failed to send frame to a viewer ({e}). Marking for removal.")
            disconnected_viewers.append(websocket)

    # Remove disconnected viewers after iterating
    for websocket in disconnected_viewers:
        if websocket in viewer_websockets:
            viewer_websockets.remove(websocket)
            logger.info(f"Removed disconnected viewer. Remaining: {len(viewer_websockets)}")

# --- HTML Page for Viewing ---
@app.get("/", response_class=HTMLResponse)
async def get_viewer_page(request: Request):
    # Use request.url to dynamically get the host (http/https and hostname)
    # and then construct the websocket URL (ws/wss)
    # For Render, this will typically be HTTPS, so wss.
    # If running locally with uvicorn http://localhost:8000, it will be ws.

    scheme = "wss" if request.url.scheme == "https" else "ws"
    websocket_url = f"{scheme}://{request.url.hostname}{f':{request.url.port}' if request.url.port else ''}/ws/viewer"

    html_content = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <title>Screen Viewer</title>
        <style>
            /* Corrected curly braces for f-string */
            body {{ margin: 0; overflow: hidden; background-color: #000; display: flex; justify-content: center; align-items: center; height: 100vh; }}
            #screenImage {{ max-width: 100%; max-height: 100%; object-fit: contain; }} /* Ensure image fits within view */
            #status {{ color: white; position: absolute; top: 10px; left: 10px; background: rgba(0,0,0,0.5); padding: 5px; border-radius: 3px; font-family: sans-serif; font-size: 12px; }}
        </style>
    </head>
    <body>
        <img id="screenImage" src="" alt="Loading screen stream..." />
        <div id="status">Status: Connecting...</div>

        <script>
            const imageElement = document.getElementById('screenImage');
            const statusElement = document.getElementById('status');
            const websocketUrl = "{websocket_url}"; // Dynamically set WebSocket URL

            let ws = null;
            let frameCount = 0;
            let startTime = Date.now();
            let lastObjectUrl = null; // To keep track of URLs to revoke

            function connectWebSocket() {{
                if (ws && (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING)) {{
                    console.log("WebSocket already open or connecting.");
                    return;
                }}

                statusElement.textContent = 'Status: Connecting...';
                console.log(`Attempting to connect to WebSocket: ${{websocketUrl}}`); // Already correctly escaped

                ws = new WebSocket(websocketUrl);

                ws.onopen = function(event) {{ // Already correctly escaped
                    console.log('WebSocket connected');
                    statusElement.textContent = 'Status: Connected';
                    frameCount = 0;
                    startTime = Date.now();
                }};

                ws.onmessage = function(event) {{ // Already correctly escaped
                    // event.data will be a Blob for binary messages
                    if (event.data instanceof Blob) {{ // Already correctly escaped
                        frameCount++;
                        const elapsed = (Date.now() - startTime) / 1000;
                        const fps = elapsed > 0 ? frameCount / elapsed : 0;
                        statusElement.textContent = `Status: Streaming | FPS: ${{fps.toFixed(1)}}`; // Already correctly escaped

                        // Revoke the previous object URL to free memory
                        if (lastObjectUrl) {{ // Already correctly escaped
                            URL.revokeObjectURL(lastObjectUrl);
                        }}

                        // Create a URL for the Blob and set it as the image source
                        const imageUrl = URL.createObjectURL(event.data);
                        imageElement.src = imageUrl;
                        lastObjectUrl = imageUrl; // Store the new URL
                    }} else {{ // Already correctly escaped
                        console.warn("Received non-blob data:", event.data);
                    }}
                }};

                ws.onerror = function(event) {{ // Already correctly escaped
                    console.error('WebSocket error observed:', event);
                    statusElement.textContent = 'Status: Error';
                }};

                ws.onclose = function(event) {{ // Already correctly escaped
                    console.log('WebSocket connection closed:', event);
                    statusElement.src = ""; // Clear the image
                    statusElement.textContent = 'Status: Disconnected';

                    // Attempt to reconnect after a delay
                    setTimeout(connectWebSocket, 5000); // Try reconnecting every 5 seconds
                }};
            }

            // Initial connection attempt
            connectWebSocket();

             // Clean up object URLs on page unload
            window.addEventListener('beforeunload', function() {{ // Already correctly escaped
                if (lastObjectUrl) {{ // Already correctly escaped
                    URL.revokeObjectURL(lastObjectUrl);
                }}
                 if (ws) {{ // Already correctly escaped
                    ws.close();
                }}
            }});


        </script>
    </body>
    </html>
    """
    return HTMLResponse(content=html_content)

# Optional: Add a health check endpoint for Render
@app.get("/health")
async def health_check():
    return {"status": "ok"}

if __name__ == "__main__":
    # This part is for local testing only. Render runs your app using uvicorn command.
    uvicorn.run(app, host="0.0.0.0", port=8000)
