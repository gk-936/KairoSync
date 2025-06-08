// main.js
const { app, BrowserWindow } = require('electron');
const path = require('path');
const { spawn } = require('child_process');

let pythonProcess = null;
let mainWindow; // Declaring mainWindow globally

function startPythonBackend() {
    // IMPORTANT: Adjust the path to your Python executable and app.py
    // This assumes 'python' is in your PATH and app.py is in the same directory.
    // If your venv Python is not in PATH, use its full path:
    // e.g., path.join(__dirname, 'venv', 'Scripts', 'python.exe')
    pythonProcess = spawn(path.join(__dirname, 'venv', 'Scripts', 'python.exe'), [path.join(__dirname, 'app.py')]);

    pythonProcess.stdout.on('data', (data) => {
        console.log(`Python Backend: ${data}`);
    });

    pythonProcess.stderr.on('data', (data) => {
        console.error(`Python Backend Error: ${data}`);
    });

    pythonProcess.on('close', (code) => {
        console.log(`Python backend process exited with code ${code}`);
        pythonProcess = null; // Clear the reference
    });
}

function createWindow() {
    mainWindow = new BrowserWindow({ // Assigning to the global mainWindow
        width: 1000, // Adjust width as needed for your Stark Industries theme
        height: 700, // Adjust height as needed
        minWidth: 800, // Recommended: Set minimum width
        minHeight: 600, // Recommended: Set minimum height
        frame: true, // <--- THIS IS THE KEY CHANGE: Set to true for native frame/resizing/fullscreen
        transparent: false, // Setting to false because transparent windows usually require frame: false
                           // If you want transparency with a frame, you'll need OS-specific settings.
                           // For now, let's keep it simple to get resizing working.
        webPreferences: {
            preload: path.join(__dirname, 'preload.js'), // For secure communication
            nodeIntegration: false, // Keep nodeIntegration false for security
            contextIsolation: true // Keep contextIsolation true for security
        },
        resizable: true,     // Explicitly ensure resizable is true
        fullscreenable: true, // Explicitly ensure fullscreenable is true
        maximizable: true,   // Explicitly ensure maximizable is true
    });

    mainWindow.loadFile('index.html'); // Load your HTML UI

    // Open the DevTools.
    // mainWindow.webContents.openDevTools(); // Uncomment this line if you need DevTools
}

// This method will be called when Electron has finished
// initialization and is ready to create browser windows.
// Some APIs can only be used after this event occurs.
app.whenReady().then(() => {
    startPythonBackend(); // Start the Flask backend when Electron is ready
    createWindow();

    app.on('activate', () => {
        // On macOS it's common to re-create a window in the app when the
        // dock icon is clicked and there are no other windows open.
        if (BrowserWindow.getAllWindows().length === 0) {
            createWindow();
        }
    });
});

// Quit when all windows are closed, except on macOS. There, it's common
// for applications and their menu bar to stay active until the user quits
// explicitly with Cmd + Q.
app.on('window-all-closed', () => {
    if (process.platform !== 'darwin') {
        app.quit();
    }
});

// Ensure Python backend is killed when Electron app quits
app.on('before-quit', (event) => {
    if (pythonProcess) {
        console.log("Terminating Python backend process...");
        pythonProcess.kill();
        pythonProcess = null;
    }
});