/**
 * Journalyst AI Assistant - Test Client
 * Modern chat interface for testing the AI pipeline
 */

// ============================================
// State
// ============================================

let sessionId = generateUUID();
let isLoading = false;

// ============================================
// DOM Elements
// ============================================

const elements = {
  userId: document.getElementById('userId'),
  sessionId: document.getElementById('sessionId'),
  query: document.getElementById('query'),
  sendBtn: document.getElementById('sendBtn'),
  chatMessages: document.getElementById('chatMessages'),
  metadataPanel: document.getElementById('metadataPanel'),
  metadataContent: document.getElementById('metadataContent'),
  toggleMetaBtn: document.getElementById('toggleMetaBtn'),
  clearChatBtn: document.getElementById('clearChatBtn'),
  newSessionBtn: document.getElementById('newSessionBtn'),
  apiStatus: document.getElementById('apiStatus'),
  quickQueries: document.querySelectorAll('.quick-query')
};

const API_BASE = 'http://localhost:8000';

// ============================================
// Utilities
// ============================================

function generateUUID() {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
}

function formatTime(date) {
  return new Intl.DateTimeFormat('en-US', {
    hour: 'numeric',
    minute: '2-digit',
    hour12: true
  }).format(date);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

function autoResizeTextarea(textarea) {
  textarea.style.height = 'auto';
  textarea.style.height = Math.min(textarea.scrollHeight, 120) + 'px';
}

// ============================================
// API Status Check
// ============================================

async function checkApiStatus() {
  const statusEl = elements.apiStatus;
  
  try {
    const res = await fetch(`${API_BASE}/health`, { method: 'GET' });
    if (res.ok) {
      statusEl.className = 'status-indicator connected';
      statusEl.querySelector('.status-text').textContent = 'Connected';
    } else {
      throw new Error('API returned error');
    }
  } catch (err) {
    statusEl.className = 'status-indicator error';
    statusEl.querySelector('.status-text').textContent = 'Disconnected';
  }
}

// ============================================
// Chat Messages
// ============================================

function addMessage(type, content, metadata = null) {
  // Remove welcome message if present
  const welcome = elements.chatMessages.querySelector('.welcome-message');
  if (welcome) welcome.remove();
  
  const message = document.createElement('div');
  message.className = `message ${type}`;
  
  const time = formatTime(new Date());
  
  if (type === 'loading') {
    message.innerHTML = `
      <div class="message-avatar">
        <i class="fas fa-robot"></i>
      </div>
      <div class="message-content">
        <div class="typing-indicator">
          <span></span><span></span><span></span>
        </div>
        <span style="margin-left: 8px; color: var(--text-muted);">Thinking...</span>
      </div>
    `;
  } else if (type === 'user') {
    message.innerHTML = `
      <div class="message-avatar">
        <i class="fas fa-user"></i>
      </div>
      <div class="message-content">
        <div class="message-text">${escapeHtml(content)}</div>
        <div class="message-time">${time}</div>
      </div>
    `;
  } else if (type === 'assistant') {
    let suggestionsHtml = '';
    if (metadata?.suggestions && metadata.suggestions.length > 0) {
      suggestionsHtml = `
        <div class="suggestions">
          ${metadata.suggestions.map(s => 
            `<button class="suggestion-chip" data-query="${escapeHtml(s)}">${escapeHtml(s)}</button>`
          ).join('')}
        </div>
      `;
    }
    
    message.innerHTML = `
      <div class="message-avatar">
        <i class="fas fa-robot"></i>
      </div>
      <div class="message-content">
        <div class="message-text">${escapeHtml(content)}</div>
        ${suggestionsHtml}
        <div class="message-time">${time}</div>
      </div>
    `;
    
    // Add click handlers for suggestions
    message.querySelectorAll('.suggestion-chip').forEach(chip => {
      chip.addEventListener('click', () => {
        elements.query.value = chip.dataset.query;
        autoResizeTextarea(elements.query);
        elements.query.focus();
      });
    });
  } else if (type === 'error') {
    message.innerHTML = `
      <div class="message-avatar">
        <i class="fas fa-exclamation-triangle"></i>
      </div>
      <div class="message-content">
        <div class="message-text">${escapeHtml(content)}</div>
        <div class="message-time">${time}</div>
      </div>
    `;
  }
  
  elements.chatMessages.appendChild(message);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
  
  return message;
}

function removeLoadingMessage() {
  const loading = elements.chatMessages.querySelector('.message.loading');
  if (loading) loading.remove();
}

// ============================================
// Metadata Panel
// ============================================

function updateMetadataPanel(data) {
  if (!data) {
    elements.metadataContent.innerHTML = `
      <div class="empty-state">
        <i class="fas fa-inbox"></i>
        <p>Send a query to see response metadata</p>
      </div>
    `;
    return;
  }
  
  let html = '';
  
  // Query Info
  if (data.metadata) {
    const meta = data.metadata;
    html += `
      <div class="meta-section">
        <h4><i class="fas fa-tags"></i> Query Classification</h4>
        <div>
          ${meta.query_type ? `<span class="meta-badge info">${meta.query_type}</span>` : ''}
          ${meta.is_in_domain !== undefined ? 
            `<span class="meta-badge ${meta.is_in_domain ? 'success' : 'warning'}">
              ${meta.is_in_domain ? 'In Domain' : 'Out of Domain'}
            </span>` : ''
          }
        </div>
      </div>
    `;
    
    // Sources Used
    if (meta.sources_used && meta.sources_used.length > 0) {
      html += `
        <div class="meta-section">
          <h4><i class="fas fa-database"></i> Sources</h4>
          <div>
            ${meta.sources_used.map(s => `<span class="meta-badge">${s}</span>`).join('')}
          </div>
        </div>
      `;
    }
    
    // Confidence
    if (meta.confidence !== undefined) {
      const confidencePercent = Math.round(meta.confidence * 100);
      const confidenceClass = confidencePercent >= 80 ? 'success' : confidencePercent >= 50 ? 'warning' : 'error';
      html += `
        <div class="meta-section">
          <h4><i class="fas fa-chart-line"></i> Confidence</h4>
          <span class="meta-badge ${confidenceClass}">${confidencePercent}%</span>
        </div>
      `;
    }
  }
  
  // Trade Data
  if (data.data?.trade_data && data.data.trade_data.length > 0) {
    const trades = data.data.trade_data;
    html += `
      <div class="meta-section">
        <h4><i class="fas fa-exchange-alt"></i> Trade Data (${trades.length} rows)</h4>
        <div class="meta-json">${JSON.stringify(trades.slice(0, 5), null, 2)}${trades.length > 5 ? '\n... and ' + (trades.length - 5) + ' more' : ''}</div>
      </div>
    `;
  }
  
  // Journal Data
  if (data.data?.journal_data && data.data.journal_data.length > 0) {
    const journals = data.data.journal_data;
    html += `
      <div class="meta-section">
        <h4><i class="fas fa-book"></i> Journal Entries (${journals.length})</h4>
        <div class="meta-json">${JSON.stringify(journals.slice(0, 3), null, 2)}${journals.length > 3 ? '\n... and ' + (journals.length - 3) + ' more' : ''}</div>
      </div>
    `;
  }
  
  // Raw Response
  html += `
    <div class="meta-section">
      <h4><i class="fas fa-code"></i> Full Response</h4>
      <div class="meta-json">${JSON.stringify(data, null, 2)}</div>
    </div>
  `;
  
  elements.metadataContent.innerHTML = html;
}

// ============================================
// Send Query (with Streaming Support)
// ============================================

/**
 * Creates a streaming assistant message element that can be updated.
 */
function createStreamingMessage() {
  const welcome = elements.chatMessages.querySelector('.welcome-message');
  if (welcome) welcome.remove();
  
  const message = document.createElement('div');
  message.className = 'message assistant streaming';
  message.innerHTML = `
    <div class="message-avatar">
      <i class="fas fa-robot"></i>
    </div>
    <div class="message-content">
      <div class="message-text"></div>
      <div class="message-time">${formatTime(new Date())}</div>
    </div>
  `;
  
  elements.chatMessages.appendChild(message);
  elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
  
  return message;
}

/**
 * Updates a streaming message with new content.
 */
function updateStreamingMessage(message, text) {
  const textEl = message.querySelector('.message-text');
  if (textEl) {
    textEl.textContent = text;
    elements.chatMessages.scrollTop = elements.chatMessages.scrollHeight;
  }
}

/**
 * Finalizes a streaming message (removes streaming class).
 */
function finalizeStreamingMessage(message) {
  message.classList.remove('streaming');
}

/**
 * Sends a query with streaming response using Server-Sent Events.
 */
async function sendQueryStreaming() {
  const query = elements.query.value.trim();
  if (!query || isLoading) return;
  
  const userId = Number(elements.userId.value || 1);
  const currentSession = elements.sessionId.value || sessionId;
  
  // Update session display
  elements.sessionId.value = currentSession;
  
  // Add user message
  addMessage('user', query);
  
  // Clear input
  elements.query.value = '';
  autoResizeTextarea(elements.query);
  
  // Show loading initially
  isLoading = true;
  elements.sendBtn.disabled = true;
  
  // Collected data for metadata panel
  let collectedData = {
    response: '',
    data: {},
    metadata: {}
  };
  
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        session_id: currentSession,
        query: query,
        stream: true
      })
    });
    
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`HTTP ${res.status}: ${txt}`);
    }
    
    // Create streaming message element
    const streamingMessage = createStreamingMessage();
    let fullResponse = '';
    
    // Read the SSE stream
    const reader = res.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      
      buffer += decoder.decode(value, { stream: true });
      
      // Process complete SSE events (separated by double newlines)
      const events = buffer.split('\n\n');
      buffer = events.pop() || ''; // Keep incomplete event in buffer
      
      for (const eventBlock of events) {
        if (!eventBlock.trim()) continue;
        
        // Parse SSE event
        const lines = eventBlock.split('\n');
        let eventType = '';
        let eventData = '';
        
        for (const line of lines) {
          if (line.startsWith('event: ')) {
            eventType = line.slice(7);
          } else if (line.startsWith('data: ')) {
            eventData = line.slice(6);
          }
        }
        
        if (!eventData) continue;
        
        try {
          const data = JSON.parse(eventData);
          
          switch (eventType) {
            case 'start':
              // Query classification info
              collectedData.metadata.query_type = data.query_type;
              break;
              
            case 'data':
              // Retrieved trade/journal data
              collectedData.data = {
                trade_data: data.trade_data || [],
                journal_data: data.journal_data || []
              };
              // Update metadata panel with data immediately
              updateMetadataPanel(collectedData);
              break;
              
            case 'chunk':
              // Text chunk from LLM
              fullResponse += data.text;
              updateStreamingMessage(streamingMessage, fullResponse);
              break;
              
            case 'done':
              // Streaming complete
              collectedData.response = fullResponse;
              collectedData.metadata = {
                ...collectedData.metadata,
                duration_ms: data.duration_ms,
                response_length: data.response_length
              };
              finalizeStreamingMessage(streamingMessage);
              updateMetadataPanel(collectedData);
              break;
              
            case 'error':
              throw new Error(data.error || 'Stream error');
          }
        } catch (parseErr) {
          console.warn('Failed to parse SSE event:', parseErr, eventData);
        }
      }
    }
    
  } catch (err) {
    addMessage('error', `Error: ${err.message}`);
    updateMetadataPanel(null);
  } finally {
    isLoading = false;
    elements.sendBtn.disabled = false;
    elements.query.focus();
  }
}

