import { WebSocketServer } from "ws";
import https from 'https';
import fs from 'fs';
import readline from 'readline';

const WS_PORT = 4444

// SSL/TLS configuration from WSS
const privateKey = fs.readFileSync('server.key', 'utf8');
const certificate = fs.readFileSync('server.crt', 'utf8');
const credentials =  { key:  privateKey, cert: certificate };

// Create HTTPS Server
const httpsServer =  https.createServer(credentials, (req, res) => {
    res.writeHead(200, { 'Content-Type': 'text/plain' })
    res.end('WebSocket server is running over HTTPS \n ')
})

// Pass the https server to WebSocket
const wss  = new WebSocketServer({ server: httpsServer})

httpsServer.listen(WS_PORT, () => {
    console.log(`HTTPS server (for WSS) started on port ${WS_PORT}`);
    startCli(); // Start the CLI after the server is listening
});
console.log('Server is ready to accept WSS connections.');

// Map to store connected clients by their Device ID
const connectedClients = new Map();

wss.on('connection', ws => {
    console.log('\n--- Client connected (WSS) ---');
    ws.deviceId = 'unregistered'; // Initialize deviceId for the new connection

    // Send a welcome message immediately on connection.
    // This is distinct from the registration confirmation.
    ws.send(JSON.stringify({ type: 'welcome', message: 'Welcome to the Android Control WebSocket Server!' }));
    displayCliPrompt();

    ws.on('message', message => {
        const messageString = message.toString();
        console.log(`\nReceived message from client (${ws.deviceId}): ${messageString}`);

        try {
            const data = JSON.parse(messageString);

            // --- IMPORTANT: Prioritize message type handling ---
            // Handle 'register' first
            if (data.type === 'register' && data.deviceId) {
                if (connectedClients.has(data.deviceId)) {
                    console.warn(`Device ID ${data.deviceId} already registered. Overwriting connection.`);
                    // Optionally, send an error if overwriting is not allowed.
                }
                ws.deviceId = data.deviceId;
                connectedClients.set(data.deviceId, ws);
                console.log(`Device registered: ${ws.deviceId}`);
                // Send confirmation of registration
                ws.send(JSON.stringify({ type: 'registered', message: `Server recognized you as ${ws.deviceId}` }));
                displayCliPrompt();
                return; // IMPORTANT: Exit here after handling 'register'
            }
            
            // Handle 'response' messages from the client (e.g., command results, client errors)
            if (data.type === 'response') {
                console.log(`\n--- Response from ${ws.deviceId} for command ${data.commandId || 'unknown'} ---`);
                console.log(`Status: ${data.status || 'N/A'}`);
                console.log(`Message: ${data.message || 'No message'}`);
                if (data.data) {
                    console.log(`Data: ${JSON.stringify(data.data, null, 2)}`);
                }
                console.log('------------------------------------------');
                displayCliPrompt();
                return; // IMPORTANT: Exit here after handling 'response'
            }

            // If not 'register' or 'response', ensure client is registered for other commands
            if (ws.deviceId === 'unregistered') {
                console.warn('Received message from unregistered client. Ignoring:', data);
                ws.send(JSON.stringify({ type: 'error', message: 'Please register your device ID first to send commands.' }));
                displayCliPrompt();
                return; // IMPORTANT: Exit if unregistered and not a registration attempt
            }
            
            // Handle 'command' messages from the client (if your client sends commands)
            // Currently, your Android client sends 'register' and 'response' only.
            // If the client sends its own commands (e.g., 'heartbeat', 'status_update'), handle them here.
            if (data.type === 'command') {
                console.log(`Processing command from ${ws.deviceId}:`, data);
                if (data.action === 'get_info') { // Example of a client-initiated command
                    ws.send(JSON.stringify({ type: 'response', commandId: data.commandId, status: 'success', data: { serverTime: Date.now() }, message: 'Info provided' }));
                } else {
                    ws.send(JSON.stringify({ type: 'error', message: `Unknown command action: '${data.action}'.`, commandId: data.commandId || 'unknown' }));
                }
                displayCliPrompt();
                return; // IMPORTANT: Exit after handling a client-initiated command
            }

            // Fallback for any other unknown or unhandled message types from the client
            ws.send(JSON.stringify({ type: 'error', message: `Server received an unknown message type: '${data.type || 'N/A'}'.` }));
            console.warn(`Server sent 'Unknown message type' for: ${messageString}`);
            displayCliPrompt();

        } catch (e) {
            console.error(`Error parsing or processing message from client (${ws.deviceId}):`, e.message);
            ws.send(JSON.stringify({ type: 'error', message: `Invalid JSON or server error: ${e.message}`, commandId: 'unknown' }));
            displayCliPrompt();
        }
    });

    ws.on('close', () => {
        if (ws.deviceId && ws.deviceId !== 'unregistered') {
            connectedClients.delete(ws.deviceId);
            console.log(`\nClient disconnected: ${ws.deviceId}`);
        } else {
            console.log('\nUnregistered client disconnected.');
        }
        displayCliPrompt();
    });

    ws.on('error', error => {
        console.error(`\nWebSocket error for client (${ws.deviceId}):`, error);
        displayCliPrompt();
    });
});

