import '../styles/demoBadge.css';

/** Плашка «Демо» для голосовой телефонии */
export default function DemoBadge({ className = '' }) {
  return <span className={`demo-badge${className ? ` ${className}` : ''}`}>Демо</span>;
}

/** Заголовок секции с плашкой «Демо» */
export function TitleWithDemoBadge({ as: Tag = 'span', className = '', children }) {
  return (
    <Tag className={`title-with-demo-badge${className ? ` ${className}` : ''}`}>
      {children}
      <DemoBadge />
    </Tag>
  );
}
