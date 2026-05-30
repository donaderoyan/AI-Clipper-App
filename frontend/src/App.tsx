import { useState } from 'react';
import { useWebSocket } from './hooks/useWebSocket';
import { TerminalUI } from './components/TerminalUI';
import { Video, Play } from 'lucide-react';
import './App.css';

function App() {
  const [wsUrl, setWsUrl] = useState<string | null>(null);
  const { subscribe, notifyListeners } = useWebSocket(wsUrl);

  const [url, setUrl] = useState('');
  const [ratio, setRatio] = useState('9:16');
  const [duration, setDuration] = useState('');
  const [count, setCount] = useState('');
  const [prompt, setPrompt] = useState('');
  const [timestamps, setTimestamps] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsProcessing(true);
    notifyListeners(`\x1b[36m[SYSTEM] Submitting job for ${url}...\x1b[0m\r\n`);
    
    try {
      const response = await fetch('http://localhost:8000/api/v1/process', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ 
          url, 
          ratio, 
          duration: duration ? parseInt(duration, 10) : undefined, 
          count: count ? parseInt(count, 10) : undefined, 
          prompt, 
          timestamps 
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
      }

      const data = await response.json();
      if (data.job_id) {
        notifyListeners(`\x1b[32m[SYSTEM] Job created successfully. Job ID: ${data.job_id}\x1b[0m\r\n`);
        setWsUrl(`ws://localhost:8000/api/v1/ws/status/${data.job_id}`);
      } else {
        notifyListeners(`\x1b[33m[SYSTEM] Unexpected response: No job_id returned.\x1b[0m\r\n`);
      }
    } catch (error) {
      notifyListeners(`\x1b[31m[SYSTEM] Failed to start processing: ${error instanceof Error ? error.message : String(error)}\x1b[0m\r\n`);
    } finally {
      setIsProcessing(false);
    }
  };

  return (
    <div className="app-container">
      {/* Left Panel: Input Form */}
      <aside className="left-panel">
        <div className="panel-header">
          <Video className="brand-icon" />
          <h1>AI Clipper</h1>
        </div>
        
        <form className="input-form" onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="url">YouTube URL *</label>
            <input 
              type="url" 
              id="url"
              required
              placeholder="https://www.youtube.com/watch?v=..."
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              disabled={isProcessing}
            />
          </div>

          <div className="form-row">
            <div className="form-group half">
              <label htmlFor="ratio">Aspect Ratio</label>
              <select id="ratio" value={ratio} onChange={(e) => setRatio(e.target.value)} disabled={isProcessing}>
                <option value="9:16">Vertical (9:16)</option>
                <option value="16:9">Horizontal (16:9)</option>
              </select>
            </div>
            <div className="form-group half">
              <label htmlFor="duration">Target Duration (min)</label>
              <input 
                type="number" 
                id="duration"
                min="1"
                placeholder="e.g. 3"
                value={duration}
                onChange={(e) => setDuration(e.target.value)}
                disabled={isProcessing}
              />
            </div>
          </div>

          <div className="form-group">
            <label htmlFor="count">Max Output Clips</label>
            <input 
              type="number" 
              id="count"
              min="1"
              placeholder="e.g. 5"
              value={count}
              onChange={(e) => setCount(e.target.value)}
              disabled={isProcessing}
            />
          </div>

          <div className="form-group">
            <label htmlFor="prompt">AI Context Prompt</label>
            <textarea 
              id="prompt"
              rows={3}
              placeholder="What kind of moments are you looking for?"
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              disabled={isProcessing}
            />
          </div>

          <div className="form-group">
            <label htmlFor="timestamps">Custom Timestamps (Optional)</label>
            <input 
              type="text" 
              id="timestamps"
              placeholder="e.g. 01:20-02:00, 05:00-06:30"
              value={timestamps}
              onChange={(e) => setTimestamps(e.target.value)}
              disabled={isProcessing}
            />
          </div>

          <button type="submit" className="btn-submit" disabled={!url || isProcessing}>
            <Play size={18} />
            {isProcessing ? 'Submitting...' : 'Start Processing'}
          </button>
        </form>
      </aside>

      {/* Right Panel: Terminal Pipeline */}
      <main className="right-panel">
        <div className="terminal-wrapper">
          <TerminalUI subscribe={subscribe} height="100%" />
        </div>
      </main>
    </div>
  );
}

export default App;
