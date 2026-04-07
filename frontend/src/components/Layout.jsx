/**
 * MainLayout
 * Main wrapper for pages with header and footer
 */

import React from 'react';
import Navbar from './Navbar';
import Footer from './Footer';
import '../styles/layout.css';

const MainLayout = ({ children, showNavbar = true }) => {
  return (
    <div className="layout">
      {showNavbar && <Navbar />}
      <main className="layout-main">
        {children}
      </main>
      <Footer />
    </div>
  );
};

export default MainLayout;
