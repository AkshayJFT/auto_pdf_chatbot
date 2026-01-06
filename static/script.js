// Global variables
let currentSlide = 0;
let totalSlides = 0;
let presentationMode = false;
let isStreaming = false;
let autoPlay = false;
let isPaused = false;
let speechSynthesis = window.speechSynthesis;
let isAudioEnabled = true;
let isVoiceMode = false;
let currentSpeech = null;
let autoPlayInterval = null;

// Advanced streaming control
let currentStreamingSlide = null;
let streamingController = null;
let currentSpeechPosition = 0;
let currentTypewriterPosition = 0;
let pausedSpeechPosition = 0;
let pausedTypewriterPosition = 0;

// DOM Elements
const fileInput = document.getElementById('fileInput');
const messageInput = document.getElementById('messageInput');
const sendBtn = document.getElementById('sendBtn');
const chatMessages = document.getElementById('chatMessages');
const statusIndicator = document.getElementById('statusIndicator');
const statusText = document.getElementById('statusText');
const loadingOverlay = document.getElementById('loadingOverlay');
const loadingText = document.getElementById('loadingText');
const typingIndicator = document.getElementById('typingIndicator');
const charCount = document.getElementById('charCount');
const imagesContent = document.getElementById('imagesContent');
const presentationControls = document.getElementById('presentationControls');
const slideCounter = document.getElementById('slideCounter');

// Initialize app
document.addEventListener('DOMContentLoaded', function() {
    checkStatus();
    setupEventListeners();
});

// Setup event listeners
function setupEventListeners() {
    fileInput.addEventListener('change', handleFileUpload);
    messageInput.addEventListener('keypress', handleKeyPress);
    messageInput.addEventListener('input', updateCharCount);
    sendBtn.addEventListener('click', sendMessage);
    
    // Check status periodically
    setInterval(checkStatus, 10000);
}

// Check server status
async function checkStatus() {
    try {
        const response = await fetch('/status');
        const data = await response.json();
        
        if (data.status === 'connected') {
            statusIndicator.className = 'status-indicator connected';
            statusText.textContent = 'Connected';
            
            if (data.pdfs_loaded) {
                statusText.textContent = `Connected - ${data.pages_count} pages loaded`;
                
                // Show generate button when PDFs are loaded
                const generateBtn = document.getElementById('generateBtn');
                if (generateBtn) {
                    generateBtn.style.display = 'inline-block';
                }
            }
        }
    } catch (error) {
        statusIndicator.className = 'status-indicator disconnected';
        statusText.textContent = 'Disconnected';
    }
}

// Handle file upload
async function handleFileUpload(event) {
    const files = Array.from(event.target.files);
    
    if (files.length === 0) return;
    
    showLoading('Uploading and processing PDFs...');
    
    const formData = new FormData();
    files.forEach(file => formData.append('files', file));
    
    try {
        const response = await fetch('/upload', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.json();
        
        if (response.ok) {
            showUploadedFiles(files, result);
            addAssistantMessage(`✅ Successfully processed ${result.pages_count} pages from ${files.length} PDF(s). You can now ask me questions about your documents!`);
            checkStatus();
        } else {
            throw new Error(result.detail || 'Upload failed');
        }
    } catch (error) {
        addAssistantMessage(`❌ Error uploading files: ${error.message}`);
    } finally {
        hideLoading();
    }
}

// Show uploaded files in chat
function showUploadedFiles(files, result) {
    const fileNames = files.map(f => f.name).join(', ');
    addAssistantMessage(`📄 Uploaded: ${fileNames}\n✅ Processed ${result.pages_count} pages. Ready for questions!`);
}

// Handle key press
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

// Update character count
function updateCharCount() {
    const length = messageInput.value.length;
    charCount.textContent = `${length}/500`;
    
    if (length > 450) {
        charCount.style.color = 'var(--error-color)';
    } else {
        charCount.style.color = 'var(--text-secondary)';
    }
}

// Send message
async function sendMessage() {
    const message = messageInput.value.trim();
    
    if (!message || isStreaming) return;
    
    // Add user message
    addUserMessage(message);
    messageInput.value = '';
    updateCharCount();
    
    // Start streaming response
    await streamResponse(message);
}

// Send suggestion
function sendSuggestion(suggestion) {
    if (suggestion === 'Create a presentation summary' || suggestion === '🎯 Generate Presentation') {
        generatePresentation();
    } else {
        messageInput.value = suggestion.replace(/�[�-�]|�[�-�]|�[�-�]/g, '').trim();
        sendMessage();
    }
}

// Stream response from server
async function streamResponse(message) {
    isStreaming = true;
    showTyping();
    
    try {
        const response = await fetch('/chat/stream', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ message: message })
        });
        
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let assistantMessage = null;
        let fullResponse = '';
        let contextPages = [];
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'context') {
                            contextPages = data.pages;
                            showContextInfo(contextPages);
                        } else if (data.type === 'chunk') {
                            if (!assistantMessage) {
                                assistantMessage = addAssistantMessage('');
                            }
                            fullResponse = data.full_response;
                            updateAssistantMessage(assistantMessage, fullResponse);
                        } else if (data.type === 'complete') {
                            if (assistantMessage) {
                                finalizeAssistantMessage(assistantMessage, data.full_response, data.related_pages);
                            }
                        } else if (data.type === 'error') {
                            addAssistantMessage(`❌ Error: ${data.message}`);
                        }
                    } catch (error) {
                        console.error('Error parsing SSE data:', error);
                    }
                }
            }
        }
    } catch (error) {
        addAssistantMessage(`❌ Error: ${error.message}`);
    } finally {
        hideTyping();
        isStreaming = false;
    }
}