wss.on('error', error => {
    console.error('WebSocket server error:', error);
    displayCliPrompt();
});


// --- CLI Implementation (unchanged, but added comments for context) ---
let rl;

function startCli() {
    rl = readline.createInterface({
        input: process.stdin,
        output: process.stdout,
        prompt: 'CMD > '
    });

    console.log('\n--- CLI Commands ---');
    console.log('  list           - List connected device IDs');
    console.log('  send <id> wifi - Request Wi-Fi status from a device');
    console.log('  exit           - Shut down the server');
    console.log('--------------------');

    displayCliPrompt();

    rl.on('line', (line) => {
        const input = line.trim().toLowerCase();
        const parts = input.split(' ');
        const command = parts[0];

        switch (command) {
            case 'list':
                if (connectedClients.size === 0) {
                    console.log('No devices connected.');
                } else {
                    console.log('Connected Devices:');
                    connectedClients.forEach((ws, id) => {
                        console.log(`  - ${id}`);
                    });
                }
                break;

            case 'send':
                const deviceId = parts[1];
                const action = parts[2];
                
                if (!deviceId) {
                    console.error('Error: Please specify a device ID. Usage: send <id> <command>');
                    break;
                }
                if (!action) {
                    console.error('Error: Please specify a command action (e.g., wifi). Usage: send <id> <command>');
                    break;
                }

                const targetWs = connectedClients.get(deviceId);
                if (!targetWs) {
                    console.error(`Error: Device ID '${deviceId}' not found.`);
                } else {
                    if (action === 'wifi') {
                        const commandId = Date.now().toString(); // Simple unique ID
                        const message = {
                            type: 'command', // Server-initiated commands are 'command' type
                            action: 'get_wifi_status', // The specific action
                            commandId: commandId
                        };
                        try {
                            targetWs.send(JSON.stringify(message));
                            console.log(`Sent 'get_wifi_status' command to ${deviceId}. (Command ID: ${commandId})`);
                        } catch (e) {
                            console.error(`Failed to send command to ${deviceId}:`, e.message);
                        }
                    } else {
                        console.error(`Error: Unknown command action '${action}'. Try 'wifi'.`);
                    }
                }
                break;

            case 'exit':
                console.log('Shutting down server...');
                wss.close();
                httpsServer.close(() => {
                    rl.close();
                    process.exit(0);
                });
                return;
            
            default:
                console.log(`Unknown command: '${input}'. Type 'list' or 'help' for available commands.`);
                break;
        }
        displayCliPrompt();
    });

    rl.on('close', () => {
        console.log('CLI terminated.');
        process.exit(0);
    });
}

function displayCliPrompt() {
    rl.prompt(true);
}