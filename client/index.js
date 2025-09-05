const input = document.getElementById('chat-input');
const btn = document.getElementById('send-btn');
const chatWindow = document.getElementById('chat-window');

function appendMessage(text, sender) {
    const msg = document.createElement('div');
    msg.classList.add('message', sender);
    msg.textContent = text;
    chatWindow.appendChild(msg);
    chatWindow.scrollTop = chatWindow.scrollHeight;
}

btn.addEventListener("click", async () => {
    const text = input.value.trim();
    if (!text) return;

    appendMessage(text, "user");
    input.value = "";

    // await streamDemo(text);
    await streamReply(text);
});

input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') btn.click();
});


async function streamReply(userText) {
    const response = await fetch(`/api/research?question=${encodeURIComponent(userText)}`);
    console.log(response.status + ' ' + response.statusText);
    console.log(`response body: ${response.body}`)
    const reader = response.body.getReader();
    console.log(`response body reader: ${reader}`)

    const decoder = new TextDecoder("utf-8");

    let botMsg = document.createElement("div");
    botMsg.classList.add("message", "bot");
    chatWindow.appendChild(botMsg);

    let buffer = "";
    while (true) {
        const { done, value } = await reader.read();
        console.log(`raw value: ${value}`);

        // Decode the current chunk
        buffer += decoder.decode(value, { stream: true });
        console.log(`BUFFER!: ${buffer}`);

        // Optional: split on newline if server sends chunked lines
        // e.g. for SSE or JSON streaming, parse buffer here
        botMsg.textContent += buffer;
        buffer = ""; // reset since we’re directly appending
        chatWindow.scrollTop = chatWindow.scrollHeight;
        if (done) break;

    }

    // flush any remaining buffered text
    buffer += decoder.decode();
    if (buffer) botMsg.textContent += buffer;
    chatWindow.appendChild(botMsg);
}



async function streamDemo(inputText) {
    const response = await fetch(`/demo?msg=${encodeURIComponent(inputText)}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder('utf-8');

    let botMsg = document.createElement("div");
    botMsg.classList.add('message', 'bot');
    chatWindow.appendChild(botMsg);

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        botMsg.textContent += decoder.decode(value, { stream: true });
        chatWindow.scrollTop = chatWindow.scrollHeight;
    }
}