// Main application module
class ChatApp {
    constructor() {
        this.input = document.getElementById('chat-input');
        this.btn = document.getElementById('send-btn');
        this.chatWindow = document.getElementById('chat-window');
        this.downloadBtn = document.getElementById('download-btn');
        this.initializeEventListeners();
    }

    initializeEventListeners() {
        this.btn.addEventListener("click", () => this.handleSendMessage());
        this.input.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.handleSendMessage();
        });

        if (this.downloadBtn) {
            this.downloadBtn.addEventListener('click', () => this.handleDownloadEssay());
        }
    }

    async handleSendMessage() {
        const text = this.input.value.trim();
        if (!text) return;

        this.appendMessage(text, "user");
        this.input.value = "";

        try {
            await this.streamReplyWebSocket(text);
        } catch (error) {
            console.error('Error sending message:', error);
            this.appendMessage("Sorry, I encountered an error. Please try again.", "bot");
        }
    }

    appendMessage(text, sender) {
        const msg = document.createElement('div');
        msg.classList.add('message', sender);

        if (sender === 'bot') {
            const sanitized = DOMPurify.sanitize(marked.parse(text));
            msg.innerHTML = sanitized;

            // Add copy button to entire bot message
            this.addCopyButtonToMessage(msg, text);
            this.addDownloadButtonToMessage(msg)

            // Add copy buttons to code blocks
            setTimeout(() => {
                this.addCopyButtonsToCodeBlocks(msg);
            }, 100);
        } else {
            msg.textContent = text;
        }

        this.chatWindow.appendChild(msg);
        this.chatWindow.scrollTop = this.chatWindow.scrollHeight;
    }

    addCopyButtonToMessage(messageElement, text) {
        const copyBtn = document.createElement('button');
        copyBtn.textContent = '📋 Copy';
        copyBtn.classList.add('copy-message-btn');
        copyBtn.onclick = () => {
            navigator.clipboard.writeText(text);
            copyBtn.textContent = '✅ Copied!';
            setTimeout(() => copyBtn.textContent = '📋 Copy', 2000);
        };
        messageElement.appendChild(copyBtn);
    }

    addCopyButtonsToCodeBlocks(container = document) {
        container.querySelectorAll('pre code').forEach(codeBlock => {
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
                pre.appendChild(copyBtn);
            }
        });
    }

    addDownloadButtonToMessage(messageElement) {
        /**
         * <!-- Action buttons -->
        <div class="action-buttons">
            <button id="download-btn" class="action-btn" title="Download Essay">
                
            </button>
        </div>
         */
        const actionButtons = document.createElement('div');
        const downloadBtn = document.createElement('button');
        actionButtons.classList.add('action-buttons');
        downloadBtn.classList.add('action-btn')
        downloadBtn.onclick = () => {
            this.handleDownloadEssay()
            downloadBtn.textContent = "Downloadin'!";
                    setTimeout(() => copyBtn.textContent = '"📄 Click to Download Essay";', 3000);
        }
        downloadBtn.setAttribute('id', 'download-btn');
        downloadBtn.setAttribute('title', 'Download Essay');
        downloadBtn.textContent = "📄 Click to Download Essay";
        actionButtons.appendChild(downloadBtn);
        messageElement.appendChild(actionButtons);
    }

    async streamReplyWebSocket(userText) {
        const ws = new WebSocket('ws://127.0.0.1:5000/api/research');

        let botMsg = document.createElement("div");
        botMsg.classList.add("message", "bot");
        this.chatWindow.appendChild(botMsg);

        let accumulatedText = "";

        return new Promise((resolve, reject) => {
            ws.onopen = () => {
                ws.send(JSON.stringify({ question: userText }));
            };

            ws.onmessage = (event) => {
                accumulatedText += event.data;
                const sanitized = DOMPurify.sanitize(marked.parse(accumulatedText));
                botMsg.innerHTML = sanitized;
                this.chatWindow.scrollTop = this.chatWindow.scrollHeight;
            };

            ws.onerror = (error) => {
                console.error('WebSocket error:', error);
                botMsg.innerHTML += `\nError: Connection failed`;
                reject(error);
            };

            ws.onclose = (event) => {
                this.addCopyButtonToMessage(botMsg, accumulatedText);
                this.addCopyButtonsToCodeBlocks(botMsg);
                resolve();
            };
        });
    }

    handleDownloadEssay() {
        const essayContent = this.extractEssayContent();
        if (!essayContent) {
            alert('No essay content found between <essay> tags');
            return;
        }

        this.generatePDF(essayContent);
    }

    extractEssayContent() {
        const botMessages = this.chatWindow.querySelectorAll('.message.bot');
        let essayContent = '';

        botMessages.forEach(message => {
            const text = message.textContent || message.innerText;

            // First try to extract content between <essay> tags
            const essayMatch = text.match(/<essay>(.*?)<\/essay>/s);
            if (essayMatch && essayMatch[1]) {
                essayContent += essayMatch[1].trim() + '\n\n';
            } else {
                // Fallback: look for "📝 Generating comprehensive essay.." pattern
                const essayStartIndex = text.indexOf('📝 Generating comprehensive essay..');
                if (essayStartIndex !== -1) {
                    // Extract everything after the essay start indicator
                    const essayText = text.substring(essayStartIndex + '📝 Generating comprehensive essay..'.length).trim();
                    if (essayText) {
                        essayContent += essayText + '\n\n';
                    }
                }
            }
        });

        return essayContent.trim();
    }

    generatePDF(content) {
        // Using jsPDF for PDF generation
        if (typeof jspdf !== 'undefined') {
            const doc = new jspdf.jsPDF();
            const lines = doc.splitTextToSize(content, 180);
            doc.text(lines, 10, 10);
            doc.save('essay.pdf');
        } else {
            // Fallback: download as text file
            this.downloadTextFile(content, 'essay.txt');
        }
    }

    downloadTextFile(content, filename) {
        const blob = new Blob([content], { type: 'text/plain' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
    }
}

// Initialize app when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.chatApp = new ChatApp();
});