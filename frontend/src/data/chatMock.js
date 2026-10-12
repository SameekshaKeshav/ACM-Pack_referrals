export const currentUser = { id: 7, name: 'Sanjana Shetty' };
export const incomingRequests = [
  { id: 123, sender: { id: 21, name: 'Maya Patel', company: 'IBM', role: 'Computer Science · Class of 2027' }, message_text: 'Hi Sanjana! I saw your work at IBM. Could we connect and talk about the software engineering internship?', status: 'pending', created_at: 'Today' },
  { id: 124, sender: { id: 22, name: 'Alex Rivera', company: 'Red Hat', role: 'Computer Engineering · Class of 2026' }, message_text: 'Hey! I’m exploring cloud engineering roles and would love to hear about your experience.', status: 'pending', created_at: 'Yesterday' },
  { id: 125, sender: { id: 23, name: 'Jordan Lee', company: 'Cisco', role: 'Computer Science · Class of 2028' }, message_text: 'Fellow Wolfpack here! Would you be open to sharing a few tips for my first internship search?', status: 'pending', created_at: 'Yesterday' },
];
export const outgoingRequests = [
  { id: 201, recipient: { id: 31, name: 'Priya Shah', company: 'Microsoft' }, message_text: 'I’d love to learn about your summer internship experience.', status: 'pending', created_at: 'Today' },
  { id: 202, recipient: { id: 32, name: 'Ethan Brooks', company: 'SAS' }, message_text: 'Thanks for connecting with the Wolfpack community!', status: 'accepted', created_at: 'Oct 5' },
];
export const conversations = [
  { id: 5, other_user: { id: 41, name: 'Avery Chen', company: 'Red Hat', role: 'Software Engineering Intern' }, last_message: 'Happy to help. Send me the role you’re interested in!', updated_at: '10:34 AM', unread_count: 0 },
  { id: 6, other_user: { id: 42, name: 'Sam Wilson', company: 'IBM', role: 'Software Engineering Intern' }, last_message: 'Let’s find a time to chat this week.', updated_at: 'Yesterday', unread_count: 2 },
  { id: 7, other_user: { id: 43, name: 'Nina Davis', company: 'Cisco', role: 'Network Engineering Intern' }, last_message: 'The team was really welcoming.', updated_at: 'Mon', unread_count: 0 },
];
export const fiveMessageThread = [
  { id: 1, sender_id: 41, body_text: 'Hi Sanjana! Thanks for reaching out. What would you like to know about Red Hat?', created_at: '10:30 AM' },
  { id: 2, sender_id: 7, body_text: 'Thanks for connecting! How was your software engineering internship?', created_at: '10:31 AM' },
  { id: 3, sender_id: 41, body_text: 'I worked on the platform team. Lots of hands-on learning and a great mentor.', created_at: '10:32 AM' },
  { id: 4, sender_id: 7, body_text: 'That sounds great. Could I ask about the application process too?', created_at: '10:33 AM' },
  { id: 5, sender_id: 41, body_text: 'Happy to help. Send me the role you’re interested in!', created_at: '10:34 AM' },
];
