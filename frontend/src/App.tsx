import './styles/App.css';
import RecipeCanvas from './RecipeCanvas';
import { MinecraftVersionProvider } from './context/MinecraftVersionContext';

function App() {
    return (
        <MinecraftVersionProvider>
            <RecipeCanvas />
        </MinecraftVersionProvider>
    );
}

export default App;
