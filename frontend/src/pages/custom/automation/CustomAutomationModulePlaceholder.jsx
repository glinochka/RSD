import React from 'react';
import { useParams } from 'react-router-dom';
import { UBT_MODULES } from './customNav';
import '../../../styles/customSolutionNav.css';

const CustomAutomationModulePlaceholder = () => {
  const { moduleId } = useParams();
  const module = UBT_MODULES.find((item) => item.id === moduleId);
  const labels = {
    'dm-broadcasts': 'ЛС-рассылки',
    masstagging: 'Масстегинг',
    neurodialogs: 'Нейродиалоги',
  };
  const title = module?.label || labels[moduleId] || 'Модуль';

  return (
    <div className="ubt-placeholder">
      <span className="ubt-badge">Телеграм УБТ</span>
      <h1>{title}</h1>
      <p>
        Этого раздела нет в текущем контуре. Входящие личные обрабатывает перехват заявок,
        ответы в группах — нейрочаттинг, списки чатов — парсер и раздел «Чаты».
      </p>
    </div>
  );
};

export default CustomAutomationModulePlaceholder;
