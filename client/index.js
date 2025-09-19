const input = document.getElementById('chat-input');
const btn = document.getElementById('send-btn');
const chatWindow = document.getElementById('chat-window');

// Create a DOMPurify instance for HTML sanitization (fallback if not available)
const purifyHTML = (dirty) => {
    try {
        if (typeof DOMPurify !== 'undefined') {
            return DOMPurify.sanitize(dirty);
        }
    } catch (e) {
        console.warn('DOMPurify not available, using basic sanitization');
    }
    
    // Basic sanitization fallback
    return dirty
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#x27;');
};

// Configure marked options
marked.setOptions({
    highlight: function(code, lang) {
        if (typeof hljs !== 'undefined' && lang && hljs.getLanguage(lang)) {
            return hljs.highlight(code, { language: lang }).value;
        }
        return code;
    },
    breaks: true,
    gfm: true
});

function appendMessage(text, sender) {
    const msg = document.createElement('div');
    msg.classList.add('message', sender);
    
    // Process markdown for bot messages, plain text for user messages
    if (sender === 'bot') {
        const sanitized = purifyHTML(marked.parse(text));
        msg.innerHTML = sanitized;
        
        // Add copy button to code blocks
        setTimeout(() => {
            msg.querySelectorAll('pre code').forEach(codeBlock => {
                const copyBtn = document.createElement('button');
                copyBtn.textContent = 'Copy';
                copyBtn.classList.add('copy-btn');
                copyBtn.onclick = () => {
                    navigator.clipboard.writeText(codeBlock.textContent);
                    copyBtn.textContent = 'Copied!';
                    setTimeout(() => copyBtn.textContent = 'Copy', 2000);
                };
                
                const pre = codeBlock.parentElement;
                if (pre && !pre.querySelector('.copy-btn')) {
                    pre.style.position = 'relative';
                    copyBtn.style.position = 'absolute';
                    copyBtn.style.top = '8px';
                    copyBtn.style.right = '8px';
                    copyBtn.style.padding = '4px 8px';
                    copyBtn.style.fontSize = '12px';
                    copyBtn.style.background = 'rgba(255, 255, 255, 0.1)';
                    copyBtn.style.border = '1px solid rgba(255, 255, 255, 0.2)';
                    copyBtn.style.borderRadius = '4px';
                    copyBtn.style.color = 'white';
                    copyBtn.style.cursor = 'pointer';
                    pre.appendChild(copyBtn);
                }
            });
        }, 100);
    } else {
        msg.textContent = text;
    }
    
    chatWindow.appendChild(msg);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

btn.addEventListener("click", async () => {
    const text = input.value.trim();
    if (!text) return;

    appendMessage(text, "user");
    input.value = "";

    // Choose either WebSocket or HTTP streaming
    // await streamReply(text); // HTTP version
    await streamReplyWebSocket(text); // WebSocket version
});

input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') btn.click();
});


// WebSocket implementation for /api/research
async function streamReplyWebSocket(userText) {
    // Create WebSocket connection to localhost for development
    const ws = new WebSocket('ws://127.0.0.1:5000/api/research');
    console.log('usrtxt', userText)
    
    let botMsg = document.createElement("div");
    botMsg.classList.add("message", "bot");
    chatWindow.appendChild(botMsg);
    
    let accumulatedText = "";

    ws.onopen = () => {
        // Send the question as JSON when connection opens
        ws.send(JSON.stringify({ question: userText }));
    };

    ws.onmessage = (event) => {
        // Append received data to accumulated text
        accumulatedText += event.data;
        
        // Process markdown and update the message
        const sanitized = purifyHTML(marked.parse(accumulatedText));
        botMsg.innerHTML = sanitized;
        
        chatWindow.scrollTop = chatWindow.scrollHeight;
        console.log('evt data', event.data)
    };

    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        botMsg.innerHTML += `\nError: Connection failed`;
    };

    ws.onclose = (event) => {
        console.log('WebSocket connection closed:', event.code, event.reason);
        // Add copy buttons to any code blocks
        addCopyButtonsToCodeBlocks();
    };

    // Return a promise that resolves when the connection closes
    return new Promise((resolve) => {
        ws.onclose = (event) => {
            console.log('WebSocket connection closed:', event.code, event.reason);
            addCopyButtonsToCodeBlocks();
            resolve();
        };
    });
}

// Helper function to add copy buttons to code blocks
function addCopyButtonsToCodeBlocks() {
    document.querySelectorAll('pre code').forEach(codeBlock => {
        const pre = codeBlock.parentElement;
        if (pre && !pre.querySelector('.copy-btn')) {
            const copyBtn = document.createElement('button');
            copyBtn.textContent = 'Copy';
            copyBtn.classList.add('copy-btn');
            copyBtn.onclick = () => {
                navigator.clipboard.writeText(codeBlock.textContent);
                copyBtn.textContent = 'Copied!';
                setTimeout(() => copyBtn.textContent = 'Copy', 2000);
            };
            
            pre.style.position = 'relative';
            copyBtn.style.position = 'absolute';
            copyBtn.style.top = '8px';
            copyBtn.style.right = '8px';
            copyBtn.style.padding = '4px 8px';
            copyBtn.style.fontSize = '12px';
            copyBtn.style.background = 'rgba(255, 255, 255, 0.1)';
            copyBtn.style.border = '1px solid rgba(255, 255, 255, 0.2)';
            copyBtn.style.borderRadius = '4px';
            copyBtn.style.color = 'white';
            copyBtn.style.cursor = 'pointer';
            pre.appendChild(copyBtn);
        }
    });
}

// Original HTTP streaming implementation (keep for reference)
async function streamReply(userText) {
    const response = await fetch(`http://127.0.0.1:5000/api/research?question=${encodeURIComponent(userText)}`);
    console.log(response.status + ' ' + response.statusText);
    console.log(`response body: ${response.body}`)
    const reader = response.body.getReader();
    console.log(`response body reader: ${reader}`)

    const decoder = new TextDecoder("utf-8");

    let botMsg = document.createElement("div");
    botMsg.classList.add("message", "bot");
    chatWindow.appendChild(botMsg);

    let buffer = "";
    let accumulatedText = "";
    while (true) {
        const { done, value } = await reader.read();
        console.log(`raw value: ${value}`);

        // Decode the current chunk
        buffer += decoder.decode(value, { stream: true });
        console.log(`BUFFER!: ${buffer}`);

        // Append to accumulated text and process markdown
        accumulatedText += buffer;
        const sanitized = purifyHTML(marked.parse(accumulatedText));
        botMsg.innerHTML = sanitized;
        
        buffer = "";
        chatWindow.scrollTop = chatWindow.scrollHeight;
        if (done) break;
    }

    // flush any remaining buffered text
    buffer += decoder.decode();
    if (buffer) {
        accumulatedText += buffer;
        const sanitized = purifyHTML(marked.parse(accumulatedText));
        botMsg.innerHTML = sanitized;
    }
    addCopyButtonsToCodeBlocks();
    chatWindow.scrollTop = chatWindow.scrollHeight;
}



async function streamDemo(inputText) {
    const response = await fetch(`/demo?msg=${encodeURIComponent(inputText)}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');

    let botMsg = document.createElement("div");
    botMsg.classList.add('message', 'bot');
    chatWindow.appendChild(botMsg);

    let accumulatedText = "";
    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        accumulatedText += decoder.decode(value, { stream: true });
        const sanitized = purifyHTML(marked.parse(accumulatedText));
        botMsg.innerHTML = sanitized;
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }
    addCopyButtonsToCodeBlocks();
}
