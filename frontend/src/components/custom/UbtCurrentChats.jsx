import React from 'react';
import FeatureToggle from '../FeatureToggle';

const UbtCurrentChats = ({ checked, onChange }) => (
  <FeatureToggle
    compact
    title="Работать с текущими чатами/каналами"
    description="Кроме целей этой задачи аккаунт работает и в чатах проекта, где уже состоит. Новое вступление туда не ставим. Если в одном таком чате сидят несколько выбранных аккаунтов, задачу ведёт один из них."
    checked={Boolean(checked)}
    onChange={onChange}
  />
);

export default UbtCurrentChats;
