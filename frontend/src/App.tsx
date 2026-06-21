import './styles/App.css';
import { useEffect, useState } from 'react';
import PreviewPage from './PreviewPage';

function App() {
    const [route, setRoute] = useState<string>(window.location.hash || '#home');

    useEffect(() => {
        const onHash = () => setRoute(window.location.hash || '#home');
        window.addEventListener('hashchange', onHash);
        return () => window.removeEventListener('hashchange', onHash);
    }, []);

    return (
        <div className="app">
            <header className="app-header">
                <h1>Recipe Tree Visualizer</h1>
                <p>React + TypeScript frontend structure is ready.</p>
                <div style={{ marginTop: 12 }}>
                    {route !== '#preview' ? (
                        <button onClick={() => (window.location.hash = '#preview')}>Перейти к предпросмотру</button>
                    ) : (
                        <button onClick={() => (window.location.hash = '#home')}>Назад</button>
                    )}
                </div>
            </header>
            <main className="app-main">
                {route === '#preview' ? <PreviewPage /> : <div className="home-message">Открой предпросмотр блока и предмета нажатием кнопки.</div>}
            </main>
        </div>
    );
}

export default App;
