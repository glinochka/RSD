/**
 * Wrapper for legal / static policy pages (MainLayout + typography shell).
 */

import React from 'react';
import { Link } from 'react-router-dom';
import MainLayout from './Layout';
import { NAVIGATION_ROUTES } from '../config/constants';
import '../styles/legalDocument.css';

const LegalDocCrossLinks = () => (
  <nav className="legal-document-crosslinks" aria-label="Связанные документы">
    <Link to={NAVIGATION_ROUTES.PUBLIC_OFFER}>Публичная оферта</Link>
    <span className="legal-document-crosslinks-sep" aria-hidden="true">
      ·
    </span>
    <Link to={NAVIGATION_ROUTES.USER_AGREEMENT}>Пользовательское соглашение</Link>
    <span className="legal-document-crosslinks-sep" aria-hidden="true">
      ·
    </span>
    <Link to={NAVIGATION_ROUTES.PRIVACY_POLICY}>Политика конфиденциальности</Link>
  </nav>
);

const LegalDocumentLayout = ({ title, editionLabel, children }) => {
  return (
    <MainLayout>
      <div className="legal-document-page">
        <div className="container legal-document-inner">
          <article className="legal-document">
            <header className="legal-document-header">
              <h1>{title}</h1>
              {editionLabel ? <p className="legal-document-meta">{editionLabel}</p> : null}
            </header>
            <div className="legal-document-body">{children}</div>
            <footer className="legal-document-footer">
              <LegalDocCrossLinks />
            </footer>
          </article>
        </div>
      </div>
    </MainLayout>
  );
};

export default LegalDocumentLayout;
