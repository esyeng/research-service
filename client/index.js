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

    await streamDemo(text);
});

input.addEventListener('keypress', (e) => {
    if (e.key === 'Enter') btn.click();
});


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