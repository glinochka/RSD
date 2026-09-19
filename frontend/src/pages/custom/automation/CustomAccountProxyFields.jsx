import React from 'react';
import CustomSelect from '../../../components/CustomSelect';

const AUTO_OPTION = { value: '', label: 'Авто из пула' };

const CustomAccountProxyFields = ({
  proxies = [],
  proxyId,
  proxyLine,
  onProxyIdChange,
  onProxyLineChange,
  disabled = false,
  hint = 'Можно выбрать прокси из пула или ввести новый — он останется только у этого аккаунта.',
}) => {
  const options = [
    AUTO_OPTION,
    ...proxies.map((item) => ({
      value: String(item.id),
      label: item.label || `${item.scheme}://${item.host}:${item.port}`,
    })),
  ];
  const hasOwnLine = Boolean((proxyLine || '').trim());

  return (
    <>
      <div className="form-group">
        <label htmlFor="account-proxy-pool">Прокси из пула</label>
        <CustomSelect
          id="account-proxy-pool"
          value={hasOwnLine ? '' : proxyId}
          options={options}
          onChange={(e) => onProxyIdChange(e.target.value)}
          disabled={disabled || hasOwnLine}
        />
      </div>
      <div className="form-group">
        <label htmlFor="account-proxy-line">Свой прокси (только этот аккаунт)</label>
        <input
          id="account-proxy-line"
          type="text"
          value={proxyLine}
          onChange={(e) => onProxyLineChange(e.target.value)}
          disabled={disabled}
          placeholder="socks5://user:pass@host:port"
        />
        <p className="form-hint">{hint}</p>
      </div>
    </>
  );
};

export default CustomAccountProxyFields;
