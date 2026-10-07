export default function Avatar({ name, small = false }) {
  const initials = name.split(' ').slice(0, 2).map((part) => part[0]).join('');
  return <span className={`avatar ${small ? 'avatar-small' : ''}`} aria-hidden="true">{initials}</span>;
}
