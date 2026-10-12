import React from 'react';
import { createRoot } from 'react-dom/client';
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom';
import ChatMockPage from './ChatMockPage';
import './styles.css';

createRoot(document.getElementById('root')).render(
  <React.StrictMode>
    <BrowserRouter>
      <Routes>
        <Route path="/chat-mock" element={<ChatMockPage />} />
        <Route path="*" element={<Navigate to="/chat-mock" replace />} />
      </Routes>
    </BrowserRouter>
  </React.StrictMode>,
);
