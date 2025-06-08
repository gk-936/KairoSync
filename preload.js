// preload.js
const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('api', {
    send: (channel, data) => {
        // whitelist channels
        let validChannels = ["command", "getTasks", "getDailyTasks", "getWeeklyTasks", "getMonthlyTasks"];
        if (validChannels.includes(channel)) {
            ipcRenderer.send(channel, data);
        }
    },
    receive: (channel, func) => {
        let validChannels = ["tasksResponse", "commandResponse", "error"];
        if (validChannels.includes(channel)) {
            // Deliberately strip event as it includes `sender` which is not what we want to expose
            ipcRenderer.on(channel, (event, ...args) => func(...args));
        }
    }
});