// Add user message to chat with enhanced styling
function addUserMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message user';
    messageDiv.innerHTML = `
        <div class="message-content">
            <p>${message}</p>
        </div>
    `;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
}

// Add assistant message to chat with enhanced styling
function addAssistantMessage(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = 'message bot';
    messageDiv.innerHTML = `
        <div class="message-content">
            <p class="response-text">${message}</p>
        </div>
    `;
    chatMessages.appendChild(messageDiv);
    scrollToBottom();
    
    // Speak message if audio is enabled and it's not empty
    if (isAudioEnabled && message.trim()) {
        const textToSpeak = message.replace(/[#*•�-🤀-�]/g, '').trim();
        if (textToSpeak) {
            setTimeout(() => speakText(textToSpeak), 300);
        }
    }
    
    return messageDiv;
}

// Update assistant message during streaming
function updateAssistantMessage(messageElement, text) {
    const responseText = messageElement.querySelector('.response-text');
    responseText.innerHTML = formatMessage(text);
    scrollToBottom();
}

// Finalize assistant message
function finalizeAssistantMessage(messageElement, text, relatedPages) {
    updateAssistantMessage(messageElement, text);
    
    if (relatedPages && relatedPages.length > 0) {
        const messageContent = messageElement.querySelector('.message-content');
        const contextInfo = document.createElement('div');
        contextInfo.className = 'context-info';
        contextInfo.innerHTML = `📄 Based on ${relatedPages.length} related page(s)`;
        messageContent.appendChild(contextInfo);
    }
}

// Format message text
function formatMessage(text) {
    return text
        .replace(/\n/g, '<br>')
        .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.*?)\*/g, '<em>$1</em>');
}

// Show context info
function showContextInfo(pages) {
    if (pages && pages.length > 0) {
        console.log('Context pages:', pages);
        // Could show visual indicator of context being used
    }
}

// Show/hide typing indicator
function showTyping() {
    typingIndicator.style.display = 'flex';
}

function hideTyping() {
    typingIndicator.style.display = 'none';
}

// Show/hide loading overlay
function showLoading(text = 'Processing...') {
    loadingText.textContent = text;
    loadingOverlay.style.display = 'flex';
}

function hideLoading() {
    loadingOverlay.style.display = 'none';
}

