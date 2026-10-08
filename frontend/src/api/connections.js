export class ApiError extends Error {
  constructor(message, status) { super(message); this.name = 'ApiError'; this.status = status; }
}

export async function sendConnectionRequest({ recipientId, messageText, accessToken }) {
  const response = await fetch('/api/connections/', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${accessToken}` },
    body: JSON.stringify({ recipient_id: recipientId, message_text: messageText }),
  });
  let data;
  try { data = await response.json(); } catch { data = null; }
  if (!response.ok) {
    const errors = {
      400: 'Check the recipient and message. The note must be at most 500 characters.',
      401: 'Your session expired. Sign in again before sending.',
      403: 'This person is currently unavailable to connect.',
      404: 'The connection endpoint or recipient could not be found. Confirm the API route with BE2.',
      409: 'A request already exists for this person.',
      429: 'You’ve reached the request limit. Try again later.',
      501: 'The backend connection endpoint is still a stub. Try again after BE2 implements it.',
    };
    throw new ApiError(errors[response.status] || 'Could not send the request. Please try again.', response.status);
  }
  if (response.status !== 201 || !Number.isInteger(data?.id) || data.status !== 'pending') {
    throw new ApiError('The server response did not match the agreed request shape. Confirm it with BE2.', response.status);
  }
  return data;
}