/**
 * Sends a query without streaming (original behavior).
 */
async function sendQueryNonStreaming() {
  const query = elements.query.value.trim();
  if (!query || isLoading) return;
  
  const userId = Number(elements.userId.value || 1);
  const currentSession = elements.sessionId.value || sessionId;
  
  // Update session display
  elements.sessionId.value = currentSession;
  
  // Add user message
  addMessage('user', query);
  
  // Clear input
  elements.query.value = '';
  autoResizeTextarea(elements.query);
  
  // Show loading
  isLoading = true;
  elements.sendBtn.disabled = true;
  const loadingMsg = addMessage('loading');
  
  try {
    const res = await fetch(`${API_BASE}/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: userId,
        session_id: currentSession,
        query: query,
        stream: false
      })
    });
    
    removeLoadingMessage();
    
    if (!res.ok) {
      const txt = await res.text();
      throw new Error(`HTTP ${res.status}: ${txt}`);
    }
    
    const data = await res.json();
    
    // Add assistant message
    addMessage('assistant', data.response || '(No response)', data);
    
    // Update metadata panel
    updateMetadataPanel(data);
    
  } catch (err) {
    removeLoadingMessage();
    addMessage('error', `Error: ${err.message}`);
    updateMetadataPanel(null);
  } finally {
    isLoading = false;
    elements.sendBtn.disabled = false;
    elements.query.focus();
  }
}

// Use streaming by default
const sendQuery = sendQueryStreaming;

// ============================================
// Event Listeners
// ============================================

// Send button
elements.sendBtn.addEventListener('click', sendQuery);

// Enter key to send (Shift+Enter for new line)
elements.query.addEventListener('keydown', (e) => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendQuery();
  }
});

// Auto-resize textarea
elements.query.addEventListener('input', () => {
  autoResizeTextarea(elements.query);
});

// Toggle metadata panel
elements.toggleMetaBtn.addEventListener('click', () => {
  elements.metadataPanel.classList.toggle('hidden');
  elements.toggleMetaBtn.classList.toggle('active');
});

// Clear chat
elements.clearChatBtn.addEventListener('click', () => {
  elements.chatMessages.innerHTML = `
    <div class="welcome-message">
      <div class="welcome-icon">
        <i class="fas fa-chart-pie"></i>
      </div>
      <h2>Welcome to Journalyst AI</h2>
      <p>Ask me anything about your trading data, journal entries, or performance metrics.</p>
      <div class="welcome-examples">
        <span>Try asking:</span>
        <ul>
          <li>"Show my top 5 profitable trades this month"</li>
          <li>"What's my win rate on forex pairs?"</li>
          <li>"Analyze my emotional patterns when trading"</li>
        </ul>
      </div>
    </div>
  `;
  updateMetadataPanel(null);
});

// New session
elements.newSessionBtn.addEventListener('click', () => {
  sessionId = generateUUID();
  elements.sessionId.value = sessionId;
});

// Quick queries
elements.quickQueries.forEach(btn => {
  btn.addEventListener('click', () => {
    elements.query.value = btn.dataset.query;
    autoResizeTextarea(elements.query);
    elements.query.focus();
  });
});

// ============================================
// Initialize
// ============================================

// Set initial session ID
elements.sessionId.placeholder = sessionId.substring(0, 8) + '...';

// Check API status on load
checkApiStatus();

// Check API status every 30 seconds
setInterval(checkApiStatus, 30000);

// Focus query input
elements.query.focus();
