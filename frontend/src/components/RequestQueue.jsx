import ConnectionRequestCard from './ConnectionRequestCard';

export default function RequestQueue({ requests, direction = 'incoming', onAccept, onDecline }) {
  return <div className="request-grid">
    {requests.length === 0 ? <p className="empty-state">You’re all caught up. No {direction} requests.</p> : requests.map((request) => (
      <ConnectionRequestCard key={request.id} request={request} direction={direction} onAccept={onAccept} onDecline={onDecline} />
    ))}
  </div>;
}