// Scroll to bottom of chat
function scrollToBottom() {
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

// Clear chat
async function clearChat() {
    try {
        await fetch('/chat/clear', { method: 'DELETE' });
        
        // Clear chat UI
        chatMessages.innerHTML = `
            <div class="welcome-message">
                <div class="assistant-message">
                    <i class="fas fa-robot"></i>
                    <div class="message-content">
                        <p>Chat history cleared. How can I help you with your documents?</p>
                    </div>
                </div>
            </div>
        `;
    } catch (error) {
        console.error('Error clearing chat:', error);
    }
}

// Generate presentation
async function generatePresentation() {
    showLoading('Generating advanced presentation...');
    
    try {
        const response = await fetch('/presentation/generate', {
            method: 'POST'
        });
        
        const result = await response.json();
        
        if (response.ok) {
            totalSlides = result.presentation.total_slides;
            currentSlide = 0;
            presentationMode = true;
            isPaused = false;
            
            // Show presentation controls
            presentationControls.style.display = 'block';
            const presentationControlsBottom = document.getElementById('presentationControlsBottom');
            if (presentationControlsBottom) presentationControlsBottom.style.display = 'flex';
            
            // Show auto play and pause buttons
            const autoPlayBtn = document.getElementById('autoPlayBtn');
            const pauseBtn = document.getElementById('pauseBtn');
            if (autoPlayBtn) autoPlayBtn.style.display = 'inline-block';
            if (pauseBtn) pauseBtn.style.display = 'inline-block';
            
            updateSlideCounter();
            updatePresentationStatus('Presentation ready - Use controls or enable auto-play');
            
            // Add message to chat
            addAssistantMessage(`🎯 Generated advanced presentation with ${totalSlides} slides! 🎤 Audio enabled, ⏯️ Auto-play available. Navigate using controls or voice commands.`);
            
            // Load first slide immediately
            await loadSlide(0);
            
        } else {
            throw new Error(result.detail || 'Failed to generate presentation');
        }
    } catch (error) {
        addAssistantMessage(`❌ Error generating presentation: ${error.message}`);
    } finally {
        hideLoading();
    }
}

// Load specific slide with streaming
async function loadSlide(slideNumber) {
    try {
        // Clear images panel and show loading
        imagesContent.innerHTML = `
            <div class="loading-images" style="text-align: center; color: var(--text-secondary); padding: 40px 20px;">
                <i class="fas fa-circle-notch fa-spin" style="font-size: 2rem; color: var(--accent-color); margin-bottom: 1rem;"></i>
                <p>Loading slide ${slideNumber + 1}...</p>
            </div>
        `;
        
        currentSlide = slideNumber;
        updateSlideCounter();
        
        // Start streaming the slide
        await streamSlide(slideNumber);
        
    } catch (error) {
        console.error('Error loading slide:', error);
        imagesContent.innerHTML = `
            <div class="error-message" style="color: var(--error-color); text-align: center; padding: 20px;">
                Error loading slide: ${error.message}
            </div>
        `;
    }
}

// Advanced stream slide content with enhanced controls
async function streamSlide(slideNumber) {
    try {
        // Setup streaming controller for pause/resume
        streamingController = new AbortController();
        currentStreamingSlide = slideNumber;
        
        const response = await fetch(`/presentation/slide/${slideNumber}/stream`, {
            signal: streamingController.signal
        });
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        let slideTitle = '';
        let slideContent = '';
        let fullSlideText = '';
        let imageCount = 0;
        let assistantMessage = null;
        let streamingContent = '';
        
        // Initialize images panel
        imagesContent.innerHTML = `
            <div class="images-loading" style="padding: 20px;">
                <h4 style="color: #3b82f6; margin-bottom: 15px; display: flex; align-items: center; gap: 0.5rem;">
                    <i class="fas fa-images"></i> Slide ${slideNumber + 1} Visuals
                </h4>
                <div class="images-list"></div>
            </div>
        `;
        
        while (true) {
            const { done, value } = await reader.read();
            
            if (done) break;
            
            // Check if paused
            while (isPaused && !streamingController.signal.aborted) {
                await new Promise(resolve => setTimeout(resolve, 100));
            }
            
            if (streamingController.signal.aborted) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6));
                        
                        if (data.type === 'slide_info') {
                            slideTitle = data.title;
                            fullSlideText = data.title;
                            
                            // Add slide title message to chat with enhanced styling
                            assistantMessage = addAssistantMessage('');
                            const titleContent = `## 🎯 ${data.title}\n\n*📊 Slide ${data.slide_number + 1} of ${data.total_slides}*\n\n`;
                            updateAssistantMessage(assistantMessage, titleContent);
                            
                            // Speak title if audio enabled
                            if (isAudioEnabled && !isPaused) {
                                speakText(data.title);
                            }
                            
                        } else if (data.type === 'content_chunk') {
                            // Advanced word-by-word streaming with progress tracking
                            streamingContent = `## 🎯 ${slideTitle}\n\n*📝 Content:*\n\n${data.full_content}`;
                            fullSlideText = slideTitle + '. ' + data.full_content;
                            
                            if (assistantMessage && !isPaused) {
                                updateAssistantMessage(assistantMessage, streamingContent + '<span class="cursor">|</span>');
                            }
                            
                            // Update progress
                            updatePresentationStatus(`Streaming... ${Math.round(data.progress * 100)}% complete`);
                            
                        } else if (data.type === 'image') {
                            // Enhanced image display with animations
                            const imagesList = imagesContent.querySelector('.images-list');
                            
                            // Remove cursor from chat when first image arrives
                            if (imageCount === 0 && assistantMessage) {
                                updateAssistantMessage(assistantMessage, streamingContent);
                                
                                // Speak content after text streaming completes
                                if (isAudioEnabled && !isPaused && streamingContent) {
                                    const contentToSpeak = streamingContent.replace(/[#*•]/g, '').replace(/\n/g, ' ');
                                    setTimeout(() => speakText(contentToSpeak), 500);
                                }
                            }
                            
                            const imageElement = document.createElement('div');
                            imageElement.className = 'slide-image-item';
                            imageElement.style.cssText = `
                                opacity: 0;
                                transform: translateY(20px) scale(0.95);
                                animation: slideInUp 0.8s ease forwards;
                                animation-delay: ${imageCount * 0.5}s;
                                margin-bottom: 15px;
                                padding: 12px;
                                background: rgba(255,255,255,0.05);
                                border-radius: 12px;
                                border: 1px solid rgba(255,255,255,0.1);
                                transition: all 0.3s ease;
                            `;
                            
                            imageElement.innerHTML = `
                                <div style="margin-bottom: 12px; display: flex; justify-content: space-between; align-items: center;">
                                    <div style="display: flex; align-items: center; gap: 0.5rem;">
                                        <span style="background: linear-gradient(135deg, #3b82f6 0%, #2563eb 100%); color: white; padding: 4px 12px; border-radius: 20px; font-size: 0.75rem; font-weight: 500;">
                                            Image ${data.image_index + 1}
                                        </span>
                                        <span style="color: rgba(255,255,255,0.6); font-size: 0.75rem;">
                                            Page ${data.page_number}
                                        </span>
                                    </div>
                                    <div style="display: flex; gap: 0.25rem;">
                                        ${Array(data.total_images).fill(0).map((_, i) => 
                                            `<div style="width: 8px; height: 8px; border-radius: 50%; background: ${
                                                i <= data.image_index ? '#3b82f6' : 'rgba(255,255,255,0.3)'
                                            };"></div>`
                                        ).join('')}
                                    </div>
                                </div>
                                <div style="position: relative; overflow: hidden; border-radius: 8px;">
                                    <img src="${data.data}" 
                                         style="width: 100%; height: auto; border-radius: 8px; box-shadow: 0 4px 20px rgba(0,0,0,0.3); transition: transform 0.3s ease;"
                                         alt="Page ${data.page_number}"
                                         onmouseover="this.style.transform='scale(1.02)'"
                                         onmouseout="this.style.transform='scale(1)'">
                                </div>
                            `;
                            
                            imagesList.appendChild(imageElement);
                            imageCount++;
                            
                            updatePresentationStatus(`Loaded ${imageCount} of ${data.total_images} images`);
                            
                        } else if (data.type === 'complete') {
                            // Slide loading complete with enhanced completion
                            console.log(`Slide ${data.slide_number} loaded completely`);
                            if (assistantMessage) {
                                finalizeAssistantMessage(assistantMessage, streamingContent, []);
                            }
                            
                            updatePresentationStatus(`Slide ${slideNumber + 1} complete - ${imageCount} images loaded`);
                            
                            // Auto-advance if auto-play is enabled
                            if (autoPlay && !isPaused && slideNumber < totalSlides - 1) {
                                setTimeout(() => {
                                    if (autoPlay && !isPaused) nextSlide();
                                }, 3000); // Wait 3 seconds before auto-advancing
                            }
                            
                        } else if (data.type === 'error') {
                            throw new Error(data.message);
                        }
                        
                    } catch (parseError) {
                        console.error('Error parsing SSE data:', parseError);
                    }
                }
            }
        }
        
    } catch (error) {
        if (error.name === 'AbortError') {
            console.log('Slide streaming aborted');
            return;
        }
        console.error('Error streaming slide:', error);
        updatePresentationStatus('Error loading slide: ' + error.message);
        throw error;
    } finally {
        streamingController = null;
        currentStreamingSlide = null;
    }
}

// Display slide content
function displaySlide(slide) {
    console.log('Displaying slide:', slide); // Debug log
    
    let imagesHTML = '';
    
    if (slide.images && slide.images.length > 0) {
        imagesHTML = `
            <div class="slide-images">
                <h4>📸 Visuals:</h4>
                ${slide.images.map(img => 
                    `<img src="${img.data}" class="slide-image" alt="Page ${img.page_number}" 
                          style="max-width: 100%; margin: 10px 0; border-radius: 8px; box-shadow: 0 2px 10px rgba(0,0,0,0.3);">`
                ).join('')}
            </div>
        `;
    } else {
        // Show related page info if no images
        if (slide.relevant_pages && slide.relevant_pages.length > 0) {
            const pageNums = slide.relevant_pages.map(p => p.page_number).join(', ');
            imagesHTML = `<div class="page-reference">📄 Based on pages: ${pageNums}</div>`;
        }
    }
    
    documentContent.innerHTML = `
        <div class="slide-content" style="padding: 20px; background: var(--primary-bg); border-radius: 12px; margin: 10px 0;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
                <h2 class="slide-title" style="color: var(--accent-color); margin: 0;">${slide.title}</h2>
                <span style="background: var(--accent-color); color: white; padding: 5px 10px; border-radius: 15px; font-size: 0.8em;">
                    Slide ${slide.slide_number}
                </span>
            </div>
            <div class="slide-text" style="line-height: 1.6; margin-bottom: 20px;">
                ${formatMessage(slide.content)}
            </div>
            ${imagesHTML}
        </div>
    `;
}

// Navigation functions
function previousSlide() {
    if (currentSlide > 0) {
        loadSlide(currentSlide - 1);
    }
}

function nextSlide() {
    if (currentSlide < totalSlides - 1) {
        loadSlide(currentSlide + 1);
    }
}

function updateSlideCounter() {
    slideCounter.textContent = `Slide ${currentSlide + 1} of ${totalSlides}`;
}

// Advanced presentation controls
function startAutoPresentation() {
    if (!presentationMode || autoPlay) return;
    
    autoPlay = true;
    isPaused = false;
    updateAutoPlayButton();
    updatePresentationStatus('Auto-play started - Slides will advance automatically');
    
    // Start auto-advancing slides every 15 seconds
    autoPlayInterval = setInterval(() => {
        if (!isPaused && autoPlay) {
            if (currentSlide < totalSlides - 1) {
                nextSlide();
            } else {
                // End of presentation
                stopAutoPlay();
                updatePresentationStatus('Presentation completed');
                addAssistantMessage('🏁 Presentation completed! You can restart or navigate manually.');
            }
        }
    }, 15000);
}

function stopAutoPlay() {
    autoPlay = false;
    isPaused = false;
    
    if (autoPlayInterval) {
        clearInterval(autoPlayInterval);
        autoPlayInterval = null;
    }
    
    updateAutoPlayButton();
    updatePresentationStatus('Auto-play stopped');
}

function toggleAutoPlay() {
    if (autoPlay) {
        stopAutoPlay();
    } else {
        startAutoPresentation();
    }
}

function pauseResume() {
    if (!presentationMode) return;
    
    isPaused = !isPaused;
    
    const pauseIcon = document.getElementById('pauseIcon');
    const pauseResumeBtn = document.getElementById('pauseResumeBtn');
    
    if (isPaused) {
        // Pause speech if active
        if (currentSpeech && speechSynthesis.speaking) {
            speechSynthesis.pause();
        }
        
        if (pauseIcon) pauseIcon.className = 'fas fa-play';
        updatePresentationStatus('Presentation paused');
        
    } else {
        // Resume speech if paused
        if (currentSpeech && speechSynthesis.paused) {
            speechSynthesis.resume();
        }
        
        if (pauseIcon) pauseIcon.className = 'fas fa-pause';
        updatePresentationStatus(autoPlay ? 'Auto-play resumed' : 'Presentation resumed');
    }
}

function pausePresentation() {
    if (!isPaused) {
        pauseResume();
    }
}

function updateAutoPlayButton() {
    const autoToggleBtn = document.getElementById('autoToggleBtn');
    const autoIcon = document.getElementById('autoIcon');
    
    if (autoToggleBtn && autoIcon) {
        if (autoPlay) {
            autoIcon.className = 'fas fa-stop';
            autoToggleBtn.innerHTML = '<i class="fas fa-stop" id="autoIcon"></i> Stop Auto';
        } else {
            autoIcon.className = 'fas fa-play';
            autoToggleBtn.innerHTML = '<i class="fas fa-play" id="autoIcon"></i> Auto Play';
        }
    }
}

function updatePresentationStatus(message) {
    const statusElement = document.getElementById('presentationStatus');
    if (statusElement) {
        if (message) {
            statusElement.textContent = message;
            statusElement.style.display = 'inline';
            
            // Auto-hide after 3 seconds
            setTimeout(() => {
                if (statusElement.textContent === message) {
                    statusElement.style.display = 'none';
                }
            }, 3000);
        } else {
            statusElement.style.display = 'none';
        }
    }
}

// Audio and voice controls
function toggleAudio() {
    isAudioEnabled = !isAudioEnabled;
    
    const audioToggle = document.getElementById('audioToggle');
    const audioIcon = document.getElementById('audioIcon');
    
    if (isAudioEnabled) {
        audioToggle.innerHTML = '<i class="fas fa-volume-up" id="audioIcon"></i> Audio On';
        audioToggle.classList.remove('muted');
        updatePresentationStatus('Audio enabled');
    } else {
        audioToggle.innerHTML = '<i class="fas fa-volume-mute" id="audioIcon"></i> Audio Off';
        audioToggle.classList.add('muted');
        
        // Stop any current speech
        if (currentSpeech) {
            speechSynthesis.cancel();
            currentSpeech = null;
        }
        
        updatePresentationStatus('Audio disabled');
    }
}

function toggleVoiceMode() {
    isVoiceMode = !isVoiceMode;
    
    const voiceModeBtn = document.getElementById('voiceModeBtn');
    
    if (isVoiceMode) {
        voiceModeBtn.innerHTML = '<i class="fas fa-microphone-slash"></i> Exit Voice';
        updatePresentationStatus('Voice mode enabled - Speak your commands');
        startVoiceRecognition();
    } else {
        voiceModeBtn.innerHTML = '<i class="fas fa-microphone"></i> Voice Mode';
        updatePresentationStatus('Voice mode disabled');
        stopVoiceRecognition();
    }
}

function toggleVoiceInput() {
    const voiceBtn = document.getElementById('voiceBtn');
    
    if (voiceBtn.classList.contains('recording')) {
        // Stop recording
        voiceBtn.classList.remove('recording');
        stopVoiceRecognition();
    } else {
        // Start recording
        voiceBtn.classList.add('recording');
        startVoiceRecognition();
    }
}

let recognition = null;

function startVoiceRecognition() {
    if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
        updatePresentationStatus('Speech recognition not supported');
        return;
    }
    
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
    recognition = new SpeechRecognition();
    
    recognition.continuous = true;
    recognition.interimResults = false;
    recognition.lang = 'en-US';
    
    recognition.onresult = function(event) {
        const command = event.results[event.results.length - 1][0].transcript.toLowerCase().trim();
        handleVoiceCommand(command);
    };
    
    recognition.onerror = function(event) {
        console.error('Speech recognition error:', event.error);
        updatePresentationStatus('Voice recognition error: ' + event.error);
    };
    
    recognition.start();
}

function stopVoiceRecognition() {
    if (recognition) {
        recognition.stop();
        recognition = null;
    }
    
    const voiceBtn = document.getElementById('voiceBtn');
    if (voiceBtn) {
        voiceBtn.classList.remove('recording');
    }
}

function handleVoiceCommand(command) {
    console.log('Voice command:', command);
    
    if (command.includes('next slide') || command.includes('next')) {
        nextSlide();
        updatePresentationStatus('Voice command: Next slide');
    } else if (command.includes('previous slide') || command.includes('previous') || command.includes('back')) {
        previousSlide();
        updatePresentationStatus('Voice command: Previous slide');
    } else if (command.includes('pause')) {
        if (!isPaused) pauseResume();
        updatePresentationStatus('Voice command: Paused');
    } else if (command.includes('resume') || command.includes('continue') || command.includes('play')) {
        if (isPaused) pauseResume();
        else if (!autoPlay) startAutoPresentation();
        updatePresentationStatus('Voice command: Resumed');
    } else if (command.includes('stop')) {
        stopAutoPlay();
        updatePresentationStatus('Voice command: Stopped');
    } else if (command.includes('auto play') || command.includes('start auto')) {
        startAutoPresentation();
        updatePresentationStatus('Voice command: Auto-play started');
    } else if (command.includes('exit') || command.includes('close')) {
        exitPresentation();
        updatePresentationStatus('Voice command: Exit presentation');
    } else {
        // Treat as a regular question
        messageInput.value = command;
        sendMessage();
        updatePresentationStatus('Voice question processed');
    }
}

function speakText(text) {
    if (!isAudioEnabled || !speechSynthesis) return;
    
    // Cancel any previous speech
    speechSynthesis.cancel();
    
    // Clean text for speech
    const cleanText = text.replace(/[#*•-]/g, '').replace(/\n/g, ' ').trim();
    if (!cleanText) return;
    
    currentSpeech = new SpeechSynthesisUtterance(cleanText);
    currentSpeech.rate = 0.9;
    currentSpeech.pitch = 1.0;
    currentSpeech.volume = 0.8;
    
    currentSpeech.onend = () => {
        currentSpeech = null;
        const audioToggle = document.getElementById('audioToggle');
        if (audioToggle) audioToggle.classList.remove('speaking');
    };
    
    currentSpeech.onstart = () => {
        const audioToggle = document.getElementById('audioToggle');
        if (audioToggle) audioToggle.classList.add('speaking');
    };
    
    speechSynthesis.speak(currentSpeech);
}

function exitPresentation() {
    presentationMode = false;
    autoPlay = false;
    isPaused = false;
    
    // Stop any ongoing speech or streaming
    if (currentSpeech) {
        speechSynthesis.cancel();
        currentSpeech = null;
    }
    
    if (autoPlayInterval) {
        clearInterval(autoPlayInterval);
        autoPlayInterval = null;
    }
    
    if (streamingController) {
        streamingController.abort();
        streamingController = null;
    }
    
    // Hide presentation controls
    presentationControls.style.display = 'none';
    const presentationControlsBottom = document.getElementById('presentationControlsBottom');
    if (presentationControlsBottom) presentationControlsBottom.style.display = 'none';
    
    // Hide auto play and pause buttons
    const autoPlayBtn = document.getElementById('autoPlayBtn');
    const pauseBtn = document.getElementById('pauseBtn');
    if (autoPlayBtn) autoPlayBtn.style.display = 'none';
    if (pauseBtn) pauseBtn.style.display = 'none';
    
    // Reset images content
    imagesContent.innerHTML = `
        <div class="content-placeholder">
            <i class="fas fa-image"></i>
            <p>Images will appear here during presentation</p>
            <p style="font-size: 0.9rem; opacity: 0.7; margin-top: 1rem;">Upload PDFs and generate a presentation to see visuals</p>
        </div>
    `;
    
    updatePresentationStatus('');
    addAssistantMessage("📋 Presentation mode closed. You can generate a new presentation anytime!");
}

// Panel toggle function
function togglePanel(side) {
    const panel = document.getElementById(side === 'left' ? 'leftPanel' : 'rightPanel');
    const toggleBtn = document.getElementById(side + 'Toggle');
    
    if (panel.style.display === 'none') {
        panel.style.display = 'flex';
        toggleBtn.innerHTML = '<i class="fas fa-eye-slash"></i>';
    } else {
        panel.style.display = 'none';
        toggleBtn.innerHTML = '<i class="fas fa-eye"></i>';
    }
}