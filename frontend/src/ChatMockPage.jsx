import { useState } from 'react';
import RequestQueue from './components/RequestQueue';
import ConversationListItem from './components/ConversationListItem';
import ChatWindow from './components/ChatWindow';
import SendRequestForm from './components/SendRequestForm';
import { incomingRequests, outgoingRequests, conversations, fiveMessageThread, currentUser } from './data/chatMock';

export default function ChatMockPage() {
  const [incoming, setIncoming] = useState(incomingRequests);
  const [outgoing, setOutgoing] = useState(outgoingRequests);
  const [tab, setTab] = useState('incoming');
  const [selectedId, setSelectedId] = useState(5);
  const [notice, setNotice] = useState('');
  const [accessToken, setAccessToken] = useState('');
  const conversation = conversations.find((item) => item.id === selectedId);

  function resolveRequest(id, action) {
    console.info(`PATCH /api/connections/${id}/${action}/`, { mock: true });
    setIncoming((requests) => requests.filter((request) => request.id !== id));
    setNotice(`Request #${id} ${action === 'accept' ? 'accepted' : 'declined'} locally. No API call was made.`);
  }

  function reset() { setIncoming(incomingRequests); setOutgoing(outgoingRequests); setTab('incoming'); setSelectedId(5); setNotice('Demo data reset.'); }

  return <div className="app-shell">
    <header className="site-header"><a className="brand" href="/chat-mock"><span className="brand-mark">PR</span>Pack Referrals</a><span className="school">NC STATE UNIVERSITY</span><span className="user-chip">SS <span>Sanjana</span></span></header>
    <main className="main-content">
      <div className="page-heading"><div><p className="eyebrow">YOUR WOLFPACK NETWORK</p><h1>Chat & Connect</h1><p>Good connections start with a conversation.</p></div><button className="button-secondary" onClick={reset}>Reset demo</button></div>
      <div className="demo-banner"><span className="demo-dot" /><span><strong>Chat mock</strong> · requests and conversations below use fictional data. Send Request uses the live API.</span></div>
      <section aria-labelledby="requests-heading" className="requests-section">
        <div className="section-heading"><h2 id="requests-heading">Connection requests</h2><span className="meta">A shared campus. A new opportunity.</span></div>
        <div className="tabs" role="tablist" aria-label="Request direction">
          <button id="incoming-tab" role="tab" aria-selected={tab === 'incoming'} aria-controls="requests-panel" onClick={() => setTab('incoming')}>Incoming <span>{incoming.length}</span></button>
          <button id="outgoing-tab" role="tab" aria-selected={tab === 'outgoing'} aria-controls="requests-panel" onClick={() => setTab('outgoing')}>Outgoing <span>{outgoing.length}</span></button>
        </div>
        <div id="requests-panel" role="tabpanel" aria-labelledby={`${tab}-tab`}><RequestQueue requests={tab === 'incoming' ? incoming : outgoing} direction={tab} onAccept={(id) => resolveRequest(id, 'accept')} onDecline={(id) => resolveRequest(id, 'decline')} /></div>
        <p className="local-notice" role="status">{notice}</p>
      </section>
      <section aria-labelledby="conversations-heading"><div className="section-heading"><h2 id="conversations-heading">Conversations</h2><span className="meta">Private, one-to-one chats</span></div>
        <div className="chat-layout"><aside className="conversation-sidebar" aria-label="Conversation list"><div className="sidebar-heading">Messages <span>{conversations.length}</span></div>{conversations.map((item) => <ConversationListItem key={item.id} conversation={item} selected={item.id === selectedId} onSelect={setSelectedId} />)}</aside><ChatWindow key={selectedId} conversation={conversation} messages={selectedId === 5 ? fiveMessageThread : []} currentUser={currentUser} /></div>
      </section>
      <section className="request-api-section" aria-labelledby="send-heading"><div className="api-description"><p className="eyebrow">CONNECT WITH SOMEONE NEW</p><h2 id="send-heading">Send a request</h2><p>Your note is limited to 500 characters. This form posts to <code>/api/connections/</code>.</p><details className="api-settings"><summary>API test panel</summary><p>Run Django on port 8000. Use a valid JWT for your test account. The token stays in page memory and clears on refresh.</p><label htmlFor="access-token">Access token</label><input id="access-token" type="password" autoComplete="off" value={accessToken} onChange={(e) => setAccessToken(e.target.value)} placeholder="Paste a test access token" /><p className="meta">Do not send test requests to real users. BE2 must implement this endpoint before a real send can succeed.</p></details></div><SendRequestForm accessToken={accessToken} onCreated={(request) => setOutgoing((requests) => [...requests, request])} /></section>
    </main><footer className="site-footer">Built for the Wolfpack · Chat & Connect preview</footer>
  </div>;
}
