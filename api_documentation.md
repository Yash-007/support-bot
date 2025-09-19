# CoinSwitch Pro AI Chatbot - Hackathon Integration Guide

## Quick Start
The chatbot combines real-time trading data, portfolio information, and static FAQs to provide intelligent responses. Single API endpoint, simple integration.

## Core API
```
POST /api/chat
Content-Type: application/json
Cookie: st=your_auth_token

{
    "query": "Show me my portfolio value"
}
```

Response:
```json
{
    "answer": "Your natural language response here",
    "status": "success"
}
```

## Key Features

### 1. Smart Query Understanding
The system automatically detects what the user is asking about:
- Portfolio holdings and performance
- Wallet activity (deposits, withdrawals)
- Trading history (orders, PnL)
- Platform fees
- General FAQs

### 2. Real-time Data (requires auth)

#### Portfolio Queries
```
# Overall Portfolio
"What's my total portfolio value?"
"Show me my portfolio summary"
"How much profit/loss am I in?"
"Which assets are profitable?"
"Show me my best performing assets"
"What's my total investment value?"

# Specific Asset Queries
"How much ETH do I have?"
"What's my average buy price for BTC?"
"Show me my COMP holdings"
"What's my P&L on GMT?"
"Show me my blocked balance in USDT"
"What's my unrealized profit in ETH?"

# Asset Status
"Show me my staked assets"
"What's my available balance vs blocked?"
"Which assets are in orders?"
"Show me assets in my vault"
"What's my futures balance?"

# Performance Analysis
"Show me assets with positive P&L"
"Which coin am I losing most on?"
"What's my best performing asset?"
"Compare my BTC and ETH performance"
"Show me assets with over 10% profit"
```

#### Wallet Queries
```
"What's my total deposit amount in my wallet?"
"Show me my last 5 deposits"
"How much money have I withdrawn in total?"
"What's my current wallet balance?"
"Show me my transaction history"
```

#### Trading Queries
```
"What's my average purchase price for BTC?"
"Show me all my closed orders for ETH"
"How much Bitcoin have I bought in total?"
"What's my total trading volume?"
"Show me my ETH trading history"
```

### 3. Static Knowledge

#### Fee Structure Queries
```
"What are the spot trading fees?"
"Show me futures trading fees for INR pairs"
"What are the maker fees for USDT futures?"
"Tell me about options trading fees"
"What are the taker fees for spot trading?"
```

#### FAQ & Documentation Queries
```
"What documents do I need for KYC verification?"
"How does futures trading work on your platform?"
"What happens if my deposit fails?"
"How secure is my crypto on this platform?"
"What are the different types of orders I can place?"
```

## Quick Integration (React + TypeScript)

```typescript
// chatService.ts
interface ChatResponse {
  answer: string;
  status: 'success' | 'error';
}

const sendQuery = async (query: string): Promise<ChatResponse> => {
  try {
    const response = await fetch('/api/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query })
    });
    return await response.json();
  } catch (error) {
    return {
      status: 'error',
      answer: 'Something went wrong. Please try again.'
    };
  }
};

// ChatComponent.tsx
import { useState } from 'react';

export const ChatBot = () => {
  const [messages, setMessages] = useState<Array<{text: string, isUser: boolean}>>([]);
  const [input, setInput] = useState('');
  const [loading, setLoading] = useState(false);

  const handleSend = async () => {
    if (!input.trim()) return;
    
    // Add user message
    setMessages(prev => [...prev, { text: input, isUser: true }]);
    setLoading(true);

    try {
      const response = await sendQuery(input);
      // Add bot response
      setMessages(prev => [...prev, { text: response.answer, isUser: false }]);
    } catch (error) {
      setMessages(prev => [...prev, { 
        text: 'Sorry, I encountered an error. Please try again.',
        isUser: false 
      }]);
    }

    setLoading(false);
    setInput('');
  };

  return (
    <div className="chat-container">
      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={msg.isUser ? 'user-message' : 'bot-message'}>
            {msg.text}
          </div>
        ))}
        {loading && <div className="loading">...</div>}
      </div>
      <div className="input-area">
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyPress={(e) => e.key === 'Enter' && handleSend()}
          placeholder="Ask about your portfolio, trades, wallet, or any questions..."
        />
        <button onClick={handleSend}>Send</button>
      </div>
    </div>
  );
};
```

## Basic Styling
```css
.chat-container {
  max-width: 600px;
  margin: 0 auto;
  padding: 20px;
}

.messages {
  height: 400px;
  overflow-y: auto;
  padding: 10px;
  border: 1px solid #eee;
  border-radius: 8px;
}

.user-message,
.bot-message {
  margin: 10px 0;
  padding: 10px;
  border-radius: 8px;
  max-width: 80%;
}

.user-message {
  background: #007AFF;
  color: white;
  margin-left: auto;
}

.bot-message {
  background: #F0F0F0;
}

.input-area {
  margin-top: 20px;
  display: flex;
  gap: 10px;
}

input {
  flex: 1;
  padding: 10px;
  border: 1px solid #ddd;
  border-radius: 4px;
}

button {
  padding: 10px 20px;
  background: #007AFF;
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
}

.loading {
  text-align: center;
  color: #888;
}
```

## Implementation Tips

1. **Must-Haves**
   - Loading states for API calls
   - Error handling for failed requests
   - Message history
   - Clean, responsive UI

2. **Nice-to-Haves** (if time permits)
   - Message timestamps
   - Copy response to clipboard
   - Clear chat history
   - Save chat history
   - Markdown support in responses
   - Portfolio summary cards
   - Asset performance charts

3. **Auth Handling**
   - Get auth token from your app's session
   - Handle token expiry gracefully
   - Show login prompt when needed

Remember: The AI understands natural language, so users can ask questions conversationally!