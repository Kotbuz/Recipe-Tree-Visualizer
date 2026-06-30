import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import { installDesktopFetchProxy } from './api/base';
import './styles/index.css';

installDesktopFetchProxy();

const root = ReactDOM.createRoot(document.getElementById('root')!);
root.render(
    <React.StrictMode>
        <App />
    </React.StrictMode>
);
